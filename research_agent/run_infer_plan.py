import json
# 导入项目内部自定义的流程模块、工具模块和代理模块
from research_agent.inno.workflow.flowcache import FlowModule, ToolModule, AgentModule
# 导入用于获取 arXiv 论文元数据的工具函数
from research_agent.inno.tools.inno_tools.paper_search import get_arxiv_paper_meta
# 导入 GitHub 搜索相关工具
from research_agent.inno.tools.inno_tools.code_search import search_github_repos, search_github_code
# 导入各种专门代理的构建函数
from research_agent.inno.agents.inno_agent.plan_agent import get_coding_plan_agent
from research_agent.inno.agents.inno_agent.prepare_agent import get_prepare_agent
from research_agent.inno.agents.inno_agent.ml_agent import get_ml_agent
from research_agent.inno.agents.inno_agent.judge_agent import get_judge_agent
from research_agent.inno.agents.inno_agent.survey_agent import get_survey_agent
from research_agent.inno.agents.inno_agent.exp_analyser import get_exp_analyser_agent
# 根据论文标题下载 arXiv 源码的工具
from research_agent.inno.tools.arxiv_source import download_arxiv_source_by_title
from research_agent.inno import MetaChain
from tqdm import tqdm
from pydantic import BaseModel, Field
# 导入全局常量，如工作区名称、模型名称等
from research_agent.constant import DOCKER_WORKPLACE_NAME, COMPLETION_MODEL, CHEEP_MODEL
from research_agent.inno.util import single_select_menu
# 环境相关模块
from research_agent.inno.environment.docker_env import DockerEnv, DockerConfig
from research_agent.inno.environment.browser_env import BrowserEnv
from research_agent.inno.environment.markdown_browser import RequestsMarkdownBrowser
import asyncio
import argparse
import os
from typing import List, Dict, Any, Union
from research_agent.inno.logger import MetaChainLogger
import importlib
from research_agent.inno.environment.utils import setup_dataset

# 辅助函数：将源论文列表格式化为可读字符串
def warp_source_papers(source_papers):
    return "\n".join([f"Title: {source_paper['reference']}; You can use this paper in the following way: {source_paper['usage']}" for source_paper in source_papers])

# 辅助函数：从一段可能包含额外文本的输出中提取 JSON 对象
def extract_json_from_output(output_text: str) -> dict:
    # 使用栈来匹配最外层的大括号，找到完整的 JSON 字符串
    def find_json_boundaries(text):
        stack = []
        start = -1
        
        for i, char in enumerate(text):
            if char == '{':
                if not stack:  # 第一个开括号，记录起始位置
                    start = i
                stack.append(char)
            elif char == '}':
                stack.pop()
                if not stack and start != -1:  # 栈为空且已找到起始位置，返回完整 JSON 字符串
                    return text[start:i+1]
        
        return None

    json_str = find_json_boundaries(output_text)
    
    if json_str:
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            print(f"JSON解析错误: {e}")
            return {}
    return {}

# 解析命令行参数
def get_args(): 
    parser = argparse.ArgumentParser()
    parser.add_argument("--instance_path", type=str, default="benchmark/gnn.json")
    parser.add_argument('--container_name', type=str, default='paper_eval')
    parser.add_argument("--task_level", type=str, default="task1")
    parser.add_argument("--model", type=str, default="gpt-4o-2024-08-06")
    parser.add_argument("--workplace_name", type=str, default="workplace")
    parser.add_argument("--cache_path", type=str, default="cache")
    parser.add_argument("--port", type=int, default=12345)
    parser.add_argument("--max_iter_times", type=int, default=0)
    parser.add_argument("--category", type=str, default="recommendation")
    args = parser.parse_args()
    return args

# 定义评估元数据的数据模型
class EvalMetadata(BaseModel):
    source_papers: List[dict] = Field(description="the list of source papers")
    task_instructions: str = Field(description="the task instructions")
    date: str = Field(description="the date", pattern="^\d{4}-\d{2}-\d{2}$")  # YYYY-MM-DD 格式
    date_limit: str = Field(description="the date limit", pattern="^\d{4}-\d{2}-\d{2}$")

# 加载评估实例：从 JSON 文件读取并补充论文元数据
def load_instance(instance_path, task_level) -> Dict:
    with open(instance_path, "r", encoding="utf-8") as f:
        eval_instance = json.load(f)
    source_papers = eval_instance["source_papers"]  
    task_instructions = eval_instance[task_level]   
    arxiv_url = eval_instance["url"]
    meta = get_arxiv_paper_meta(arxiv_url)
    if meta is None:
        date = "2024-01-01"  # 获取元数据失败时使用默认日期
    else:
        date = meta["published"].strftime("%Y-%m-%d")
    return EvalMetadata(source_papers=source_papers, task_instructions=task_instructions, date=date, date_limit=date).model_dump()

