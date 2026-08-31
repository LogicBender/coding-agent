import os
from openai import OpenAI
from dotenv import load_dotenv

# 加载 .env 文件中的环境变量
load_dotenv()

def init_client() -> OpenAI:
    """
    初始化并返回 OpenAI 兼容的客户端。
    优先读取 .env 中的 OPENAI_API_KEY 和 OPENAI_BASE_URL。
    """
    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL")
    
    if not api_key or api_key == "sk-xxxxxxxxxxxxxxxxxxxxxxxx":
        raise ValueError("请在 .env 文件中配置有效的 OPENAI_API_KEY")

    client_kwargs = {"api_key": api_key}
    
    # base_url
    if base_url:
        client_kwargs["base_url"] = base_url
        
    return OpenAI(**client_kwargs)

def chat_completion(client: OpenAI, messages: list, tools: list = None, model: str = "deepseek-v4-pro") -> dict:
    """
    发送对话请求到大模型，并处理工具调用的逻辑。
    
    :param client: OpenAI 客户端实例
    :param messages: 对话历史列表
    :param tools: 允许模型调用的工具列表 (JSON Schema)
    :param model: 使用的模型名称，默认为 deepseek-v4-pro
    :return: 模型的回复消息对象 (包含文本或工具调用指令)
    """
    kwargs = {
        "model": model,
        "messages": messages,
        "stream": False,
        "reasoning_effort": "high",
        "extra_body": {"thinking": {"type": "enabled"}}
    }
    
    # 如果传入了工具，则让模型知道可以使用哪些工具
    if tools:
        kwargs["tools"] = tools
        
    response = client.chat.completions.create(**kwargs)
    return response.choices[0].message


# 简单的测试代码
if __name__ == "__main__":
    try:
        print("正在初始化客户端")
        client = init_client()
        print("客户端初始化成功！尝试向模型发送一条测试消息")
        
        test_messages = [{"role": "user", "content": "你好，请用一句话介绍你自己。"}]
        reply = chat_completion(client, test_messages)
        
        print(f"\n模型回复: {reply.content}")
        
    except Exception as e:
        print(f"\n运行失败: {e}")
