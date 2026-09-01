import os
import json

class DynamicToolManager:
    """
    动态工具管理器：负责在运行时允许 LLM 编写并装载原生的 Python 工具。
    工具会被持久化保存，并且可以随着上下文即时生效。
    """
    def __init__(self, storage_dir=".dynamic_tools"):
        self.storage_dir = storage_dir
        os.makedirs(self.storage_dir, exist_ok=True)
        self.tools_schema = []
        self.tool_functions = {}
        self.load_all()

    def load_all(self):
        self.tools_schema = []
        self.tool_functions = {}
        if not os.path.exists(self.storage_dir):
            return
            
        for filename in os.listdir(self.storage_dir):
            if filename.endswith(".json"):
                base_name = filename[:-5]
                py_file = os.path.join(self.storage_dir, f"{base_name}.py")
                json_file = os.path.join(self.storage_dir, filename)
                
                if os.path.exists(py_file):
                    try:
                        with open(json_file, 'r', encoding='utf-8') as f:
                            schema = json.load(f)
                        with open(py_file, 'r', encoding='utf-8') as f:
                            code = f.read()
                            
                        # 动态编译加载
                        local_scope = {}
                        exec(code, globals(), local_scope)
                        func = local_scope.get(base_name)
                        
                        if callable(func):
                            self.tools_schema.append(schema)
                            self.tool_functions[base_name] = func
                    except Exception as e:
                        print(f"[警告] 加载动态工具 {base_name} 失败: {e}")

    def create_tool(self, tool_name: str, description: str, parameters_schema_json: str, python_code: str) -> str:
        try:
            params = json.loads(parameters_schema_json)
        except Exception:
            return "[Error] 错误: parameters_schema 必须是有效的 JSON 字符串。"
            
        schema = {
            "type": "function",
            "function": {
                "name": tool_name,
                "description": description,
                "parameters": params
            }
        }
        
        # 预编译检查，防止大模型写出语法错误的代码
        try:
            local_scope = {}
            exec(python_code, globals(), local_scope)
            func = local_scope.get(tool_name)
            if not callable(func):
                return f"[Error] 错误: 提供的 Python 代码中必须包含名为 '{tool_name}' 的函数。"
        except Exception as e:
            return f"[Error] 错误: Python 代码编译或执行失败 - {str(e)}"
            
        # 落盘保存
        py_file = os.path.join(self.storage_dir, f"{tool_name}.py")
        json_file = os.path.join(self.storage_dir, f"{tool_name}.json")
        
        with open(py_file, 'w', encoding='utf-8') as f:
            f.write(python_code)
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(schema, f, ensure_ascii=False, indent=2)
            
        # 热重载进入内存
        self.tools_schema.append(schema)
        self.tool_functions[tool_name] = func
        
        return f"[Success] 成功: 自定义原生工具 '{tool_name}' 已构建并热加载完毕！你现在就可以在下一轮思考中立刻调用它。"

    def get_schemas(self) -> list:
        return self.tools_schema

    def execute(self, tool_name: str, arguments_dict: dict) -> str:
        if tool_name not in self.tool_functions:
            return f"[Error] 错误: 动态工具 '{tool_name}' 不存在或未正确加载。"
        try:
            func = self.tool_functions[tool_name]
            result = func(**arguments_dict)
            return str(result)
        except Exception as e:
            return f"[Error] 动态工具 '{tool_name}' 执行内部异常: {str(e)}"
