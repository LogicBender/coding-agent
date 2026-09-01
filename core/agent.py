import os
import json
import re
from gateway.llm_client import init_client, chat_completion
from toolchain.tools import get_tools_schema, execute_tool
from memory.graph_notepad import GraphNotepad
from memory.engineering_graph import EngineeringGraph
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
            "1. 工程任务网络 (Task Network): 这是项目的宏观目标、依赖拓扑与文件映射。你需要根据它来明确自己的定位。\n"
            "2. 近期上下文踪迹 (MMU Cache): 这是你最近的思考与动作流水账。状态为 [Evicted] 的节点代表日志已清理，如需查阅必须调用 expand_node 工具。\n"
            "状态为 [Pointer -> Node_ID] 表示详情在 Node_ID 的日志中，请直接查阅 Node_ID 对应上下文内容，切勿重复调用工具！\n"
            "\n"
            "【强制结构化总结与滚动规划】\n"
            "在你决定【不调用任何工具，准备给用户最终回复】的那一次输出时，必须在回复末尾隐式加上两段 XML。\n"
            "第一段用于更新你的 MMU 上下文轨迹：\n"
            "<graph_update>\n"
            "  <task>简述本回合动作 (10-50字)</task>\n"
            "  <result>结果如何 (10-50字)</result>\n"
            "  <core_details>关键细节与教训 (30-100字)</core_details>\n"
            "  <edges>你认为哪些过去 Node ID 与本节点代表的上下文高度相关，有则列出，无则留空</edges>\n"
            "</graph_update>\n"
            "\n"
            "第二段用于动态更新任务网络 (2-Hop 滚动规划)，你可以创建新任务、更新旧任务状态、或者映射刚修改的文件：\n"
            "<plan_network>\n"
            "  <goals>\n"
            "    <goal id=\"Task_1\" status=\"[Success]\" desc=\"描述\"></goal>\n"
            "    <goal id=\"Task_2\" status=\"In_Progress\" desc=\"描述\"></goal>\n"
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
        self.model = "deepseek-v4-pro"
        self.auto_accept = False
        
        # 强制 Git 环境就绪 (解决纯新文件夹报错)
        import subprocess
        if not os.path.exists(".git"):
            try:
                subprocess.check_call(["git", "init"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except: pass
            
        # 自动配置 .gitignore，保护隐私并防止日志污染
        gitignore_path = ".gitignore"
        exclusions = [".agent_sessions/", ".dynamic_tools/", ".env"]
        existing_lines = []
        if os.path.exists(gitignore_path):
            with open(gitignore_path, "r", encoding="utf-8") as f:
                existing_lines = [line.strip() for line in f.readlines()]
        
        with open(gitignore_path, "a", encoding="utf-8") as f:
            for exc in exclusions:
                if exc not in existing_lines and exc.strip('/') not in existing_lines:
                    f.write(f"\n{exc}")
                    
        try:
            # 尝试一次空 commit 防止 HEAD 不存在
            subprocess.check_call(["git", "-c", "user.name=coding_agent", "-c", "user.email=agent@local", "commit", "--allow-empty", "-m", "Initial commit"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except: pass
        
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
        return ".agent_tasks.json"

    def switch_session(self, new_session_name):
        self.session_name = new_session_name
        
        import subprocess
        try:
            # 尝试切换到与会话同名的 git 分支，如果没有则创建
            try:
                subprocess.check_call(["git", "checkout", new_session_name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except subprocess.CalledProcessError:
                subprocess.check_call(["git", "checkout", "-b", new_session_name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass
            
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
            
    
    def rollback_to_turn(self, turn_index: int):
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
                
        return f"[cyan][系统] 成功回滚到回合 {turn_index} (Commit: {commit_hash[:7]})。{' (已从外存重载该区间上下文)' if evicted else ''}[/cyan]" 

    def fork_session(self, turn_index: int, new_session_name: str):
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
            
        from memory.graph_notepad import GraphNotepad
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
                        
        # .agent_tasks.json 已经在根目录，由 Git branch 原生管理，无需手动拷贝
        
        self.switch_session(new_session_name)
        return f"[cyan][系统] 成功派生平行会话 '{new_session_name}' (Commit: {commit_hash[:7]})。{' (已从外存重载该区间上下文)' if evicted else ''}[/cyan]" 

    def erase_turn(self, turn_index: int):
        """深度擦除一个指定的上下文回合（内存、图谱、外存全面清除）"""
        # 1. 清理活动内存
        self.history_B = [t for t in self.history_B if t.get('turn_index') != turn_index]
        self.save_history()
        
        # 2. 清理图谱与外存日志
        node_id = f"Node_{turn_index}"
        if self.notepad.graph.has_node(node_id):
            self.notepad.graph.remove_node(node_id)
            self.notepad.save()
            
        if os.path.exists(self.notepad.raw_log_path):
            try:
                lines = []
                with open(self.notepad.raw_log_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        data = json.loads(line)
                        if data.get('turn_index') != turn_index:
                            lines.append(line)
                with open(self.notepad.raw_log_path, 'w', encoding='utf-8') as f:
                    f.writelines(lines)
            except Exception as e:
                console.print(f"[red][Error] 清理外存日志失败: {e}[/red]")
        console.print(f"[cyan][系统] 深度擦除完成: 回合 {turn_index} 的一切痕迹已被抹除。[/cyan]")

    def run_task(self, user_prompt: str):
        import subprocess
        try:
            current_branch = subprocess.check_output(["git", "branch", "--show-current"], stderr=subprocess.DEVNULL).decode().strip()
            if current_branch != self.session_name:
                subprocess.check_call(["git", "checkout", self.session_name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass
            
        console.print(f"\n[bold magenta][系统] 开始任务[/bold magenta] \n")
        
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
                    console.print(f"[dim]已将 {node_id} 的原始日志换出，在图谱中标记为  已换出。[/dim]")
        
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
                mmu_md = self.notepad.get_markdown_view()
                
                first_msg["content"] = (
                    f"<system_memory_graph>\n"
                    f"=== Engineering_Task_Network ===\n{eng_md}\n\n"
                    f"=== Context_Memory ===\n{mmu_md}\n"
                    f"</system_memory_graph>\n\n"
                    f"<current_instruction>\n{first_msg['content']}\n</current_instruction>"
                )
                dynamic_turn[0] = first_msg
                api_messages.extend(dynamic_turn)
                
                with console.status("[cyan][系统] Agent 正在思考...[/cyan]", spinner="dots"):
                    response_choice = chat_completion(
                        client=self.client, 
                        messages=api_messages, 
                        tools=self.tools,
                        model=self.model
                    )
                
                response_msg = response_choice.message
                finish_reason = response_choice.finish_reason
                msg_dict = response_msg.model_dump(exclude_none=True)

                if response_msg.tool_calls:
                    turn_messages.append(msg_dict)
                    for tool_call in response_msg.tool_calls:
                        tool_name = tool_call.function.name
                        arguments = tool_call.function.arguments
                        
                        display_args = arguments
                        try:
                            args_dict = json.loads(arguments)
                            if tool_name == "write_file":
                                if "content" in args_dict and len(args_dict["content"]) > 100:
                                    args_dict["content"] = args_dict["content"][:100] + "\n...[已折叠隐藏]..."
                            elif tool_name == "replace_file_content":
                                for k in ["TargetContent", "ReplacementContent"]:
                                    if k in args_dict and len(args_dict[k]) > 100:
                                        args_dict[k] = args_dict[k][:100] + "\n...[已折叠隐藏]..."
                            display_args = json.dumps(args_dict, ensure_ascii=False)
                        except: pass
                        
                        console.print(f"[cyan][系统] 决定调用工具:[/cyan] {tool_name}")
                        console.print(f"[dim]参数: {display_args}[/dim]")
                        
                        dangerous_tools = ["run_command", "create_tool"]
                        if self.auto_accept and tool_name not in dangerous_tools:
                            confirm = True
                            console.print(f"[cyan][系统] 自动审查模式已开启，已跳过对 {tool_name} 的人工确认。[/cyan]")
                        else:
                            confirm = Confirm.ask("[yellow][系统] 允许执行此操作吗？[/yellow]")
                            
                        if not confirm:
                            otherinfo = input_session.prompt('详细的拒绝理由: ', style=input_style)
                            tool_result = f"用户拒绝了执行该操作。补充说明: {otherinfo}"
                        else:
                            with console.status(f"[cyan][系统] 正在执行 {tool_name}...[/cyan]"):
                                tool_result = execute_tool(tool_name, arguments, notepad=self.notepad, current_node_id=new_node_id)

                        display_res = str(tool_result)
                        if tool_name == "read_file":
                            lines = display_res.split('\n')
                            if len(lines) > 5:
                                display_res = '\n'.join(lines[:5]) + f"\n...[共 {len(lines)} 行，后续已折叠隐藏]..."
                        else:
                            if len(display_res) > 1000:
                                display_res = display_res[:1000] + "\n...[输出过长，已折叠隐藏]..."
                                
                        console.print(f"[cyan][系统] 工具执行结果:[/cyan]\n[dim]{display_res}[/dim]\n")
                        turn_messages.append({"role": "tool", "tool_call_id": tool_call.id, "content": tool_result})
                    continue
                    
                # 【断点续写核心逻辑】
                if finish_reason == 'length':
                    console.print("\n[bold yellow][系统警告] 模型输出达到长度上限被截断！正在自动发起断点续写...[/bold yellow]")
                    console.print(f"[dim]已接收到的前半部分:\n{response_msg.content}[/dim]\n")
                    
                    turn_messages.append(msg_dict)
                    continue_msg = {
                        "role": "user",
                        "content": "[Warn] 系统提示：你的输出因达到最大 Token 上限被截断。请不要重复上文，严格从上一句话断掉的最后一个字符开始继续输出剩余内容。"
                    }
                    turn_messages.append(continue_msg)
                    continue

                # 最终回复阶段，解析 XML
                reply_text = response_msg.content
                
                parsed_task = "常规对话"
                parsed_res = ""
                parsed_det = ""
                edges_list = []
                
                match_graph = re.search(r'<graph_update>(.*?)</graph_update>', reply_text, re.DOTALL)
                clean_reply = reply_text
                
                if match_graph:
                    clean_reply = reply_text.replace(match_graph.group(0), "").strip()
                    graph_xml = match_graph.group(1)
                    
                    task = re.search(r'<task>(.*?)</task>', graph_xml, re.DOTALL)
                    res = re.search(r'<result>(.*?)</result>', graph_xml, re.DOTALL)
                    det = re.search(r'<core_details>(.*?)</core_details>', graph_xml, re.DOTALL)
                    edg = re.search(r'<edges>(.*?)</edges>', graph_xml, re.DOTALL)
                    
                    parsed_task = task.group(1).strip() if task else "未命名操作"
                    parsed_res = res.group(1).strip() if res else ""
                    parsed_det = det.group(1).strip() if det else ""
                    edges_list = [e.strip() for e in edg.group(1).split(',')] if edg and edg.group(1).strip() else []
                else:
                    parsed_det = clean_reply[:50]
                
                import subprocess
                
                # 强制自动 commit 本回合的任何物理文件修改，提前生成 hash
                try:
                    subprocess.check_call(["git", "add", "."], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    commit_msg = f"Agent Auto-Backup: Turn {turn_index} ({new_node_id})\nTask: {parsed_task}\nResult: {parsed_res}\nDetails: {parsed_det}"
                    subprocess.check_call(["git", "-c", "user.name=coding_agent", "-c", "user.email=agent@local", "commit", "-m", commit_msg], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                except Exception:
                    pass

                commit_hash = ""
                try:
                    commit_hash = subprocess.check_output(["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL).decode().strip()
                except Exception:
                    pass
                
                if match_graph:
                    self.notepad.add_context_node(
                        node_id=new_node_id,
                        task=parsed_task,
                        result=parsed_res,
                        core_details=parsed_det,
                        raw_content=turn_messages + [{"role": "assistant", "content": clean_reply}],
                        edges=edges_list,
                        turn_index=turn_index,
                        commit_hash=commit_hash
                    )
                    console.print(f"\n[cyan][系统] MMU 已生成追踪节点 {new_node_id}。[/cyan]")
                else:
                    self.notepad.add_context_node(
                        node_id=new_node_id, task=parsed_task, result=parsed_res, core_details=parsed_det, 
                        raw_content=turn_messages + [{"role": "assistant", "content": clean_reply}], edges=[], turn_index=turn_index, commit_hash=commit_hash
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
                        
                    console.print(f"[cyan][系统] Planner 已更新任务拓扑图 ({len(goals)} 个节点, {len(deps)} 条边, 映射了 {len(files)} 个文件)。[/cyan]")

                msg_dict["content"] = clean_reply
                turn_messages.append(msg_dict)
                console.print("\n[cyan][Agent]:[/cyan]")
                console.print(Markdown(clean_reply))
                
                # 持久化本回合
                self.history_B.append({
                    "turn_index": turn_index,
                    "node_id": new_node_id,
                    "commit_hash": commit_hash,
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