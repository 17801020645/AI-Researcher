import json
import os
from research_agent.inno.util import single_select_menu
from research_agent.inno.core import MetaChain, MetaChainLogger
from typing import Union, Dict, List, Callable, Any
from research_agent.inno import Agent
from abc import ABC, abstractmethod
from torch import nn

class AgentModule:
    """
    封装单个 Agent 的调用逻辑，支持：
    - 异步执行
    - 基于本地 JSON 文件的缓存与断点续传
    """
    def __init__(self, agent: Agent, client: MetaChain, cache_path: str):
        """
        :param agent: 要封装的 Agent 实例
        :param client: MetaChain 客户端，用于执行 Agent
        :param cache_path: 缓存文件存放的根目录
        """
        self.agent = agent
        self.client = client
        self.cache_path = cache_path

    async def __call__(self, messages: List[Dict], context_variables: Dict, iter_times: int = None, *args, **kwargs):
        """
        异步调用 Agent，集成缓存判断与保存逻辑。
        支持三种运行模式：
        1. 有缓存且选择 Yes -> 直接使用缓存结果，不重新执行 Agent
        2. 有缓存且选择 Resume -> 从缓存恢复上下文，但重新执行 Agent（断点续传）
        3. 无缓存或选择 No -> 全新执行 Agent

        :param messages: 消息列表，格式为 [{"role": "user", "content": query}, ...]
        :param context_variables: 上下文变量字典
        :param iter_times: 可选，用于区分同一 Agent 的不同迭代版本（缓存文件命名中体现）
        :return: (更新后的 messages, 更新后的 context_variables)
        """
        # 检查是否存在缓存，escape_running 表示是否跳过实际运行（Yes 为 True，Resume 为 False）
        agent_cache, escape_running = self.check_cache(self.agent.name, iter_times)

        if agent_cache and escape_running:
            # 情况1：直接使用缓存，不重新运行
            messages.extend(agent_cache["messages"])
            context_variables.update(agent_cache["context_variables"])
        elif agent_cache and not escape_running:
            # 情况2：断点续传，先恢复上下文，再执行 Agent
            messages.extend(agent_cache["messages"])
            context_variables.update(agent_cache["context_variables"])
            response = await self.client.run_async(self.agent, messages, context_variables=context_variables, debug=True)
            ret_messages = response.messages
            ret_context_variables = response.context_variables
            # 如果不是错误结束，添加一条成功标记消息（不会被保存到缓存中）
            if ret_messages[-1]["role"] != "error":
                ret_messages.append({"role": "success", "content": "The agent successfully generated a response."})
            # 缓存原有缓存 + 本次新产生的消息（不含最后添加的 success 标记）
            self.save_cache(self.agent.name, agent_cache["messages"] + ret_messages[:-1], iter_times, ret_context_variables)
            messages.extend(ret_messages[:-1])
            context_variables.update(ret_context_variables)
            if ret_messages[-1]["role"] == "error":
                raise Exception(ret_messages[-1]["content"])
        else:
            # 情况3：全新执行
            response = await self.client.run_async(self.agent, messages, context_variables=context_variables, debug=True)
            ret_messages = response.messages
            ret_context_variables = response.context_variables
            if ret_messages[-1]["role"] != "error":
                ret_messages.append({"role": "success", "content": "The agent successfully generated a response."})
            self.save_cache(self.agent.name, ret_messages[:-1], iter_times, ret_context_variables)
            messages.extend(ret_messages[:-1])
            context_variables.update(ret_context_variables)
            if ret_messages[-1]["role"] == "error":
                raise Exception(ret_messages[-1]["content"])
        return messages, context_variables

    def save_cache(self, agent_name, messages, iter_times: int = None, context_variables: Dict = None):
        """
        将 Agent 的运行消息和上下文变量序列化保存到 JSON 文件中。

        :param agent_name: Agent 名称
        :param messages: 待保存的消息列表
        :param iter_times: 可选，迭代次数标识，用于文件名区分
        :param context_variables: 上下文变量字典
        """
        agent_name = agent_name.replace(" ", "_").lower()
        if iter_times is not None:
            agent_name = agent_name + f"_iter_{iter_times}"
        agent_cache_file = f"{self.cache_path}/agents/{agent_name}.json"
        os.makedirs(os.path.dirname(agent_cache_file), exist_ok=True)
        with open(agent_cache_file, "w", encoding="utf-8") as f:
            json.dump({"messages": messages, "context_variables": context_variables}, f, ensure_ascii=False, indent=4)

    def check_cache(self, agent_name, iter_times: int = None):
        """
        检查指定 Agent 的缓存文件是否存在，并交互询问用户如何使用。

        :param agent_name: Agent 名称
        :param iter_times: 可选，迭代次数标识
        :return: (缓存数据字典或 None, escape_running 布尔值)
                 escape_running 为 True 表示直接使用缓存不重新运行，
                 为 False 表示恢复上下文但重新运行。
        """
        agent_name_norm = agent_name.replace(" ", "_").lower()
        if iter_times is not None:
            agent_name_norm = agent_name_norm + f"_iter_{iter_times}"
        cache_file = f"{self.cache_path}/agents/{agent_name_norm}.json"
        if os.path.exists(cache_file):
            # 交互式选择：Yes 使用缓存，Resume 恢复后重新执行，No 忽略缓存
            choice = single_select_menu(["Yes", "Resume", "No"], f"The agent '{agent_name}' cache file exists, do you want to use it?")
            if choice == "Yes":
                with open(cache_file, "r", encoding="utf-8") as f:
                    return json.load(f), True
            elif choice == "Resume":
                with open(cache_file, "r", encoding="utf-8") as f:
                    return json.load(f), False
            else:
                return None, False
        return None, False

    
