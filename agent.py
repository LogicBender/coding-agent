import os
import json
import re
from llm_client import init_client, chat_completion
from tools import get_tools_schema, execute_tool
from graph_notepad import GraphNotepad
from rich.console import Console
from rich.markdown import Markdown
from rich.prompt import Confirm
from prompt_toolkit import PromptSession
from prompt_toolkit.styles import Style

console = Console()

input_session = PromptSession()
input_style = Style.from_dict({'prompt': 'ansired bold'})

class CodingAgent:
    def __init__(self, session_name="default"):
        self.client = init_client()
        self.tools = get_tools_schema()
        
        # [A] 绝对静态区
        self.system_prompt = (
            "你是一个名为 Coding Agent 的顶级程序员。你的任务是自主完成用户交代的编程需求。\n"
            "你有权读取文件、修改文件、执行本地 Shell 命令。\n"
            "\n"
            "【图引导的分级记忆机制 (Graph-guided Page Fault Memory)】\n"
            "为了防止上下文超载，本系统采用了基于图谱的分级记忆。你的输入最上方会始终提供一个 <system_memory_graph>。\n"
            "1. 状态为 [🟢 在内存] 的节点，其细节还在你的上文对话历史中，你可以直接查阅。\n"
            "2. 状态为 [🔴 已换出] 的节点，其详细日志已被清理，发生『缺页中断』。如果你必须依赖该节点的细节，必须立刻调用 expand_node 工具读取原文，否则切勿盲目猜测！\n"
            "3. 状态为 [🔗 指向 Node_X] 的节点，说明它的详细内容刚刚已经被调取，并存放在了 Node_X 的对话历史中。遇到这种情况，请直接去寻找 Node_X 附近的聊天记录，切勿重复调用工具！\n"
            "\n"
            "【强制结构化总结要求】\n"
            "在你决定【不调用任何工具，准备给用户最终回复】的那一次输出时，必须在回复内容的最末尾隐式加上一段 XML，用来总结本轮你做的所有事。系统会自动拦截这段 XML 用来后台建图，用户看不到：\n"
            "<graph_update>\n"
            "  <task>简述本次任务核心目标 (10-50字)</task>\n"
            "  <result>简述最终结果成功与否及原因</result>\n"
            "  <core_details>本次修改的关键细节、重要变量名、重要教训等 (30-100字)</core_details>\n"
            "  <edges>Node_1, Node_2 (写出你认为与本次任务相关联的历史节点ID，逗号分隔，无则留空)</edges>\n"
            "</graph_update>"
        )
        
        self.session_dir = ".agent_sessions"
        if not os.path.exists(self.session_dir):
            os.makedirs(self.session_dir, exist_ok=True)
            
        self.history_B = [] # 列表的列表，按 Turn 存储
        self.switch_session(session_name)

    @property
    def current_session_folder(self):
        return os.path.join(self.session_dir, self.session_name)

    @property
    def history_file(self):
        return os.path.join(self.current_session_folder, "history.json")
        
    @property
    def graph_file(self):
        return os.path.join(self.current_session_folder, "graph.json")
        
    @property
    def raw_log_file(self):
        return os.path.join(self.current_session_folder, "history_raw.jsonl")

    def switch_session(self, new_session_name):
        self.session_name = new_session_name
        if not os.path.exists(self.current_session_folder):
            os.makedirs(self.current_session_folder, exist_ok=True)
            
        self.notepad = GraphNotepad(self.graph_file, self.raw_log_file)
        self.load_history()

    def load_history(self):
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    self.history_B = json.load(f)
                console.print(f"[dim][系统] 已恢复会话 '{self.session_name}'，包含 {len(self.history_B)} 个历史操作回合。[/dim]")
            except Exception as e:
                console.print(f"[yellow][系统] 加载历史失败: {e}[/yellow]")
                self.history_B = []
        else:
            self.history_B = []

    def save_history(self):
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self.history_B, f, ensure_ascii=False, indent=2)
        except Exception as e:
            console.print(f"[red][系统] 保存历史记录失败: {e}[/red]")

    def run_task(self, user_prompt: str):
        console.print(f"\n[bold magenta][系统] 开始任务:[/bold magenta] {user_prompt}\n")
        
        # 3. 内存告急降级 (缺页中断机制)
        # 用字符长度估算 Token。当前先进模型支持 1M Token (约 300万~400万字符)。
        # 设定 MAX_CHARS 为 200 万字符 (约 500k Token，留足空间给大文件读取)。
        # 如果超出，一次性截断直到剩余 100 万字符，避免频繁触发换出
        MAX_CHARS = 2000000
        TARGET_CHARS = 1000000
        
        def get_history_length():
            return sum(len(str(turn["messages"])) for turn in self.history_B)
            
        if get_history_length() > MAX_CHARS:
            console.print(f"[yellow][缺页中断管理器] 上下文长度超限，开始批量换出早期历史记录...[/yellow]")
            # 至少保留最近的 1 个回合以防全部删空
            while len(self.history_B) > 1 and get_history_length() > TARGET_CHARS:
                evicted_turn = self.history_B.pop(0)
                node_id = evicted_turn.get("node_id")
                if node_id:
                    self.notepad.evict_node(node_id)
                    console.print(f"[dim]已将 {node_id} 的原始日志换出，在图谱中标记为 🔴 已换出。[/dim]")
        
        # [E] 当前回合
        turn_messages = [{"role": "user", "content": user_prompt}]
        turn_index = self.notepad.graph.number_of_nodes() + 1
        new_node_id = f"Node_{turn_index}"
        
        while True:
            try:
                # 动态组装本次 API 请求的 Context (极度命中 KV Cache)
                # [A] + [B]
                api_messages = [{"role": "system", "content": self.system_prompt}]
                for turn in self.history_B:
                    api_messages.extend(turn["messages"])
                
                # [C][D][E]
                dynamic_turn = list(turn_messages)
                first_msg = dynamic_turn[0].copy()
                graph_json_str = self.notepad.get_graph_json()
                first_msg["content"] = (
                    f"<system_memory_graph>\n{graph_json_str}\n</system_memory_graph>\n\n"
                    f"<current_instruction>\n{first_msg['content']}\n</current_instruction>"
                )
                dynamic_turn[0] = first_msg
                api_messages.extend(dynamic_turn)
                
                with console.status("[bold green][系统] Agent 正在思考...[/bold green]", spinner="dots"):
                    response_choice = chat_completion(
                        client=self.client, 
                        messages=api_messages, 
                        tools=self.tools
                    )
                
                response_msg = response_choice.message
                finish_reason = response_choice.finish_reason
                msg_dict = response_msg.model_dump(exclude_none=True)

                if response_msg.tool_calls:
                    turn_messages.append(msg_dict)
                    for tool_call in response_msg.tool_calls:
                        tool_name = tool_call.function.name
                        arguments = tool_call.function.arguments
                        
                        console.print(f"[bold cyan][系统] 决定调用工具:[/bold cyan] {tool_name}")
                        console.print(f"[dim]参数: {arguments}[/dim]")
                        
                        confirm = Confirm.ask("[bold yellow][系统] 允许执行此操作吗？[/bold yellow]")
                        if not confirm:
                            otherinfo = input_session.prompt('详细的拒绝理由: ', style=input_style)
                            tool_result = f"用户拒绝了执行该操作。补充说明: {otherinfo}"
                        else:
                            with console.status(f"[bold blue][系统] 正在执行 {tool_name}...[/bold blue]"):
                                tool_result = execute_tool(tool_name, arguments, notepad=self.notepad, current_node_id=new_node_id)

                        console.print(f"[bold green][系统] 工具执行结果:[/bold green]\n{tool_result}\n")
                        turn_messages.append({"role": "tool", "tool_call_id": tool_call.id, "content": tool_result})
                    continue
                    
                # 【断点续写核心逻辑】
                if finish_reason == 'length':
                    console.print("\n[bold yellow][系统警告] 模型输出达到长度上限被截断！正在自动发起断点续写...[/bold yellow]")
                    console.print(f"[dim]已接收到的前半部分:\n{response_msg.content}[/dim]\n")
                    
                    turn_messages.append(msg_dict)
                    continue_msg = {
                        "role": "user",
                        "content": "⚠️ 系统提示：你的输出因达到最大 Token 上限被截断。请不要重复上文，不要说废话，请严格从上一句话断掉的最后一个字符开始继续输出剩余内容。"
                    }
                    turn_messages.append(continue_msg)
                    continue

                # 最终回复阶段，解析 XML
                reply_text = response_msg.content
                match = re.search(r'<graph_update>(.*?)</graph_update>', reply_text, re.DOTALL)
                
                if match:
                    graph_xml = match.group(1)
                    # 从展示给用户的文本中剔除 XML
                    clean_reply = reply_text.replace(match.group(0), "").strip()
                    
                    task = re.search(r'<task>(.*?)</task>', graph_xml, re.DOTALL)
                    res = re.search(r'<result>(.*?)</result>', graph_xml, re.DOTALL)
                    det = re.search(r'<core_details>(.*?)</core_details>', graph_xml, re.DOTALL)
                    edg = re.search(r'<edges>(.*?)</edges>', graph_xml, re.DOTALL)
                    
                    self.notepad.add_context_node(
                        node_id=new_node_id,
                        task=task.group(1).strip() if task else "未命名任务",
                        result=res.group(1).strip() if res else "",
                        core_details=det.group(1).strip() if det else "",
                        raw_content=turn_messages + [{"role": "assistant", "content": clean_reply}],
                        edges=[e.strip() for e in edg.group(1).split(',')] if edg and edg.group(1).strip() else [],
                        turn_index=turn_index
                    )
                    
                    msg_dict["content"] = clean_reply
                    console.print(f"\n[bold green][系统] 后台已静默生成节点 {new_node_id} 加入图谱，日志指针指向外存。[/bold green]")
                else:
                    # 模型忘记输出标签
                    clean_reply = reply_text
                    msg_dict["content"] = clean_reply
                    self.notepad.add_context_node(
                        node_id=new_node_id,
                        task=f"常规对话", result="", core_details=clean_reply[:50], 
                        raw_content=turn_messages + [msg_dict], edges=[],
                        turn_index=turn_index
                    )
                    
                turn_messages.append(msg_dict)
                console.print("\n[bold magenta][Agent]:[/bold magenta]")
                console.print(Markdown(clean_reply))
                
                # 持久化本回合
                self.history_B.append({
                    "node_id": new_node_id,
                    "messages": turn_messages
                })
                self.save_history()
                break
                
            except Exception as e:
                console.print(f"\n[bold red][系统] 执行期间发生异常:[/bold red] {e}")
                console.print("[yellow][系统] 提示: 异常已捕获，你可以修改代码或重新尝试。[/yellow]")
                break

if __name__ == "__main__":
    agent = CodingAgent()
    agent.run_task("打印一句 hello 测试。")