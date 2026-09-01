import os
from core.agent import CodingAgent, console
from prompt_toolkit import PromptSession
from prompt_toolkit.styles import Style
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.formatted_text import HTML

def main():
    console.print("[cyan][系统] 欢迎使用 Coding Agent![/cyan]")
    console.print("[dim]可用命令: /help, /new <name>, /resume, /history, /del <index>, /erase <index>, /clear, /model, /context, /type, /exit[/dim]\n")
    
    agent = CodingAgent()
    
    kb = KeyBindings()
    @kb.add('escape', 'enter')
    def _(event):
        event.current_buffer.insert_text('\n')
        
    @kb.add('enter')
    def _(event):
        event.current_buffer.validate_and_handle()

    style = Style.from_dict({
        'prompt': 'ansicyan bold',
        'bottom-toolbar': 'noreverse'
    })
    
    import shutil
    def bottom_toolbar():
        mode = "Auto-Accept" if agent.auto_accept else "Normal"
        model = agent.model
        term_width = shutil.get_terminal_size().columns
        left = f" {mode}"
        right = f"Model: {model}"
        space = term_width - len(left) - len(right)
        if space < 0: space = 1
        return HTML(f"<b><ansiblue>{'─' * term_width}</ansiblue></b>\n" + left + (" " * space) + right)

    session = PromptSession(style=style, key_bindings=kb, multiline=True, bottom_toolbar=bottom_toolbar)

    while True:
        try:
            term_width = shutil.get_terminal_size().columns
            console.print(f"\n\n[bold blue]{'─' * term_width}[/bold blue]")
            # console.print("[dim](提示: Enter 发送, Shift+Enter 换行)[/dim]")
            user_input = session.prompt('> ').strip()
            # console.print(f"[bold blue]{'─' * term_width}[/bold blue]\n")
            
            if not user_input:
                continue
                
            if user_input.startswith('/'):
                cmd_parts = user_input.split(' ', 1)
                cmd = cmd_parts[0].lower()
                arg = cmd_parts[1].strip() if len(cmd_parts) > 1 else ""
                
                if cmd == '/exit':
                    break
                elif cmd == '/help':
                    console.print("[cyan]可用命令列表:[/cyan]")
                    console.print("/new <name>         - 创建新会话")
                    console.print("/resume \\[name]      - 切换或查看会话")
                    console.print("/history            - 查看当前会话历史回合")
                    console.print("/del <idx>          - 浅度删除（仅从当前缓存窗口剔除，外存和图谱保留）")
                    console.print("/erase <idx>        - 深度擦除（从内存、图谱、外存彻底抹除该回合痕迹）")
                    console.print("/fork <idx> <name>  - 派生分支（从指定回合 Git 分叉并拉起平行会话）")
                    console.print("/rollback <idx>     - 代码回档（代码和上下文均回退至某历史回合）")
                    console.print("/clear              - 清空当前活动缓存")
                    console.print("/model \\[name]       - 查看或切换大模型名称")
                    console.print("/context            - 打印当前缓存字符占用量及阈值上限")
                    console.print("/type               - 开启/关闭自动审查模式 (跳过非高危工具的人工确认)")
                    console.print("/exit               - 退出系统")
                elif cmd == '/new':
                    if not arg:
                        console.print("[red][Error] 请指定会话名称。[/red]")
                        continue
                    agent.switch_session(arg)
                    console.print(f"[cyan][系统] 已切换到新会话 '{arg}'[/cyan]")
                elif cmd == '/resume':
                    sessions = []
                    if os.path.exists(agent.session_dir):
                        sessions = [d for d in os.listdir(agent.session_dir) if os.path.isdir(os.path.join(agent.session_dir, d))]
                    if not arg:
                        console.print(f"[cyan][系统] 可用会话记录:[/cyan] {', '.join(sessions)}")
                    else:
                        if arg in sessions:
                            agent.switch_session(arg)
                            console.print(f"[cyan][系统] 已切换到会话 '{arg}'[/cyan]")
                        else:
                            console.print(f"[red][Error] 找不到会话 '{arg}'[/red]")
                elif cmd == '/history':
                    if not agent.history_B:
                        console.print("[dim]历史记录为空。[/dim]")
                        continue
                    for turn in agent.history_B:
                        node_id = turn.get("node_id", "Unknown")
                        idx = turn.get("turn_index", "?")
                        commit_hash = turn.get("commit_hash", "")
                        if commit_hash:
                            console.print(f"\n\n[cyan]=== Turn {idx} ({node_id}) [Commit: {commit_hash[:7]}] ===[/cyan]")
                        else:
                            console.print(f"\n\n[cyan]=== Turn {idx} ({node_id}) ===[/cyan]")
                        for msg in turn.get("messages", []):
                            role = msg.get("role")
                            content = msg.get("content", "")
                            if role == "tool":
                                content = f"[工具执行结果: {len(content)} chars]"
                            elif len(content) > 200:
                                content = content[:200] + "... [截断]"
                            console.print(f"[dim]{role}:[/dim] {content}")
                elif cmd == '/del':
                    if arg.isdigit():
                        idx = int(arg)
                        agent.history_B = [t for t in agent.history_B if t.get("turn_index") != idx]
                        agent.save_history()
                        console.print(f"[cyan][系统] 浅度删除: 已将回合 {idx} 移出当前缓存。[/cyan]")
                    else:
                        console.print("[red][Error] 请提供有效的数字索引。[/red]")
                
                elif cmd == '/fork':
                    if len(cmd_parts) < 2:
                        console.print("[red][Error] 用法: /fork <turn_index> <new_session_name>[/red]")
                        continue
                    args = arg.split(' ')
                    if len(args) < 2 or not args[0].isdigit():
                        console.print("[red][Error] 用法: /fork <turn_index> <new_session_name>[/red]")
                        continue
                    idx = int(args[0])
                    new_name = args[1]
                    res = agent.fork_session(idx, new_name)
                    console.print(res)
                elif cmd == '/rollback':
                    if not arg.isdigit():
                        console.print("[red][Error] 请指定要回滚到的有效数字索引。用法: /rollback <turn_index>[/red]")
                        continue
                    idx = int(arg)
                    res = agent.rollback_to_turn(idx)
                    console.print(res)
    
                elif cmd == '/erase':
                    if arg.isdigit():
                        idx = int(arg)
                        agent.erase_turn(idx)
                    else:
                        console.print("[red][Error] 请提供有效的数字索引。[/red]")
                elif cmd == '/clear':
                    agent.history_B = []
                    agent.save_history()
                    console.print("[cyan][系统] 活动缓存已清空（外存与图谱均安全保留）。[/cyan]")
                elif cmd == '/model':
                    if arg:
                        agent.model = arg
                        console.print(f"[cyan][系统] 模型已强制切换为: {agent.model}[/cyan]")
                    else:
                        console.print(f"[cyan][系统] 正在向远端 API 请求可用模型列表...[/cyan]")
                        try:
                            models_response = agent.client.models.list()
                            available_models = sorted([m.id for m in models_response.data])
                            console.print(f"[cyan][系统] 当前生效模型: {agent.model}[/cyan]")
                            console.print(f"[cyan][系统] 远端端点支持的模型列表:[/cyan]")
                            for m in available_models:
                                if m == agent.model:
                                    console.print(f"  * [green]{m}[/green] (当前)")
                                else:
                                    console.print(f"  - {m}")
                            console.print("[dim]使用 /model <模型名> 进行切换[/dim]")
                        except Exception as e:
                            console.print(f"[cyan][系统] 当前生效模型: {agent.model}[/cyan]")
                            console.print(f"[red][Error] 无法拉取远端模型列表: {e}[/red]")
                elif cmd == '/context':
                    char_len = sum(len(str(t.get("messages", ""))) for t in agent.history_B)
                    console.print(f"[cyan][系统] 当前上下文使用量:[/cyan] {char_len} 字符 (阈值 1,000,000 | 上限 2,000,000)")
                elif cmd == '/type':
                    agent.auto_accept = not agent.auto_accept
                    status = "开启" if agent.auto_accept else "关闭"
                    console.print(f"[cyan][系统] 自动审查模式已 {status}！[/cyan]")
                else:
                    console.print("[red][Error] 未知命令，请输入 /help 查看支持的命令。[/red]")
                continue
                
            agent.run_task(user_input)

        except KeyboardInterrupt:
            continue
        except EOFError:
            break
        except Exception as e:
            console.print(f"[red][错误] 主循环发生异常: {str(e)}[/red]")

if __name__ == "__main__":
    main()