class ToolModule:
    """
    封装单个工具函数，支持基于 JSON 文件的结果缓存。
    若缓存存在，直接返回缓存结果，避免重复调用。
    """
    def __init__(self, tool: Callable[[Any], Union[str, Dict]], cache_path: str):
        """
        :param tool: 可调用对象，即要封装的工具函数
        :param cache_path: 缓存文件存放根目录
        """
        self.tool = tool
        self.cache_path = cache_path

    def __call__(self, tool_args: Dict, *args, **kwargs):
        """
        调用工具函数，集成缓存逻辑。
        先检查缓存，命中则返回缓存结果；否则执行工具并将结果缓存。

        :param tool_args: 传递给工具函数的参数字典
        :return: 工具函数返回的结果
        """
        tool_cache = self.check_cache(self.tool.__name__)
        if tool_cache:
            return tool_cache
        else:
            tool_result = self.tool(**tool_args)
            self.save_cache(self.tool, tool_args, tool_result)
            return tool_result

    def save_cache(self, tool: Callable, tool_args: Dict, tool_result: Union[str, Dict]):
        """
        将工具调用的参数和结果保存为 JSON 缓存文件。

        :param tool: 工具函数
        :param tool_args: 调用参数
        :param tool_result: 调用结果
        """
        tool_name = tool.__name__
        tool_cache_file = f"{self.cache_path}/tools/{tool_name}.json"
        os.makedirs(os.path.dirname(tool_cache_file), exist_ok=True)
        tool_cache_dict = {
            "name": tool_name,
            "args": tool_args,
            "result": tool_result
        }
        with open(tool_cache_file, "w", encoding="utf-8") as f:
            json.dump(tool_cache_dict, f, ensure_ascii=False, indent=4)

    def check_cache(self, tool_name: str):
        """
        检查工具缓存文件是否存在，并询问用户是否使用缓存。

        :param tool_name: 工具名称
        :return: 缓存的结果数据，若未命中或用户选择 No 则返回 None
        """
        tool_name = tool_name  # 此处保持原样，实际可直接使用参数
        cache_file = f"{self.cache_path}/tools/{tool_name}.json"
        if os.path.exists(cache_file):
            choice = single_select_menu(["Yes", "No"], f"The tool '{tool_name}' cache file exists, do you want to use it?")
            if choice == "Yes":
                with open(cache_file, "r", encoding="utf-8") as f:
                    tool_cache_dict = json.load(f)
                    return tool_cache_dict["result"]
            else:
                return None
        return None


class FlowModule(ABC):
    """
    抽象的工作流模块基类。
    子类需要实现 forward 方法，定义具体的多步骤执行逻辑。
    提供了 MetaChain 客户端和模型配置。
    """
    def __init__(self, cache_path: str, log_path: Union[str, None, MetaChainLogger] = None, model: str = "gpt-4o-2024-08-06"):
        """
        :param cache_path: 缓存根目录
        :param log_path: 日志路径或 MetaChainLogger 实例
        :param model: 使用的模型名称
        """
        self.cache_path = cache_path
        self.client = MetaChain(log_path=log_path)
        self.model = model

    @abstractmethod
    async def forward(self, *args, **kwargs):
        """
        子类必须实现的方法，定义工作流的前向执行逻辑。
        """
        raise NotImplementedError("subclass should implement this method")
    
    async def __call__(self, *args, **kwargs):
        """调用 forward 方法执行工作流。"""
        return await self.forward(*args, **kwargs)