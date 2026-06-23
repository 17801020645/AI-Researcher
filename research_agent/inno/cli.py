import asyncio
import importlib
import os
from inspect import signature

import click
from dotenv import load_dotenv

from research_agent.inno import MetaChain
from research_agent.inno.util import debug_print

# 仓库根目录 AI-Researcher/
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
load_dotenv(os.path.join(_REPO_ROOT, ".env"))


def _parse_context_variables(context_variables: tuple) -> dict:
    context_storage = {}
    for arg in context_variables:
        if "=" in arg:
            key, value = arg.split("=", 1)
            context_storage[key] = value
    return context_storage


def _build_code_env(container_name: str, port: int, workplace_name: str, local_root: str):
    from research_agent.inno.environment.docker_env import DockerConfig, DockerEnv

    os.makedirs(local_root, exist_ok=True)
    env_config = DockerConfig(
        container_name=container_name,
        workplace_name=workplace_name,
        communication_port=port,
        local_root=local_root,
    )
    code_env = DockerEnv(env_config)
    code_env.init_container()
    return code_env


@click.group()
def cli():
    """The command line interface for MetaChain / inno agents."""
    pass


@cli.command()
@click.option(
    "--model",
    default=None,
    help="LiteLLM 模型名，DeepSeek 示例：deepseek/deepseek-chat",
)
@click.option("--agent_func", default="get_prepare_agent", help="registry 中的 agent 工厂函数名")
@click.option("--query", required=True, help="发送给 agent 的用户 query")
@click.option("--init-docker/--no-init-docker", default=True, help="为需要 code_env 的 agent 初始化 Docker")
@click.option("--container_name", default="paper_eval_cli", help="Docker 容器名")
@click.option("--port", default=7020, type=int, help="tcp_server 映射端口")
@click.option("--workplace_name", default="workplace", help="容器内工作目录名")
@click.option(
    "--local_root",
    default=None,
    help="本地挂载根目录，默认 research_agent/cli_debug/<container_name>",
)
@click.argument("context_variables", nargs=-1)
def agent(
    model: str,
    agent_func: str,
    query: str,
    init_docker: bool,
    container_name: str,
    port: int,
    workplace_name: str,
    local_root: str,
    context_variables: tuple,
):
    """
    运行单个 Agent（调试用途）。

    示例:
        cd research_agent
        python -m inno.cli agent \\
          --model=deepseek/deepseek-chat \\
          --agent_func=get_prepare_agent \\
          --query="..." \\
          working_dir=workplace date_limit=2024-12-31
    """
    from research_agent.constant import CHEEP_MODEL

    if model is None:
        model = os.getenv("CHEEP_MODEL", CHEEP_MODEL)

    context_storage = _parse_context_variables(context_variables)
    context_storage.setdefault("working_dir", workplace_name)
    context_storage.setdefault("date_limit", "2024-12-31")

    # 触发 agent 模块注册
    importlib.import_module("research_agent.inno.agents")
    from research_agent.inno.registry import registry

    if agent_func not in registry.agents:
        available = ", ".join(sorted(registry.agents.keys())[:20])
        raise ValueError(
            f"Agent function '{agent_func}' not found in registry. "
            f"Examples: {available}"
        )

    agent_factory = registry.agents[agent_func]
    agent_kwargs = {}
    factory_params = signature(agent_factory).parameters

    if "code_env" in factory_params:
        if init_docker:
            if local_root is None:
                local_root = os.path.join(
                    os.path.dirname(__file__), "..", "cli_debug", container_name
                )
            local_root = os.path.abspath(local_root)
            agent_kwargs["code_env"] = _build_code_env(
                container_name, port, workplace_name, local_root
            )
        else:
            raise ValueError(
                f"{agent_func} requires Docker code_env. "
                "Use --init-docker or choose another agent."
            )

    agent_obj = agent_factory(model, **agent_kwargs)
    mc = MetaChain()
    messages = [{"role": "user", "content": query}]
    response = asyncio.run(mc.run(agent_obj, messages, context_storage, debug=True))
    debug_print(
        True,
        response.messages[-1]["content"],
        title=f"Result of running {agent_obj.name} agent",
        color="pink3",
    )
    return response.messages[-1]["content"]
