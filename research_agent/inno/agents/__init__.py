# 以下为旧版 metachain 的导入方式，现已弃用（注释掉）
# from metachain.agents.programming_agent import get_programming_agent
# from metachain.agents.tool_retriver_agent import get_tool_retriver_agent
# from metachain.agents.agent_check_agent import get_agent_check_agent
# from metachain.agents.tool_check_agent import get_tool_check_agent
# from metachain.agents.github_agent import get_github_agent
# from metachain.agents.programming_triage_agent import get_programming_triage_agent
# from metachain.agents.plan_agent import get_plan_agent

# import os
# import importlib
# from metachain.registry import registry

# # 获取当前目录下的所有 .py 文件
# current_dir = os.path.dirname(__file__)
# for file in os.listdir(current_dir):
#     if file.endswith('.py') and not file.startswith('__'):
#         module_name = file[:-3]
#         importlib.import_module(f'metachain.agents.{module_name}')

# # 导出所有注册的 agent 创建函数
# globals().update(registry.agents)

# __all__ = list(registry.agents.keys())

import os
import importlib
from research_agent.inno.registry import registry  # 导入注册中心，用于收集所有 agent


def import_agents_recursively(base_dir: str, base_package: str):
    """递归导入 base_dir 下所有 .py 文件中的 agent 模块
    
    遍历目录树，自动加载每个非 __init__ 的 Python 模块，
    以便模块中的 agent 注册到 registry 中。
    
    Args:
        base_dir: 开始搜索的根目录路径
        base_package: 对应的 Python 包基名（如 'inno.agents'）
    """
    # os.walk 递归遍历目录树
    for root, dirs, files in os.walk(base_dir):
        # 计算当前目录相对于 base_dir 的相对路径
        rel_path = os.path.relpath(root, base_dir)
        
        for file in files:
            # 只处理 .py 文件，且排除 __init__.py
            if file.endswith('.py') and not file.startswith('__'):
                # 根据相对路径构造模块完整的导入路径
                if rel_path == '.':
                    # 在根目录下的文件
                    module_path = f"{base_package}.{file[:-3]}"
                else:
                    # 在子目录下的文件，需将路径分隔符转为点号
                    package_path = rel_path.replace(os.path.sep, '.')
                    module_path = f"{base_package}.{package_path}.{file[:-3]}"
                
                # 动态导入模块，触发其中 agent 的注册
                try:
                    importlib.import_module(module_path)
                except Exception as e:
                    # 导入失败时打印警告，但不中断整体流程
                    print(f"Warning: Failed to import {module_path}: {e}")


# 获取当前 __init__.py 所在目录（即 agents 包目录）
current_dir = os.path.dirname(__file__)
# 递归导入 agents 包及其子包中的所有 agent 模块
import_agents_recursively(current_dir, 'inno.agents')

# 将注册中心收集到的所有 agent 创建函数注入当前模块的全局命名空间
globals().update(registry.agents)

# 显式声明模块的公开接口，方便 from package import * 使用
__all__ = list(registry.agents.keys())