import os
import json
import re
from llm_client import init_client, chat_completion
from tools import get_tools_schema, execute_tool
from graph_notepad import GraphNotepad
from engineering_graph import EngineeringGraph
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
            "【全景双图引导机制】\n"
            "你拥有两个维度的导航图，均会在 <system_memory_graph> 中展示给你：\n"
            "1. 🎯 工程任务网络 (Task Network): 这是项目的宏观目标、依赖拓扑与文件映射。你需要根据它来明确自己的定位。\n"
            "2. 🧠 近期上下文踪迹 (MMU Cache): 这是你最近的思考与动作流水账。状态为 [🔴 已换出] 的节点代表日志已清理，如需查阅必须调用 expand_node 工具。\n"
            "状态为 [🔗 指向 Node_X] 表示详情在 Node_X 的日志中，请直接查阅最近历史，切勿重复调用工具！\n"
            "\n"
            "【强制结构化总结与滚动规划】\n"
            "在你决定【不调用任何工具，准备给用户最终回复】的那一次输出时，必须在回复末尾隐式加上两段 XML。\n"
            "第一段用于更新你的 MMU 上下文轨迹：\n"
            "<graph_update>\n"
            "  <task>简述本回合动作 (10-50字)</task>\n"
            "  <result>成功或失败</result>\n"
            "  <core_details>关键细节与教训 (30-100字)</core_details>\n"
            "  <edges>Node_1, Node_2 (关联的过去 Node ID，无则留空)</edges>\n"
            "</graph_update>\n"
            "\n"
            "第二段用于动态更新任务网络 (2-Hop 滚动规划)，你可以创建新任务、更新旧任务状态、或者映射刚修改的文件：\n"
            "<plan_network>\n"
            "  <goals>\n"
            "    <goal id=\"Task_1\" status=\"✅ 已完成\" desc=\"描述\"></goal>\n"
            "    <goal id=\"Task_2\" status=\"⏳ 正在攻坚\" desc=\"描述\"></goal>\n"
            "  </goals>\n"
            "  <dependencies>\n"
            "    <depends from=\"Task_2\" on=\"Task_1\" />\n"
            "  </dependencies>\n"
            "  <files>\n"
            "    <file task=\"Task_1\" path=\"src/main.py\" />\n"
            "  </files>\n"
            "</plan_network>"
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
        
    @property
    def eng_graph_file(self):
        return os.path.join(self.current_session_folder, "engineering.json")

    def switch_session(self, new_session_name):
        self.session_name = new_session_name
        if not os.path.exists(self.current_session_folder):
            os.makedirs(self.current_session_folder, exist_ok=True)
            
        self.notepad = GraphNotepad(self.graph_file, self.raw_log_file)
        self.eng_graph = EngineeringGraph(self.eng_graph_file)
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
                
                # 融合两层图谱
                eng_md = self.eng_graph.get_markdown_view()
                mmu_json = self.notepad.get_graph_json()
                
                first_msg["content"] = (
                    f"<system_memory_graph>\n"
                    f"=== 🎯 工程任务网络 ===\n{eng_md}\n\n"
                    f"=== 🧠 近期上下文踪迹 ===\n{mmu_json}\n"
                    f"</system_memory_graph>\n\n"
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
                clean_reply = reply_text
                
                # 1. 解析 MMU 轨迹
                match_mmu = re.search(r'<graph_update>(.*?)</graph_update>', reply_text, re.DOTALL)
                if match_mmu:
                    clean_reply = clean_reply.replace(match_mmu.group(0), "").strip()
                    graph_xml = match_mmu.group(1)
                    
                    task = re.search(r'<task>(.*?)</task>', graph_xml, re.DOTALL)
                    res = re.search(r'<result>(.*?)</result>', graph_xml, re.DOTALL)
                    det = re.search(r'<core_details>(.*?)</core_details>', graph_xml, re.DOTALL)
                    edg = re.search(r'<edges>(.*?)</edges>', graph_xml, re.DOTALL)
                    
                    self.notepad.add_context_node(
                        node_id=new_node_id,
                        task=task.group(1).strip() if task else "未命名操作",
                        result=res.group(1).strip() if res else "",
                        core_details=det.group(1).strip() if det else "",
                        raw_content=turn_messages + [{"role": "assistant", "content": clean_reply}],
                        edges=[e.strip() for e in edg.group(1).split(',')] if edg and edg.group(1).strip() else [],
                        turn_index=turn_index
                    )
                    console.print(f"\n[bold green][系统] MMU 已生成追踪节点 {new_node_id}。[/bold green]")
                else:
                    self.notepad.add_context_node(
                        node_id=new_node_id, task="常规对话", result="", core_details=clean_reply[:50], 
                        raw_content=turn_messages + [{"role": "assistant", "content": clean_reply}], edges=[], turn_index=turn_index
                    )

                # 2. 解析 2-Hop Planner 任务网络
                match_plan = re.search(r'<plan_network>(.*?)</plan_network>', reply_text, re.DOTALL)
                if match_plan:
                    clean_reply = clean_reply.replace(match_plan.group(0), "").strip()
                    plan_xml = match_plan.group(1)
                    
                    # 粗糙的 XML 解析提取 goals
                    goals = []
                    for g_match in re.finditer(r'<goal\s+id="([^"]+)"\s+status="([^"]+)"\s+desc="([^"]+)"></goal>', plan_xml):
                        goals.append({"id": g_match.group(1), "status": g_match.group(2), "desc": g_match.group(3)})
                        
                    # 提取 dependencies
                    deps = []
                    for d_match in re.finditer(r'<depends\s+from="([^"]+)"\s+on="([^"]+)"\s*/>', plan_xml):
                        deps.append({"from": d_match.group(1), "on": d_match.group(2)})
                        
                    # 提取 files
                    files = []
                    for f_match in re.finditer(r'<file\s+task="([^"]+)"\s+path="([^"]+)"\s*/>', plan_xml):
                        files.append({"task": f_match.group(1), "path": f_match.group(2)})
                        
                    # 触发图谱更新
                    self.eng_graph.update_plan(goals, deps)
                    for f in files:
                        self.eng_graph.link_file_to_task(f['task'], f['path'])
                        
                    console.print(f"[bold cyan][系统] Planner 已更新任务拓扑图 ({len(goals)} 个节点, {len(deps)} 条边, 映射了 {len(files)} 个文件)。[/bold cyan]")

                msg_dict["content"] = clean_reply
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