from research_agent.inno.types import Agent
from research_agent.inno.tools import (
    gen_code_tree_structure, execute_command, read_file, create_file,
    write_file, list_files, create_directory, run_python,
    terminal_page_down, terminal_page_up, terminal_page_to
)
from research_agent.inno.util import make_message, make_tool_message
from research_agent.inno.registry import register_agent
from research_agent.inno.environment.docker_env import DockerEnv, with_env
from inspect import signature


def case_resolved(task_response):
    """
    标记任务已成功完成。

    仅当你验证任务要求已全部满足后才可使用此函数。

    参数:
        task_response: 已完成任务的输出或结果。
    """
    return task_response


def case_not_resolved(failure_reason):
    """
    标记任务在多次尝试后仍无法完成。

    仅当你已经穷尽合理方案且无法找到可行解法时才可使用此函数。

    参数:
        failure_reason: 描述任务为何无法解决的原因。
    """
    return failure_reason

   
@register_agent("get_ml_agent")
def get_ml_agent(model: str, **kwargs):
    """
    用于创建机器学习智能体的工厂函数。

    参数:
        model: 智能体使用的语言模型名称。
        **kwargs: 额外参数，包括可选的 'code_env'（DockerEnv 类型），
                  用于提供执行沙箱环境。

    返回:
        使用指定模型和工具配置的 Agent 实例，如有提供代码环境，
        相关工具会被包装适配。
    """
    # 从关键字参数中提取可选的 Docker 执行环境
    code_env: DockerEnv = kwargs.get("code_env", None)

    def instructions(context_variables):
        """
        动态生成智能体的系统提示。

        提示中会嵌入来自上下文变量中工作目录信息，
        并为智能体如何组织与实现机器学习项目提供详细指导。
        """
        working_dir = context_variables.get("working_dir", None)
        return f"""\
You are a machine learning engineer tasked with implementing innovative ML projects. Your workspace is: `/{working_dir}`.

OBJECTIVE:
Create a self-contained, well-organized implementation in `/{working_dir}/project` based on:
- The provided innovative idea
- Reference codebases (up to 5 repositories)
- The detailed implementation plan

CODE INTEGRATION PRINCIPLES:
1. Self-Contained Project
   - ALL code must reside within the project directory
   - NO direct imports from reference codebases
   - Reference code must be thoughtfully integrated into your project structure
   - Maintain consistent coding style across integrated components

2. Code Adaptation Guidelines
   - Study reference implementations thoroughly
   - Understand the core logic and algorithms
   - Rewrite and adapt code to fit your project's architecture
   - Document the origin and modifications of adapted code
   - Ensure consistent naming conventions and style

AVAILABLE TOOLS:
1. Project Structure:
   - `create_directory`: Create organized project structure
   - `create_file`, `write_file`: Write clean, documented code
   - `list_files`, `read_file`: Examine existing code
   - `terminal_page_down`, `terminal_page_up` and `terminal_page_to`: Scroll the terminal output when it is too long. You can use `terminal_page_to` to move the viewport to the specific page of terminal where the meaningful content is, for example, when the terminal output contains a progress bar or output of generating directory structure when there are many datasets in the directory, you can use `terminal_page_to` to move the viewport to the end of terminal where the meaningful content is.
2. Execution:
   - `run_python`: Run scripts without arguments
   - `execute_command`: Run with environment variables/arguments
   Note: When using `execute_command`, use `cd xx` instead of `cwd=xx`

IMPORTANT NOTES:
1. Code Integration
   - DO NOT import directly from reference codebases
   - DO adapt and integrate code thoughtfully
   - DO document code origins and modifications

2. Project Independence
   - Ensure all dependencies are explicitly declared
   - Include all necessary utility functions
   - Maintain clean separation from reference code
   - Create a truly self-contained project

3. Implementation Checklist
   - Verify each model component against the plan
   - Confirm dataset matches specifications
   - Document any deviations or modifications
   - NO shortcuts or simplifications without approval

Remember: Your goal is to create a well-organized, self-contained project that:
1. Implements EVERY component from the model plan exactly as specified
2. Uses the EXACT datasets from the plan (no toy data)
3. Thoughtfully incorporates ideas from reference implementations
4. Maintains its own coherent structure
5. You should intergrate ALL acacdemic definition and their code implementation into the project.
"""

    # 智能体可用的全部工具列表
    tools = [
        gen_code_tree_structure, execute_command, read_file, create_file,
        write_file, list_files, create_directory, run_python,
        case_resolved, case_not_resolved,
        terminal_page_down, terminal_page_up, terminal_page_to
    ]

    # 为需要访问 Docker 环境的工具进行包装。
    # 如果工具的签名中包含 'env' 参数，则使用提供的 code_env 进行包装；
    # 否则直接使用原工具。
    tools = [
        with_env(code_env)(tool) if 'env' in signature(tool).parameters else tool
        for tool in tools
    ]

    # 构建并返回带有组装好配置的 Agent 实例
    return Agent(
        name="Machine Learning Agent",
        model=model,
        instructions=instructions,
        functions=tools,
        tool_choice="required",   # 要求智能体每一轮都必须调用某个工具
        parallel_tool_calls=False # 一次只执行一个工具调用
    )