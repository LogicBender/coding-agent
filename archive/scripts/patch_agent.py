import os
import json
import subprocess
import shutil

def patch_agent_file():
    filepath = "/mnt/d/project/coding/agent.py"
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    new_methods = """
    def rollback_to_turn(self, turn_index: int):
        target_turn = next((t for t in self.history_B if t.get("turn_index") == turn_index), None)
        if not target_turn:
            return "[red][Error] 找不到指定的回合。[/red]"
        
        commit_hash = target_turn.get("commit_hash")
        if commit_hash:
            try:
                subprocess.check_call(["git", "reset", "--hard", commit_hash], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception as e:
                return f"[red][Error] Git 回滚失败: {e}[/red]"
        else:
            return "[yellow][Warn] 该回合没有记录 Git Hash，无法回滚代码，仅能回滚上下文。[/yellow]"
            
        # 截断历史
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
                
        return f"[cyan][系统] 成功回滚到回合 {turn_index} (Commit: {commit_hash[:7] if commit_hash else 'N/A'})[/cyan]"

    def fork_session(self, turn_index: int, new_session_name: str):
        target_turn = next((t for t in self.history_B if t.get("turn_index") == turn_index), None)
        if not target_turn:
            return "[red][Error] 找不到指定的回合。[/red]"
            
        commit_hash = target_turn.get("commit_hash")
        if commit_hash:
            try:
                subprocess.check_call(["git", "checkout", "-b", new_session_name, commit_hash], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception as e:
                return f"[red][Error] Git 创建分支失败 (可能分支已存在或有未提交更改): {e}[/red]"
        else:
            return "[red][Error] 该回合没有记录 Git Hash，无法创建精确分支。[/red]"
            
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
        return f"[cyan][系统] 成功派生新平行会话 '{new_session_name}'，已切入对应 Git 分支。[/cyan]"
"""
    
    # 插入在 erase_turn 方法后面
    if "def rollback_to_turn(" not in content:
        content = content.replace("def erase_turn(self, turn_index: int):", new_methods + "\n    def erase_turn(self, turn_index: int):")
        
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

if __name__ == "__main__":
    patch_agent_file()
