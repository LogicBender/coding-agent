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

    def add_context_node(self, node_id: str, task: str, result: str, core_details: str, raw_content: list, edges: list, turn_index: int):
        """添加一个新的上下文节点（轻量化，只存索引）"""
        import copy
        # 去重处理：如果当前回合存在 expand_node 的大段返回，将其从写入 raw_log 的数组中剔除以防指数级膨胀
        cleaned_content = []
        for msg in raw_content:
            msg_copy = copy.deepcopy(msg)
            if msg_copy.get("role") == "tool" and isinstance(msg_copy.get("content"), str):
                if "展开成功" in msg_copy["content"]:
                    header = msg_copy["content"].split("\n")[0]
                    msg_copy["content"] = f"{header}\n[详细内容已在本地存储中去重，请直接查阅被引用的原图谱节点]"
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
            return f"❌ 错误: 图中不存在节点 {node_id}"
        
        node = self.graph.nodes[node_id]
        if node.get('in_Context') == True:
            return f"⚠️ 节点 {node_id} 当前状态为 in_Context: true，其上下文仍在近期历史记录中，无需额外展开。"
            
        turn_idx = node.get('turn_index')
        if turn_idx is None:
            return f"❌ 错误: 节点 {node_id} 丢失了线性日志指针。"
            
        try:
            with open(self.raw_log_path, 'r', encoding='utf-8') as f:
                for line in f:
                    data = json.loads(line.strip())
                    if data.get("turn_index") == turn_idx:
                        raw = data.get("messages", [])
                        content_str = "\n".join([f"[{m.get('role')}]: {m.get('content')}" for m in raw])
                        
                        # 建立指针软连接
                        if current_node_id and self.graph.has_node(node_id):
                            self.graph.nodes[node_id]['in_Context'] = f"🔗 指向 {current_node_id}"
                            self.save()
                            
                        return f"✅ 节点 {node_id} 展开成功:\n{content_str}"
            return f"❌ 错误: 在原始线性日志中未找到 turn_index {turn_idx}"
        except Exception as e:
            return f"❌ 错误: 读取原始日志失败: {str(e)}"

    def get_graph_json(self) -> str:
        """直接输出原生图结构 JSON，供放在 [D] 区"""
        if self.graph.number_of_nodes() == 0:
            return "{}"
        data = nx.node_link_data(self.graph)
        return json.dumps(data, ensure_ascii=False, indent=2)
