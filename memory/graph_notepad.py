import os
import json
import networkx as nx

class GraphNotepad:
    def __init__(self, persist_path: str, raw_log_path: str):
        self.persist_path = persist_path
        self.raw_log_path = raw_log_path
        self.graph = nx.DiGraph()
        self.load()

    def load(self):
        if os.path.exists(self.persist_path):
            try:
                with open(self.persist_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.graph = nx.node_link_graph(data)
            except Exception:
                self.graph = nx.DiGraph()
        else:
            self.graph = nx.DiGraph()

    def save(self):
        try:
            data = nx.node_link_data(self.graph)
            with open(self.persist_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def add_context_node(self, node_id: str, task: str, result: str, core_details: str, raw_content: list, edges: list, turn_index: int, commit_hash: str = ""):
        """添加一个新的上下文节点（轻量化，只存索引）"""
        import copy
        # 1. 精准溯源：提取当前回合中所有调用了 expand_node 的 tool_call_id
        expand_node_call_ids = set()
        for msg in raw_content:
            if msg.get("role") == "assistant" and "tool_calls" in msg and msg["tool_calls"]:
                for tc in msg["tool_calls"]:
                    try:
                        # 兼容 pydantic 对象或 dict 字典
                        if isinstance(tc, dict):
                            func_name = tc.get("function", {}).get("name")
                            t_id = tc.get("id")
                        else:
                            func_name = getattr(getattr(tc, "function", None), "name", None)
                            t_id = getattr(tc, "id", None)
                            
                        if func_name == "expand_node" and t_id:
                            expand_node_call_ids.add(t_id)
                    except: pass
                    
        # 2. 对象级拦截：去重处理
        cleaned_content = []
        for msg in raw_content:
            msg_copy = copy.deepcopy(msg)
            if msg_copy.get("role") == "tool" and msg_copy.get("tool_call_id") in expand_node_call_ids:
                if isinstance(msg_copy.get("content"), str):
                    header = msg_copy["content"].split("\n")[0]
                    msg_copy["content"] = f"{header}\n[详细内容已在本地外存中去重，请直接查阅原图谱节点]"
            cleaned_content.append(msg_copy)

        try:
            with open(self.raw_log_path, 'a', encoding='utf-8') as f:
                f.write(json.dumps({"turn_index": turn_index, "messages": cleaned_content}, ensure_ascii=False) + "\n")
        except Exception:
            pass

        self.graph.add_node(
            node_id, 
            task=task,
            result=result,
            core_details=core_details,
            turn_index=turn_index,
            commit_hash=commit_hash,
            in_Context=True
        )
        
        nodes = list(self.graph.nodes())
        if len(nodes) > 1:
            prev_node = nodes[-2]
            self.graph.add_edge(prev_node, node_id, relation="NEXT_STEP")
            
        for target_id in edges:
            if self.graph.has_node(target_id):
                self.graph.add_edge(node_id, target_id, relation="RELATES_TO")
                
        self.save()
        return node_id

    def evict_node(self, node_id: str):
        """将节点标记为缺页换出状态，并清空所有指向该节点的弱引用指针"""
        if self.graph.has_node(node_id):
            self.graph.nodes[node_id]['in_Context'] = False
            
        # 指针垃圾回收：如果有其他节点通过指针借用了它的上下文，此刻也必须失效
        for n_id in self.graph.nodes():
            in_ctx = self.graph.nodes[n_id].get('in_Context')
            if isinstance(in_ctx, str) and str(node_id) in in_ctx:
                self.graph.nodes[n_id]['in_Context'] = False
                
        self.save()

    def expand_node(self, node_id: str, current_node_id: str = None) -> str:
        """供大模型调用：循着指针去原始线性日志里捞取原文，并建立软链接指针"""
        if not self.graph.has_node(node_id):
            return f"[Error] 错误: 图中不存在节点 {node_id}"
        
        node = self.graph.nodes[node_id]
        if node.get('in_Context') == True:
            return f"[Warn] 节点 {node_id} 当前状态为 in_Context: true，其上下文仍在近期历史记录中，无需额外展开。"
            
        turn_idx = node.get('turn_index')
        if turn_idx is None:
            return f"[Error] 错误: 节点 {node_id} 丢失了线性日志指针。"
            
        try:
            with open(self.raw_log_path, 'r', encoding='utf-8') as f:
                for line in f:
                    data = json.loads(line.strip())
                    if data.get("turn_index") == turn_idx:
                        raw = data.get("messages", [])
                        content_str = "\n".join([f"[{m.get('role')}]: {m.get('content')}" for m in raw])
                        
                        # 建立指针软连接
                        if current_node_id and self.graph.has_node(node_id):
                            self.graph.nodes[node_id]['in_Context'] = f" 指向 {current_node_id}"
                            self.save()
                            
                        return f"[Success] 节点 {node_id} 展开成功:\n{content_str}"
            return f"[Error] 错误: 在原始线性日志中未找到 turn_index {turn_idx}"
        except Exception as e:
            return f"[Error] 错误: 读取原始日志失败: {str(e)}"

    def get_markdown_view(self) -> str:
        """输出可读性高的 Markdown 列表格式，包含状态和关联节点"""
        if self.graph.number_of_nodes() == 0:
            return "（上下文轨迹为空）"
            
        lines = []
        for node_id, data in self.graph.nodes(data=True):
            in_ctx = data.get("in_Context")
            if in_ctx is True:
                status = "[In_Memory]"
            elif isinstance(in_ctx, str):
                status = f"[{in_ctx.strip()}]"
            else:
                status = "[Evicted]"
                
            task = data.get("task", "")
            
            # 提取非 NEXT_STEP 的语义关联边
            related_nodes = []
            for u, v, edata in self.graph.edges(data=True):
                if edata.get("relation") == "RELATES_TO" and (u == node_id or v == node_id):
                    target = v if u == node_id else u
                    if target not in related_nodes:
                        related_nodes.append(target)
            
            edge_str = f" 相关联的上下文节点: {', '.join(related_nodes)}" if related_nodes else ""
            lines.append(f"- {node_id}: {task} {status}{edge_str}")
                
        return "\n".join(lines)
