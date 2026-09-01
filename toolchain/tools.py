import os
import json
import subprocess
import re

def strip_ansi(text: str) -> str:
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)

def auto_git_backup(reason: str):
    try:
        res = subprocess.run("git rev-parse --is-inside-work-tree", shell=True, capture_output=True, text=True)
        if res.returncode != 0:
            subprocess.run("git init", shell=True, capture_output=True)
        res = subprocess.run("git status --porcelain", shell=True, capture_output=True, text=True)
        if res.stdout.strip():
            subprocess.run("git add .", shell=True, capture_output=True)
            safe_reason = reason.replace('"', "'")
            subprocess.run(f'git commit -m "Auto backup: {safe_reason}"', shell=True, capture_output=True)
    except Exception:
        pass

def read_file(filepath: str) -> str:
    try:
        if not os.path.isabs(filepath):
            filepath = os.path.abspath(filepath)
        if not os.path.exists(filepath):
            return f"[Error] 错误: 文件不存在 {filepath}"
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        return f"[Error] 错误: 读取文件失败 {filepath}\n详细信息: {str(e)}"

def write_file(filepath: str, content: str) -> str:
    auto_git_backup(f"before writing {filepath}")
    try:
        if not os.path.isabs(filepath):
            filepath = os.path.abspath(filepath)
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return f"[Success] 成功: 文件已全量写入到 {filepath}"
    except Exception as e:
        return f"[Error] 错误: 写入文件失败 {filepath}\n详细信息: {str(e)}"

def edit_file(filepath: str, target_content: str, replacement_content: str) -> str:
    auto_git_backup(f"before editing {filepath}")
    try:
        if not os.path.isabs(filepath):
            filepath = os.path.abspath(filepath)
        if not os.path.exists(filepath):
            return f"[Error] 错误: 文件不存在 {filepath}"
        
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            
        count = content.count(target_content)
        if count == 0:
            return "[Error] 错误: 未找到匹配内容。请检查缩进、空格或换行符。"
        elif count > 1:
            return f"[Error] 错误: 找到 {count} 处匹配。请提供更多上下文行。"
            
        new_content = content.replace(target_content, replacement_content)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        return f"[Success] 成功: 已精准局部替换 {filepath} 中的代码块。"
    except Exception as e:
        return f"[Error] 错误: 局部修改文件失败 {filepath}\n详细信息: {str(e)}"

def run_command(command: str) -> str:
    auto_git_backup(f"before running command: {command}")
    try:
        print(f"\n[系统提示] 正在后台执行: {command}")
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=120
        )
        output = result.stdout + result.stderr
        output = strip_ansi(output)
        if len(output) > 2000:
            omitted = len(output) - 2000
            output = output[:500] + f"\n\n... [警告：输出过长，已省略中间 {omitted} 个字符] ...\n\n" + output[-1500:]
            
        if result.returncode != 0:
            return f"[Warn] 命令执行完成，但返回了错误码 {result.returncode}:\n{output}"
        return f"[Success] 命令执行成功:\n{output}" if output.strip() else "[Success] 命令执行成功，无终端输出。"
    except subprocess.TimeoutExpired:
        return "[Error] 错误: 命令执行超时 (超过 120 秒)。"
    except Exception as e:
        return f"[Error] 错误: 无法执行命令。\n详细信息: {str(e)}"

from toolchain.dynamic_tools_manager import DynamicToolManager

# 全局初始化动态工具管理器
dyn_manager = DynamicToolManager()

def get_tools_schema() -> list:
    base_tools = [
        {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "读取指定路径的本地文件内容",
                "parameters": {
                    "type": "object",
                    "properties": {"filepath": {"type": "string"}},
                    "required": ["filepath"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "write_file",
                "description": "全量覆盖写入新文件。注意：如果只是修改现有文件的一小部分，请优先使用 edit_file，以节约 Token 并减少错误。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "filepath": {"type": "string"},
                        "content": {"type": "string"}
                    },
                    "required": ["filepath", "content"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "edit_file",
                "description": "局部替换文件的某一段代码。非常适合精准修改文件中的一个函数或几行代码。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "filepath": {"type": "string"},
                        "target_content": {
                            "type": "string", 
                            "description": "必须要被替换的原始代码。必须与源文件一字不差。"
                        },
                        "replacement_content": {
                            "type": "string",
                            "description": "修改后的新代码片段，将完整替换掉 target_content。"
                        }
                    },
                    "required": ["filepath", "target_content", "replacement_content"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "run_command",
                "description": "执行 Shell 命令。可以运行代码、安装依赖、查看目录结构等。输出过长会自动截断。",
                "parameters": {
                    "type": "object",
                    "properties": {"command": {"type": "string"}},
                    "required": ["command"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "expand_node",
                "description": "缺页中断核心机制：当系统上下文图谱（system_memory_graph）中提示某个节点的状态为 [Evicted] 时，你可以调用此工具传入节点 ID，拉取该节点当时被换出的完整原文日志。如果你发现需要理解之前的上下文，务必首先调用此工具。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "node_id": {"type": "string", "description": "需要展开读取的节点 ID，例如 'Node_1'"}
                    },
                    "required": ["node_id"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "create_tool",
                "description": "当你发现某些操作需要大量重复使用（如正则爬取、特定 API 抓包、复杂的数学计算）或者需要原生 Python 支持时，你可以直接编写工具代码并永久热重载到自己的武器库中。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "tool_name": {"type": "string", "description": "工具的英文函数名，例如 fetch_html"},
                        "description": {"type": "string", "description": "给大模型自己看的工具详细用途描述"},
                        "parameters_schema_json": {"type": "string", "description": "符合 OpenAPI 规范的 Parameters 部分的 JSON 字符串表示。"},
                        "python_code": {"type": "string", "description": "完整且可独立运行的 Python 代码。必须包含与 tool_name 同名的函数，并且返回值必须是可以通过 str() 打印的。可以导入常见的标准库。"}
                    },
                    "required": ["tool_name", "description", "parameters_schema_json", "python_code"]
                }
            }
        }
    ]
    # 拼接原生基础工具与大模型自己创造的衍生工具
    return base_tools + dyn_manager.get_schemas()

def execute_tool(tool_name: str, arguments: str, notepad=None, current_node_id=None) -> str:
    try:
        args_dict = json.loads(arguments)
    except json.JSONDecodeError:
        return "[Error] 错误: 工具参数解析失败，无法解析为 JSON 格式。"

    # 1. 基础硬编码工具路由
    if tool_name == "read_file":
        return read_file(args_dict.get("filepath"))
    elif tool_name == "write_file":
        return write_file(args_dict.get("filepath"), args_dict.get("content"))
    elif tool_name == "edit_file":
        return edit_file(args_dict.get("filepath"), args_dict.get("target_content"), args_dict.get("replacement_content"))
    elif tool_name == "run_command":
        return run_command(args_dict.get("command"))
    elif tool_name == "expand_node":
        return notepad.expand_node(args_dict.get("node_id"), current_node_id) if notepad else "[Error] 错误: 图引擎未初始化"
    elif tool_name == "create_tool":
        return dyn_manager.create_tool(
            args_dict.get("tool_name"),
            args_dict.get("description"),
            args_dict.get("parameters_schema_json"),
            args_dict.get("python_code")
        )
    # 2. 动态衍生工具路由 fallback
    else:
        return dyn_manager.execute(tool_name, args_dict)
