import json
import os
import re

def patch_agent_advanced():
    filepath = "/mnt/d/project/coding/agent.py"
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # We will replace the entire rollback_to_turn and fork_session functions.
    
    new_rollback = """    def rollback_to_turn(self, turn_index: int):
        target_turn = next((t for t in self.history_B if t.get("turn_index") == turn_index), None)
        commit_hash = None
        evicted = False
        
        if target_turn:
            commit_hash = target_turn.get("commit_hash")
        else:
            node_id = f"Node_{turn_index}"
            if self.notepad.graph.has_node(node_id):
                commit_hash = self.notepad.graph.nodes[node_id].get("commit_hash")
                evicted = True
                
        if not commit_hash:
            return f"[red][Error] 找不到回合 {turn_index} 的记录或 Git Hash，无法回滚。[/red]"
            
        import subprocess
        try:
            subprocess.check_call(["git", "reset", "--hard", commit_hash], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            return f"[red][Error] Git 回滚失败: {e}[/red]"
            
        if evicted:
            # 被换出的节点回滚：清空当前 B 区，从外存调回自身及前两回合
            self.history_B = []
            if os.path.exists(self.notepad.raw_log_path):
                with open(self.notepad.raw_log_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        try:
                            data = json.loads(line)
                            t_idx = data.get('turn_index')
                            # 提取目标回合及前两回合（[turn_index-2, turn_index]）
                            if t_idx and (turn_index - 2 <= t_idx <= turn_index):
                                self.history_B.append(data)
                        except: pass
        else:
            # 正常回滚：截断历史
            self.history_B = [t for t in self.history_B if t.get("turn_index") <= turn_index]
            
        self.save_history()
        
        # 截断图谱
        nodes_to_remove = [n for n, d in self.notepad.graph.nodes(data=True) if d.get('turn_index') and d['turn_index'] > turn_index]
        self.notepad.graph.remove_nodes_from(nodes_to_remove)
        self.notepad.save()
        
        # 重写 raw_log
        if os.path.exists(self.notepad.raw_log_path):
            lines = []
            with open(self.notepad.raw_log_path, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        if json.loads(line).get('turn_index') <= turn_index:
                            lines.append(line)
                    except: pass
            with open(self.notepad.raw_log_path, 'w', encoding='utf-8') as f:
                f.writelines(lines)
                
        return f"[cyan][系统] 成功回滚到回合 {turn_index} (Commit: {commit_hash[:7]})。{' (已从外存重载该区间上下文)' if evicted else ''}[/cyan]" """

    new_fork = """    def fork_session(self, turn_index: int, new_session_name: str):
        target_turn = next((t for t in self.history_B if t.get("turn_index") == turn_index), None)
        commit_hash = None
        evicted = False
        
        if target_turn:
            commit_hash = target_turn.get("commit_hash")
        else:
            node_id = f"Node_{turn_index}"
            if self.notepad.graph.has_node(node_id):
                commit_hash = self.notepad.graph.nodes[node_id].get("commit_hash")
                evicted = True
                
        if not commit_hash:
            return f"[red][Error] 找不到回合 {turn_index} 的记录或 Git Hash，无法创建分支。[/red]"
            
        import subprocess
        try:
            subprocess.check_call(["git", "checkout", "-b", new_session_name, commit_hash], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            return f"[red][Error] Git 创建分支失败: {e}[/red]"
            
        import shutil
        new_folder = os.path.join(self.session_dir, new_session_name)
        os.makedirs(new_folder, exist_ok=True)
        
        new_history = []
        if evicted:
            if os.path.exists(self.notepad.raw_log_path):
                with open(self.notepad.raw_log_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        try:
                            data = json.loads(line)
                            t_idx = data.get('turn_index')
                            if t_idx and (turn_index - 2 <= t_idx <= turn_index):
                                new_history.append(data)
                        except: pass
        else:
            new_history = [t for t in self.history_B if t.get("turn_index") <= turn_index]
            
        with open(os.path.join(new_folder, "history.json"), 'w', encoding='utf-8') as f:
            json.dump(new_history, f, ensure_ascii=False, indent=2)
            
        from graph_notepad import GraphNotepad
        new_notepad = GraphNotepad(os.path.join(new_folder, "graph.json"), os.path.join(new_folder, "history_raw.jsonl"))
        new_notepad.graph = self.notepad.graph.copy()
        nodes_to_remove = [n for n, d in new_notepad.graph.nodes(data=True) if d.get('turn_index') and d['turn_index'] > turn_index]
        new_notepad.graph.remove_nodes_from(nodes_to_remove)
        new_notepad.save()
        
        if os.path.exists(self.notepad.raw_log_path):
            with open(self.notepad.raw_log_path, 'r', encoding='utf-8') as fin, open(new_notepad.raw_log_path, 'w', encoding='utf-8') as fout:
                for line in fin:
                    try:
                        if json.loads(line).get('turn_index') <= turn_index:
                            fout.write(line)
                    except: pass
                        
        if os.path.exists(self.eng_graph_file):
            shutil.copy(self.eng_graph_file, os.path.join(new_folder, "engineering.json"))
            
        self.switch_session(new_session_name)
        return f"[cyan][系统] 成功派生平行会话 '{new_session_name}' (Commit: {commit_hash[:7]})。{' (已从外存重载该区间上下文)' if evicted else ''}[/cyan]" """

    # Remove old rollback_to_turn
    content = re.sub(r'    def rollback_to_turn\(self, turn_index: int\):.*?return f"\[cyan\]\[系统\] 成功回滚到回合 \{turn_index\}.*?\[/cyan\]"', 
                     new_rollback, content, flags=re.DOTALL)
    
    # Remove old fork_session
    content = re.sub(r'    def fork_session\(self, turn_index: int, new_session_name: str\):.*?return f"\[cyan\]\[系统\] 成功派生新平行会话 .*?\[/cyan\]"', 
                     new_fork, content, flags=re.DOTALL)
                     
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

if __name__ == "__main__":
    patch_agent_advanced()
