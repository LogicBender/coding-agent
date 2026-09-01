import os
import re

def patch():
    filepath = "/mnt/d/project/coding/agent.py"
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # 1. 注入 Git Init 到 __init__
    git_init_code = """
        self.auto_accept = False
        
        import subprocess
        if not os.path.exists(".git"):
            try:
                subprocess.check_call(["git", "init"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                subprocess.check_call(["git", "commit", "--allow-empty", "-m", "Initial commit"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception: pass
            
        self.switch_session(session_name)"""
    content = content.replace("self.auto_accept = False\n        self.switch_session(session_name)", git_init_code)

    # 2. 修改 rollback_to_turn
    rollback_old = """    def rollback_to_turn(self, turn_index: int):
        target_turn = next((t for t in self.history_B if t.get("turn_index") == turn_index), None)
        if not target_turn:
            return "[red][Error] 找不到指定的回合。[/red]"
        
        commit_hash = target_turn.get("commit_hash")"""
    
    rollback_new = """    def rollback_to_turn(self, turn_index: int):
        target_turn = next((t for t in self.history_B if t.get("turn_index") == turn_index), None)
        commit_hash = None
        if target_turn:
            commit_hash = target_turn.get("commit_hash")
        else:
            # 尝试从图谱中寻找被换出的节点
            node_id = f"Node_{turn_index}"
            if self.notepad.graph.has_node(node_id):
                commit_hash = self.notepad.graph.nodes[node_id].get("commit_hash")
        
        if not commit_hash:
            return f"[red][Error] 找不到回合 {turn_index} 的 Git Hash 记录，无法回滚。[/red]\"\"\"
"""
    # Just replace the whole method body cleanly
    content = re.sub(r'    def rollback_to_turn\(self, turn_index: int\):.*?return f"\[cyan\]\[系统\] 成功回滚到回合 \{turn_index\}.*?\[/cyan\]"', 
                     """    def rollback_to_turn(self, turn_index: int):
        target_turn = next((t for t in self.history_B if t.get("turn_index") == turn_index), None)
        commit_hash = None
        if target_turn:
            commit_hash = target_turn.get("commit_hash")
        else:
            node_id = f"Node_{turn_index}"
            if self.notepad.graph.has_node(node_id):
                commit_hash = self.notepad.graph.nodes[node_id].get("commit_hash")
                
        if not commit_hash:
            return f"[red][Error] 找不到回合 {turn_index} 的 Git Hash 记录。[/red]"
            
        import subprocess
        try:
            subprocess.check_call(["git", "reset", "--hard", commit_hash], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            return f"[red][Error] Git 回滚失败: {e}[/red]"
            
        # 截断历史 (全部丢弃大于 turn_index 的，如果 turn_index 被换出，那 history_B 就会被完全清空)
        self.history_B = [t for t in self.history_B if t.get("turn_index") <= turn_index]
        self.save_history()
        
        # 截断图谱
        nodes_to_remove = [n for n, d in self.notepad.graph.nodes(data=True) if d.get('turn_index') and d['turn_index'] > turn_index]
        self.notepad.graph.remove_nodes_from(nodes_to_remove)
        self.notepad.save()
        
        import json, os
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
                
        return f"[cyan][系统] 成功回滚到回合 {turn_index} (Commit: {commit_hash[:7]})[/cyan]" """, content, flags=re.DOTALL)


    # 3. 修改 fork_session
    content = re.sub(r'    def fork_session\(self, turn_index: int, new_session_name: str\):.*?return f"\[cyan\]\[系统\] 成功派生新平行会话.*?\[/cyan\]"', 
                     """    def fork_session(self, turn_index: int, new_session_name: str):
        target_turn = next((t for t in self.history_B if t.get("turn_index") == turn_index), None)
        commit_hash = None
        if target_turn:
            commit_hash = target_turn.get("commit_hash")
        else:
            node_id = f"Node_{turn_index}"
            if self.notepad.graph.has_node(node_id):
                commit_hash = self.notepad.graph.nodes[node_id].get("commit_hash")
                
        if not commit_hash:
            return f"[red][Error] 找不到回合 {turn_index} 的 Git Hash 记录。[/red]"
            
        import subprocess
        try:
            subprocess.check_call(["git", "checkout", "-b", new_session_name, commit_hash], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            return f"[red][Error] Git 创建分支失败 (可能分支已存在或有未提交更改): {e}[/red]"
            
        import os, json, shutil
        new_folder = os.path.join(self.session_dir, new_session_name)
        os.makedirs(new_folder, exist_ok=True)
        
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
        return f"[cyan][系统] 成功派生新平行会话 '{new_session_name}'，已切入对应 Git 分支。[/cyan]" """, content, flags=re.DOTALL)


    # 4. 修改 run_task 中 git 的顺序
    # 截取 reply_text 解析部分
    # We will replace the whole parsing block carefully.
    
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

if __name__ == "__main__":
    patch()
