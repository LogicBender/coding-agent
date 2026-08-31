import os
import json
import networkx as nx

class EngineeringGraph:
    """
    工程逻辑图：负责管理任务网络 (Task Network)、文件树 (File Tree) 以及抽象语法树 (AST)。
    完全独立于上下文内存图 (Context Network)。
    """
    def __init__(self, persist_path: str):
        self.persist_path = persist_path
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

    def update_plan(self, goals: list, dependencies: list):
        """
        接收 LLM 传来的局部 2-Hop 更新 (Patch)。
        goals: [{"id": "G_Auth", "desc": "...", "status": "✅ 已完成" | "⏳ 正在攻坚" | "⏳ 待处理"}]
        dependencies: [{"from": "G_API", "on": "G_Auth"}]
        """
        # 1. 更新或插入节点
        for g in goals:
            node_id = g['id']
            if not self.graph.has_node(node_id):
                self.graph.add_node(node_id, type="task", desc=g.get('desc', ''), status=g.get('status', '⏳ 待处理'))
            else:
                # 仅更新被声明的属性
                if 'desc' in g and g['desc']:
                    self.graph.nodes[node_id]['desc'] = g['desc']
                if 'status' in g and g['status']:
                    self.graph.nodes[node_id]['status'] = g['status']

        # 2. 更新边关系：首先清除 goals 列表中提及的源节点 (from) 的旧依赖，保证依赖能被覆盖重构
        from_nodes = set([d['from'] for d in dependencies])
        for u in from_nodes:
            if self.graph.has_node(u):
                # 找到所有以 u 为起点，关系为 DEPENDS_ON 的边，全部删掉重连
                edges_to_remove = [(u, v) for u, v, d in self.graph.edges(u, data=True) if d.get('relation') == 'DEPENDS_ON']
                self.graph.remove_edges_from(edges_to_remove)

        # 3. 建立新依赖 (from 依赖于 on)
        for d in dependencies:
            u, v = d['from'], d['on']
            if self.graph.has_node(u) and self.graph.has_node(v):
                self.graph.add_edge(u, v, relation="DEPENDS_ON")
                
        self.save()

    def link_file_to_task(self, task_id: str, filepath: str):
        """将物理文件节点挂载到任务节点上"""
        if not self.graph.has_node(task_id):
            return
            
        if not self.graph.has_node(filepath):
            self.graph.add_node(filepath, type="file")
            
        self.graph.add_edge(filepath, task_id, relation="IMPLEMENTS")
        self.save()

    def get_markdown_view(self) -> str:
        """渲染供 LLM 查看的宏观拓扑结构 (包含 Task 和 File)"""
        tasks = [n for n, d in self.graph.nodes(data=True) if d.get('type') == 'task']
        if not tasks:
            return "当前项目暂无宏观规划。"

        lines = []
        for t in tasks:
            node = self.graph.nodes[t]
            status = node.get('status', '⏳ 待处理')
            desc = node.get('desc', '')
            
            # 查找依赖
            depends_on = [v for u, v, d in self.graph.edges(t, data=True) if d.get('relation') == 'DEPENDS_ON']
            dep_str = f" (依赖: {', '.join(depends_on)})" if depends_on else ""
            
            # 查找挂载的文件
            files = [u for u, v, d in self.graph.in_edges(t, data=True) if d.get('relation') == 'IMPLEMENTS']
            file_str = f" -> [已实现于] {', '.join(files)}" if files else ""
            
            lines.append(f"- [{status}] {t}: {desc}{dep_str}{file_str}")
            
            # 此处预留给 AST 解析：
            # 如果文件存在 AST 子节点，可以在这里进一步缩进打印
            
        return "\n".join(lines)
