import os

replacements = {
    "❌": "[Error]", 
    "✅": "[Success]", 
    "⚠️": "[Warn]",
    "[🟢 在内存]": "[In_Memory]", 
    "[🔴 已换出]": "[Evicted]", 
    "[🔗 指向": "[Pointer ->",
    "🎯 工程任务网络": "Engineering_Task_Network", 
    "🧠 近期上下文踪迹": "Context_Memory",
    "✅ 已完成": "Completed", 
    "⏳ 正在攻坚": "In_Progress", 
    "⏳ 待处理": "Pending",
    "🎯": "", "🧠": "", "⏳": "", "🔴": "", "🟢": "", "🔗": "",
    "[bold magenta][Agent]:[/bold magenta]": "[cyan][Agent]:[/cyan]",
    "[bold green]": "[cyan]",
    "[/bold green]": "[/cyan]",
    "[bold cyan]": "[cyan]",
    "[/bold cyan]": "[/cyan]"
}

files_to_process = [
    "graph_notepad.py", 
    "engineering_graph.py", 
    "dynamic_tools_manager.py", 
    "tools.py",
    "agent.py",
    "main.py"
]

for filepath in files_to_process:
    full_path = os.path.join("/mnt/d/project/coding", filepath)
    if os.path.exists(full_path):
        with open(full_path, 'r', encoding='utf-8') as f:
            content = f.read()
        for old, new in replacements.items():
            content = content.replace(old, new)
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(content)
print("Emoji and color standardization complete.")
