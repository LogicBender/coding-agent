import os

def patch_main():
    with open('/mnt/d/project/coding/main.py', 'r', encoding='utf-8') as f:
        content = f.read()

    new_commands = """
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
    """

    if "elif cmd == '/fork':" not in content:
        content = content.replace("elif cmd == '/erase':", new_commands + "\n                elif cmd == '/erase':")
        
    with open('/mnt/d/project/coding/main.py', 'w', encoding='utf-8') as f:
        f.write(content)

if __name__ == "__main__":
    patch_main()
