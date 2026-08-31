import sys
import os
import shutil
from rich.console import Console
from agent import CodingAgent
from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.styles import Style

console = Console()

def get_prompt():
    """获取带顶部边框的 Prompt"""
    width = shutil.get_terminal_size().columns
    line = "─" * width
    return HTML(f"\n\n<ansiblue>{line}</ansiblue>\n<ansigreen><b>You: </b></ansigreen>")

def bottom_toolbar():
    """获取带底部边框和模型信息的 Toolbar"""
    width = shutil.get_terminal_size().columns
    line = "─" * width
    model_name = "deepseek-v4-pro"
    model_text = f"Model: {model_name}"
    # 计算空格以实现右对齐
    spaces = " " * max(0, width - len(model_text) - 1)
    return HTML(f"<ansiblue>{line}</ansiblue>\n{spaces}<ansigray>{model_text}</ansigray>")

def main():
    console.print("[bold blue][系统] 欢迎使用 Coding Agent (Powered by DeepSeek)![/bold blue]")
    console.print("[dim]可用命令: /new <name> (开启新对话), /resume [name] (切换或查看对话), /history, /del <index>, /clear, /exit[/dim]\n")
    
    custom_style = Style.from_dict({
        'bottom-toolbar': 'noreverse', 
    })
    agent = CodingAgent()
    session = PromptSession()
    
    while True:
        try:
            # 引入动态 Prompt 和 Bottom Toolbar，让输入区永远在框内
            user_input = session.prompt(message=get_prompt, bottom_toolbar=bottom_toolbar, style=custom_style)
            
            if user_input.lower() in ['/exit', '/quit', 'exit', 'quit']:
                console.print("[bold yellow][系统] 再见！[/bold yellow]")
                break
            if not user_input.strip():
                continue
                
            # --- 拦截本地交互命令 ---
            if user_input.startswith('/'):
                cmd = user_input.split()
                
                # 新增 /new 开启全新对话
                if cmd[0] == '/new':
                    if len(cmd) == 1:
                        console.print("[red][系统] 用法: /new <session_name>[/red]")
                    else:
                        session_name = cmd[1]
                        target_dir = os.path.join(agent.session_dir, session_name)
                        if os.path.exists(target_dir):
                            console.print(f"[yellow][系统] 会话 '{session_name}' 已存在！如果你想恢复它，请使用 /resume {session_name}[/yellow]")
                        else:
                            agent.switch_session(session_name)
                            console.print(f"[green][系统] 已开启并切换到全新会话: {session_name}[/green]")
                    continue

                # 处理 /resume 命令
                elif cmd[0] == '/resume':
                    if len(cmd) == 1:
                        # 查看已有 sessions（现在是遍历文件夹）
                        if not os.path.exists(agent.session_dir):
                            sessions = []
                        else:
                            sessions = [d for d in os.listdir(agent.session_dir) if os.path.isdir(os.path.join(agent.session_dir, d))]
                            
                        if not sessions:
                            console.print("[cyan][系统] 当前没有其他的对话记录。[/cyan]")
                        else:
                            console.print("[cyan][系统] 可用对话记录:[/cyan] " + ", ".join(sessions))
                    else:
                        # 切换到指定的 session
                        session_name = cmd[1]
                        target_dir = os.path.join(agent.session_dir, session_name)
                        if not os.path.exists(target_dir):
                            console.print(f"[red][系统] 找不到会话 '{session_name}'，如果想创建，请使用 /new {session_name}[/red]")
                        else:
                            agent.switch_session(session_name)
                            console.print(f"[green][系统] 已切换到对话: {session_name}[/green]")
                    continue

                elif cmd[0] == '/history':
                    console.print(f"\n[bold cyan][系统] 当前工作区历史 (Session: {agent.session_name}):[/bold cyan]")
                    for i, turn in enumerate(agent.history_B):
                        node_id = turn.get("node_id", "未知节点")
                        console.print(f"\n[bold magenta]--- 第 {i} 回合 ({node_id}) ---[/bold magenta]")
                        for msg in turn.get("messages", []):
                            role = msg.get("role", "unknown")
                            content = str(msg.get("content", ""))
                            if msg.get("tool_calls"):
                                content += f" [调用了 {len(msg['tool_calls'])} 个工具]"
                            short_content = content[:80].replace('\n', ' ') + ('...' if len(content)>80 else '')
                            console.print(f"[{role.upper()}]: {short_content}")
                    continue
                    
                elif cmd[0] == '/del' and len(cmd) > 1:
                    try:
                        idx = int(cmd[1])
                        if 0 <= idx < len(agent.history_B):
                            deleted_turn = agent.history_B.pop(idx)
                            agent.save_history()
                            node_id = deleted_turn.get("node_id")
                            if node_id:
                                agent.notepad.evict_node(node_id)
                            console.print(f"[green][系统] 已删除第 {idx} 回合。该回合对应的节点 {node_id} 已在图谱中标记为换出。[/green]")
                        else:
                            console.print("[red][系统] 无效的索引号。请先使用 /history 查看有效的回合索引。[/red]")
                    except ValueError:
                        console.print("[red][系统] 用法: /del <数字>[/red]")
                    continue
                    
                # 撤销改动：回到上一个 git commit
                elif cmd[0] == '/rollback':
                    import subprocess
                    res = subprocess.run("git reset --hard HEAD~1", shell=True, capture_output=True, text=True)
                    if res.returncode == 0:
                        console.print("[green][系统] ✅ 文件状态已回滚到上一次 Agent 动作前！[/green]")
                        console.print("[yellow][系统] 提示: 文件已恢复，但大模型上下文未改变。建议配合 /history 和 /del 删掉最后几轮错误的对话日志。[/yellow]")
                    else:
                        console.print(f"[red][系统] ❌ 回滚失败，可能是当前没有足够多的 Commit 记录:\n{res.stderr}[/red]")
                    continue
                    
                elif cmd[0] == '/clear':
                    agent.history_B = []
                    agent.save_history()
                    console.print("[green][系统] L1 Cache (活跃上下文) 已全部清空，Agent 记忆已重置！\n提示: 图谱与原始日志依然安全保存在外存中。[/green]")
                    continue
                    
                else:
                    console.print("[yellow][系统] 未知命令。可用: /new <name>, /resume [name], /history, /del <index>, /clear, /exit[/yellow]")
                    continue
                
            # 正常派发任务
            agent.run_task(user_input)
            
        except KeyboardInterrupt:
            console.print("\n[bold yellow][系统] 已手动取消。[/bold yellow]")
            continue
        except EOFError:
            console.print("\n[bold yellow][系统] 再见！[/bold yellow]")
            break

if __name__ == "__main__":
    main()