# 对元数据中每一篇源论文在 GitHub 上进行搜索，并汇总结果
def github_search(metadata: Dict) -> str:
    github_result = ""
    for source_paper in tqdm(metadata["source_papers"]):
        github_result += search_github_repos(metadata, source_paper["reference"], 10)
        github_result += "*"*30 + "\n"
    return github_result

# 核心流程类，继承自 FlowModule，编排整个研究任务的执行
class InnoFlow(FlowModule):
    def __init__(self, cache_path: str, log_path: Union[str, None, MetaChainLogger] = None, model: str = "gpt-4o-2024-08-06", code_env: DockerEnv = None, web_env: BrowserEnv = None, file_env: RequestsMarkdownBrowser = None):
        super().__init__(cache_path, log_path, model)
        # 初始化各种模块：加载实例、GitHub 搜索、各种代理和工具
        self.load_ins = ToolModule(load_instance, cache_path)
        self.git_search = ToolModule(github_search, cache_path)
        self.prepare_agent = AgentModule(get_prepare_agent(model=CHEEP_MODEL, code_env=code_env), self.client, cache_path)
        self.download_papaer = ToolModule(download_arxiv_source_by_title, cache_path)
        self.coding_plan_agent = AgentModule(get_coding_plan_agent(model=CHEEP_MODEL, code_env=code_env), self.client, cache_path)
        self.ml_agent = AgentModule(get_ml_agent(model=COMPLETION_MODEL, code_env=code_env), self.client, cache_path)
        self.judge_agent = AgentModule(get_judge_agent(model=CHEEP_MODEL, code_env=code_env, web_env=web_env, file_env=file_env), self.client, cache_path)
        self.survey_agent = AgentModule(get_survey_agent(model=CHEEP_MODEL, file_env=file_env, code_env=code_env), self.client, cache_path)
        self.exp_analyser = AgentModule(get_exp_analyser_agent(model=CHEEP_MODEL, file_env=file_env, code_env=code_env), self.client, cache_path)

    # 定义核心执行流程
    async def forward(self, instance_path: str, task_level: str, local_root: str, workplace_name: str, max_iter_times: int, category: str, ideas: str, references: str, *args, **kwargs):
        # 1. 加载评估实例和元数据
        metadata = self.load_ins({"instance_path": instance_path, "task_level": task_level})
        context_variables = {
            "working_dir": workplace_name,
            "date_limit": metadata["date_limit"],
        }

        # 2. 执行 GitHub 搜索
        github_result = self.git_search({"metadata": metadata})
        
        # 3. 准备阶段：让 Prepare Agent 选择至少5个仓库作为参考代码库
        query = f"""\
You are given a list of papers, searching results of the papers on GitHub, and innovative ideas according to the papers.
List of papers:
{references}

Searching results of the papers on GitHub:
{github_result}

innovative ideas:
{ideas}

Your task is to choose at least 5 repositories as the reference codebases.
"""
        messages = [{"role": "user", "content": query}]
        prepare_messages, context_variables = await self.prepare_agent(messages, context_variables)
        prepare_res = prepare_messages[-1]["content"]
        prepare_dict = extract_json_from_output(prepare_res)
        paper_list = prepare_dict["reference_papers"]
        # 根据准备结果下载相关论文
        download_res = self.download_papaer({"paper_list": paper_list, "local_root": local_root, "workplace_name": workplace_name})

        # 4. 调研阶段：Survey Agent 进行全面的文献调研并给出实现计划
        survey_query = f"""\
I have an innovative ideas related to machine learning:
{ideas}
And a list of papers for your reference:
{references}

I have carefully gone through these papers' github repositories and found download some of them in my local machine, with the following information:
{prepare_res}
And I have also downloaded the corresponding paper in the Tex format, with the following information:
{download_res}

Your task is to do a comprehensive survey on the innovative ideas and the papers, and give me a detailed plan for the implementation.

Note that the math formula should be as complete as possible, and the code implementation should be as complete as possible. Don't use placeholder code.
"""
        messages = [{"role": "user", "content": survey_query}]
        context_variables["notes"] = []
        survey_messages, context_variables = await self.survey_agent(messages, context_variables)
        survey_res = survey_messages[-1]["content"]
        context_variables["model_survey"] = survey_res

        # 5. 动态加载对应类别的数据集元信息模块
        data_module = importlib.import_module(f"benchmark.process.dataset_candidate.{category}.metaprompt")
        dataset_description = f"""\
You should select SEVERAL datasets as experimental datasets from the following description:
{data_module.DATASET}

We have already selected the following baselines for these datasets:
{data_module.BASELINE}

The performance comparison of these datasets:
{data_module.COMPARISON}

And the evaluation metrics are:
{data_module.EVALUATION}

{data_module.REF}
"""

        # 6. 编码计划阶段：Coding Plan Agent 结合调研结果和数据集信息制定详细实现计划
        plan_query = f"""\
I have an innovative ideas related to machine learning:
{ideas}
And a list of papers for your reference:
{references}

I have carefully gone through these papers' github repositories and found download some of them in my local machine, with the following information:
{prepare_res}
I have also explored the innovative ideas and the papers, with the following notes:
{survey_res}

We have already selected the following datasets as experimental datasets:
{dataset_description}

Your task is to carefully review the existing resources and understand the task, and give me a detailed plan for the implementation.
"""
        messages = [{"role": "user", "content": plan_query}]
        plan_messages, context_variables = await self.coding_plan_agent(messages, context_variables)
        plan_res = plan_messages[-1]["content"]

        # 7. 核心开发阶段：ML Agent 依据计划、调研笔记和数据集描述实现具体代码并训练
        ml_dev_query = f"""\
INPUT:
You are given an innovative idea:
{ideas}. 
and the reference codebases chosen by the `Prepare Agent`:
{prepare_res}
And I have conducted the comprehensive survey on the innovative idea and the papers, and give you the model survey notes:
{survey_res}
You should carefully go through the math formula and the code implementation, and implement the innovative idea according to the plan and existing resources.

We have already selected the following datasets as experimental datasets:
{dataset_description}
Your task is to implement the innovative idea after carefully reviewing the math formula and the code implementation in the paper notes and existing resources in the directory `/{workplace_name}`. You should select ONE most appropriate and lightweight dataset from the given datasets, and implement the idea by creating new model, and EXACTLY run TWO epochs of training and testing on the ACTUAL dataset on the GPU device. Note that EVERY atomic academic concept in model survey notes should be implemented in the project.
...（省略详细项目结构要求）...
"""
        messages = [{"role": "user", "content": ml_dev_query}]
        ml_dev_messages, context_variables = await self.ml_agent(messages, context_variables)
        ml_dev_res = ml_dev_messages[-1]["content"]

        # 8. 评判阶段：Judge Agent 评估实现是否符合要求并给出修改建议
        query = f"""\
INPUT:
You are given an innovative idea:
{ideas}
and the reference codebases chosen by the `Prepare Agent`:
{prepare_res}
and the detailed coding plan:
{plan_res}
The implementation of the project:
{ml_dev_res}
Your task is to evaluate the implementation, and give a suggestion about the implementation. Note that you should carefully check whether the implementation meets the idea, especially the atomic academic concepts in the model survey notes one by one! If not, give comprehensive suggestions about the implementation.

[IMPORTANT] You should fully utilize the existing resources in the reference codebases as much as possible, including using the existing datasets, model components, and training process, but you should also implement the idea by creating new model components!
...（省略重要提示）...
"""
        input_messages = [{
            "role": "user",
            "content": query
        }]
        judge_messages, context_variables = await self.judge_agent(input_messages, context_variables)
        judge_res = judge_messages[-1]["content"]

        # 9. 迭代改进循环：根据 Judge Agent 的建议反复修改代码，直到满足要求或达到最大迭代次数
        MAX_ITER_TIMES = max_iter_times
        for i in range(MAX_ITER_TIMES):
            query = f"""\
You are given an innovative idea:
{ideas}
and the reference codebases chosen by the `Prepare Agent`:
{prepare_res}
and the detailed coding plan:
{plan_res}
and the model survey notes you should carefully follow:
{survey_res}
And your last implementation of the project:
{ml_dev_res}
The suggestion about your last implementation:
{judge_res}
Your task is to modify the project according to the suggestion. Note that you should MODIFY rather than create a new project! Take full advantage of the existing resources! Still use the SAME DATASET!
...（省略重要提示）...
"""
            judge_messages.append({"role": "user", "content": query})
            judge_messages, context_variables = await self.ml_agent(judge_messages, context_variables, iter_times=i+1)
            ml_dev_res = judge_messages[-1]["content"]
            # 再次评估修改后的实现
            query = f"""\
You are given an innovative idea:
{ideas}
and the reference codebases chosen by the `Prepare Agent`:
{prepare_res}
and the detailed coding plan:
{plan_res}
and the model survey notes you should carefully follow:
{survey_res}
The implementation of the project:
{ml_dev_res}
Please evaluate the implementation, and give a suggestion about the implementation.
"""
            judge_messages.append({"role": "user", "content": query})
            judge_messages, context_variables = await self.judge_agent(judge_messages, context_variables, iter_times=i+1)
            judge_res = judge_messages[-1]["content"]
            # 如果评估结果为完全正确，则提前结束循环
            if '"fully_correct": true' in judge_messages[-1]["content"]:
                break   

        # 10. 最终提交阶段：将代码提交到环境，运行正式实验并获取结果
        ml_submit_query = f"""\
You are given an innovative idea:
{ideas}
And your last implementation of the project:
{ml_dev_res}
The suggestion about your last implementation:
{judge_res}
You have run out the maximum iteration times to implement the idea by running the script `run_training_testing.py` with TWO epochs of training and testing on ONE ACTUAL dataset.
Your task is to submit the code to the environment by running the script `run_training_testing.py` with APPROPRIATE epochs of training and testing on THIS ACTUAL dataset in order to get some stastical results. You must MODIFY the epochs in the script `run_training_testing.py` rather than use the 2 epochs.
...（省略重要提示）...
"""
        judge_messages.append({"role": "user", "content": ml_submit_query})
        judge_messages, context_variables = await self.ml_agent(judge_messages, context_variables, iter_times="submit")
        submit_res = judge_messages[-1]["content"]

        # 11. 实验分析优化循环：对实验结果进行分析，提出进一步实验计划并迭代改进
        EXP_ITER_TIMES = 2
        for i in range(EXP_ITER_TIMES):
            exp_planner_query = f"""\
You are given an innovative idea:
{ideas}
And the reference codebases chosen by the `Prepare Agent`:
{prepare_res}
And the detailed coding plan:
{plan_res}
You have conducted the experiments and get the experimental results:
{submit_res}
Your task is to: 
1. Analyze the experimental results and give a detailed analysis report about the results.
2. Analyze the reference codebases and papers, and give a further plan to let `Machine Learning Agent` to do more experiments based on the innovative idea.
...（省略详细要求）...
"""
            judge_messages.append({"role": "user", "content": exp_planner_query})
            judge_messages, context_variables = await self.exp_analyser(judge_messages, context_variables, iter_times=f"refine_{i+1}")
            analysis_report = judge_messages[-1]["content"]

            analysis_report = context_variables["experiment_report"][-1]["analysis_report"]
            further_plan = context_variables["experiment_report"][-1]["further_plan"]

            refine_query = f"""\
You are given an innovative idea:
{ideas}
And the reference codebases chosen by the `Prepare Agent`:
{prepare_res}
And the detailed coding plan:
{plan_res}
You have conducted the experiments and get the experimental results:
{submit_res}
And a detailed analysis report about the results are given by the `Experiment Planner Agent`:
{analysis_report}
Your task is to refine the experimental results according to the analysis report by modifying existing code in the directory `/{workplace_name}/project`.
...（省略重要提示）...
"""
            judge_messages.append({"role": "user", "content": refine_query})
            judge_messages, context_variables = await self.ml_agent(judge_messages, context_variables, iter_times=f"refine_{i+1}")
            refine_res = judge_messages[-1]["content"]

