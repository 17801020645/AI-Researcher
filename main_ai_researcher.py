import numpy as np
import argparse
import os
import asyncio
import global_state
from dotenv import load_dotenv

# 该模块提供了 AI 研究者的主入口，根据不同的工作模式执行相应的研究流水线。
# 支持三种模式：详细想法描述、基于参考文献的构思、论文生成代理。
# 通过环境变量配置运行参数，并使用 global_state.INIT_FLAG 防止重复初始化。

def init_ai_researcher():
    # 初始化函数（当前为占位实现，后续可扩展）
    a = 1

def get_args_research(): 
    """解析研究代理（Research Agent）所需的命令行参数"""
    parser = argparse.ArgumentParser()
    parser.add_argument("--instance_path", type=str, default="benchmark/gnn.json",
                        help="基准实例路径")
    parser.add_argument('--container_name', type=str, default='paper_eval',
                        help="容器名称")
    parser.add_argument("--task_level", type=str, default="task1",
                        help="任务等级")
    parser.add_argument("--model", type=str, default="gpt-4o-2024-08-06",
                        help="使用的语言模型")
    parser.add_argument("--workplace_name", type=str, default="workplace",
                        help="工作目录名称")
    parser.add_argument("--cache_path", type=str, default="cache",
                        help="缓存路径")
    parser.add_argument("--port", type=int, default=12345,
                        help="服务端口")
    parser.add_argument("--max_iter_times", type=int, default=0,
                        help="最大迭代次数")
    parser.add_argument("--category", type=str, default="recommendation",
                        help="研究类别")
    args = parser.parse_args()
    return args

def get_args_paper():
    """解析论文生成代理（Paper Agent）所需的命令行参数"""
    parser = argparse.ArgumentParser()
    parser.add_argument("--research_field", type=str, default="vq",
                        help="研究领域")
    parser.add_argument("--instance_id", type=str, default="rotation_vq",
                        help="实例ID")
    args = parser.parse_args()
    return args

def main_ai_researcher(input, reference, mode):
    """
    AI 研究者主函数，根据 mode 参数选择不同的执行分支。
    参数：
        input: 输入数据（具体含义由下游模块定义）
        reference: 参考文献信息
        mode: 运行模式，可选值为 'Detailed Idea Description', 'Reference-Based Ideation', 'Paper Generation Agent'
    """
    # 从 .env 文件中加载环境变量，用于灵活配置运行参数
    load_dotenv()
    category = os.getenv("CATEGORY")
    instance_id = os.getenv("INSTANCE_ID")
    task_level = os.getenv("TASK_LEVEL")
    container_name = os.getenv("CONTAINER_NAME")
    workplace_name = os.getenv("WORKPLACE_NAME")
    cache_path = os.getenv("CACHE_PATH")
    port = int(os.getenv("PORT"))
    max_iter_times = int(os.getenv("MAX_ITER_TIMES"))

    # 根据模式分发任务
    match mode:
        case 'Detailed Idea Description':
            # 详细想法描述模式：运行研究计划推理
            # 使用 INIT_FLAG 避免在同一个会话中重复初始化环境
            if global_state.INIT_FLAG is False:
                global_state.INIT_FLAG = True
                # 获取当前文件所在目录，并切换到 research_agent 子目录
                current_file_path = os.path.realpath(__file__)
                current_dir = os.path.dirname(current_file_path)
                sub_dir = os.path.join(current_dir, "research_agent")
                os.chdir(sub_dir)

                # 动态导入研究代理相关模块
                from research_agent.constant import COMPLETION_MODEL
                from research_agent import run_infer_idea, run_infer_plan

                # 构建参数对象并填充从环境变量读取的配置
                args = get_args_research()
                args.instance_path = f"../benchmark/final/{category}/{instance_id}.json"
                args.task_level = task_level
                args.model = COMPLETION_MODEL
                args.container_name = container_name
                args.workplace_name = workplace_name
                args.cache_path = cache_path
                args.port = port
                args.max_iter_times = max_iter_times
                args.category = category

                # 执行研究计划推理主线
                run_infer_plan.main(args, input, reference)
                # 重置标志，允许下次进入
                global_state.INIT_FLAG = False

        case 'Reference-Based Ideation':
            # 基于参考文献的构思模式：根据参考资料生成想法
            if global_state.INIT_FLAG is False:
                global_state.INIT_FLAG = True
                current_file_path = os.path.realpath(__file__)
                current_dir = os.path.dirname(current_file_path)
                sub_dir = os.path.join(current_dir, "research_agent")
                os.chdir(sub_dir)

                # 导入所需模块（重复导入是为了在函数内部按需加载）
                from research_agent.constant import COMPLETION_MODEL
                from research_agent import run_infer_idea, run_infer_plan

                args = get_args_research()
                args.instance_path = f"../benchmark/final/{category}/{instance_id}.json"
                args.container_name = container_name
                args.task_level = task_level
                args.model = COMPLETION_MODEL
                args.workplace_name = workplace_name
                args.cache_path = cache_path
                args.port = port
                args.max_iter_times = max_iter_times
                args.category = category

                # 执行基于参考文献的想法生成主线
                run_infer_idea.main(args, reference)
                global_state.INIT_FLAG = False

        case 'Paper Generation Agent':
            # 论文生成代理模式：自动撰写论文
            if global_state.INIT_FLAG is False:
                global_state.INIT_FLAG = True

                from paper_agent import writing
                args = get_args_paper()

                research_field = category
                args.research_field = research_field
                args.instance_id = instance_id

                # 异步执行论文写作流程
                asyncio.run(writing.writing(args.research_field, args.instance_id))
                global_state.INIT_FLAG = False