# 主函数：负责环境搭建、流程实例化与执行
def main(args, ideas, references):
    # 读取评估实例，获取 instance_id
    with open(args.instance_path, "r", encoding="utf-8") as f:
        eval_instance = json.load(f)
    instance_id = eval_instance["instance_id"]
    # 构建本地工作目录路径
    local_root = os.path.join(os.getcwd(),"workplace_paper" , f"task_{instance_id}" + "_" + COMPLETION_MODEL.replace("/", "__"),  args.workplace_name)
    container_name = args.container_name + "_" + instance_id + "_" + COMPLETION_MODEL.replace("/", "__")
    os.makedirs(local_root, exist_ok=True)

    # 配置 Docker 环境
    env_config = DockerConfig(container_name = container_name, 
                              workplace_name = args.workplace_name, 
                              communication_port = args.port, 
                              local_root = local_root,
                              )
    code_env = DockerEnv(env_config)
    code_env.init_container()
    # 初始化数据集
    setup_dataset(args.category, code_env.local_workplace)
    # 初始化网页环境和文件浏览环境
    web_env = BrowserEnv(browsergym_eval_env = None, local_root=env_config.local_root, workplace_name=env_config.workplace_name)
    file_env = RequestsMarkdownBrowser(viewport_size=1024 * 4, local_root=env_config.local_root, workplace_name=env_config.workplace_name, downloads_folder=os.path.join(env_config.local_root, env_config.workplace_name, "downloads"))

    # 创建流程实例并运行
    flow = InnoFlow(cache_path="cache_" + instance_id + "_" + COMPLETION_MODEL.replace("/", "__"), log_path="log_" + instance_id, code_env=code_env, web_env=web_env, file_env=file_env, model=args.model)
    asyncio.run(flow(instance_path=args.instance_path, task_level=args.task_level, local_root=local_root, workplace_name=args.workplace_name, max_iter_times=args.max_iter_times, category=args.category, ideas = ideas, references = references))

if __name__ == "__main__":
    args = get_args()
    main(args)

# 以下是被注释掉的示例输入模板，不再添加注释
"""
INPUT:
You are given an innovative idea:
Combine DDPM model with transformer model to generate the image.
...
"""