# -*- coding: utf-8 -*-
"""
方法论章节自动撰写模块

本模块基于GPT模型，通过迭代生成和细化结构，并利用Agent产出的技术内容，
自动撰写学术论文中的“方法论”（Methodology）章节。
主要流程：
1. 根据模型代码和Agent输出，迭代生成/修订章节结构（LaTeX格式）。
2. 针对每个子章节，结合已有内容和新增技术信息，进行详细撰写。
3. 合并所有子章节，生成完整的方法论文本。
4. 执行最终写作检查（学术风格、数学公式、标题优化等）。
"""

import os
import json
import asyncio
import logging
from tqdm import tqdm
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 导入自定义工具：GPT客户端和基类SectionComposer
from benchmark_collection.utils.openai_utils import GPTClient
from paper_agent.section_composer import SectionComposer, setup_logging


class MethodologyComposer(SectionComposer):
    """
    方法论章节撰写器，继承自SectionComposer。
    负责生成、细化和完善Methodology部分的LaTeX内容。
    """

    def __init__(self, research_field: str, structure_iterations: int = 3):
        """
        初始化撰写器。

        :param research_field: 研究领域（用于路径和日志）
        :param structure_iterations: 结构迭代次数（默认3）
        """
        super().__init__(research_field, "methodology", structure_iterations)

    def read_model_code(self, model_dir):
        """
        读取模型目录下所有Python文件，合并为一个字符串，供后续分析。

        :param model_dir: 模型代码所在目录
        :return: 合并后的代码字符串（每个文件添加文件名注释）
        """
        combined_code = []
        for filename in os.listdir(model_dir):
            if filename.endswith('.py'):
                with open(os.path.join(model_dir, filename), 'r') as f:
                    combined_code.append(f"# File: {filename}\n{f.read()}\n")
        return '\n'.join(combined_code)

    async def generate_or_revise_structure(self, content, current_structure, iteration):
        """
        基于提供的内容（代码或Agent输出）生成或修订方法论的结构（LaTeX格式）。

        :param content: 用于分析的技术内容（文本）
        :param current_structure: 当前已有的结构（可能为空）
        :param iteration: 当前迭代次数
        :return: 更新后的结构字符串（LaTeX注释+章节标题）
        """
        prompt = f"""Based on the given content, generate or revise the technical methodology structure of the proposed method, using latex format.
Current iteration: {iteration}/{self.structure_iterations}

Current structure (if exists):
{current_structure}

Content to analyze:
{content}

Guidelines for structure generation:
1. FOCUS ON TECHNICAL METHODOLOGY:
   - Include only the technical components and mechanisms of the proposed method (e.g. a machine learning model)
   - Exclude experimental settings, configurations, and evaluation procedures (which may probably occure in the content. Ignore them)

2. SECTION HIERARCHY:
   - Main section should be the name of the Proposed Method (with latex command \section{{Name_of_Proposed_Method}})
   - Use subsections for major components under the entire proposed method (e.g., encoders, architectures, learning objectives), with latex commands \subsection{{...}} and \subsubsection{{...}}
   - Use subsubsections for detailed mechanisms within major components
   - Ensure logical flow from basic components to advanced mechanisms

3. REQUIRED COMMENTS:
   Add latex comments (start with %) under the \section or \subsection or \subsubsection commands to explain the following:

   For the entire "Proposed Method" section:
   - Overview of the technical approach (what techniques are used to achieve what goal)
   - Functionalities of different components (subsections)
   - How different components (subsections) work together. The reader should get a global picture of the entire framework with this description
   
   For each subsection and subsubsection:
   - Technical purpose of this component
   - Connection to other components
   - Key technical innovations or mechanisms
   - A brief introduction to the component

   For each subsection and the entire proposed framework, give an explicit workflow chart for the specific subsection or the entire framework, using text

   For each subsection, give clear definitions on the input and output of the component, from where it get the input, and to where the output is used

4. STRUCTURE FORMAT:
   \section{{Proposed Method}}
   % [Overall method description and component relations]
   % [Input and output of the entire framework]
   % [workflow of the entire framework]
   
   \subsection{{Component 1}}
   % [Technical purpose and relations]
   % [Input and output of component 1]
   % [workflow of component 1]
   
   \subsection{{Component 2}}
   % [Technical purpose and relations]
   % [Input and output of component 2]
   % [workflow of component 2]
   
   \subsubsection{{Component 2.1}}
   % [Technical purpose and relations]

   Note that subsections are first-level modules of the proposed method. subsubsections are either 1. second-level submodules that are relatively independent and important, or 2. aspects that are important to highlight to better introduce the module.

Output only the LaTeX structure with comments as specified above. Note again that you should include only model designs using a professional writing style for academic research in AI domains, exclude any implementation details (e.g. hyperparameter configurations, coding details), experimental settings, or evaluation procedures."""

        return await self.gpt_client.chat(prompt=prompt)

    async def detailize_subsection(self, structure, current_text, content, subsection):
        """
        根据给定的结构信息和新增技术内容，撰写或修订单个子章节的详细文本。

        :param structure: 整体的结构信息（用于理解上下文）
        :param current_text: 该子章节当前已有的文本（可能为空）
        :param content: 新增的技术内容（代码或Agent输出）
        :param subsection: 子章节名称（例如“Encoder Module”）
        :return: 更新后的该子章节LaTeX文本
        """
        # 获取一个随机的写作模板（从基类方法）
        writing_template = self.get_random_template()
        
        prompt = f"""Revise or write the following subsection of the methodology section:
\subsection{{{subsection}}}

CURRENT TEXT (if any):
{current_text}

Note: This is an iterative editing process. If current text exists:
1. Build upon and improve the existing content
2. Add missing technical details
3. Refine the writing while preserving valid technical descriptions
4. Maintain consistency with previously written parts

STRUCTURE INFORMATION:
{structure}

Note: The structure above provides high-level information about:
1. The overall architecture and components of the method
2. The purpose and role of each component
3. How components interact with each other
4. The workflow of the entire system
Use this information to understand the big picture and component relationships, NOT as writing guidelines.

NEW TECHNICAL CONTENT TO INCORPORATE:
{content}

Note: The content above contains specific technical details about:
1. Model architectures and computations
2. Mathematical formulations
3. Algorithm workflows
4. Implementation details
Use this information to write concrete technical descriptions that are missing from or can improve the current text.

REFERENCE WRITING TEMPLATE:
{writing_template}

Note: This template is for reference only. Use it to understand:
1. Common academic writing patterns (e.g., how to introduce a component, present equations, explain benefits)
2. Types of content to include (e.g., motivation, technical details, mathematical formulations)
3. Logical flow of technical presentations
4. Professional academic writing style

DO NOT:
- Follow the template word by word
- Copy its exact sentence structures
- Force your content to fit its specific format

Instead:
- Write naturally while incorporating similar elements (motivation, technical details, equations, etc.)
- Adapt the writing style to best present your specific technical content
- Maintain similar levels of technical depth and academic rigor

Requirements:
1. If current text exists:
   - Preserve valid technical content
   - Maintain consistent writing style
   - Add missing technical details
   - Improve clarity and organization
2. If starting from scratch:
   - Write comprehensive technical content
   - Follow academic writing conventions
3. In both cases:
   - Include necessary technical details from the new content
   - Ensure alignment with the structure's component descriptions
   - Use proper LaTeX formatting
   - Create smooth transitions
   - Focus on technical precision

Output the detailed LaTeX text for this subsection only."""

        return await self.gpt_client.chat(prompt=prompt)

    async def final_writing_checklist(self, methodology_text: str) -> str:
        """
        对已生成的方法论全文执行最终写作检查，包括学术风格、数学公式、标题优化等。

        :param methodology_text: 当前的方法论全文
        :return: 修订后的方法论全文（LaTeX）
        """
        prompt = f"""Review and revise the methodology section following these academic writing guidelines:

Current methodology text:
{methodology_text}

CHECKLIST FOR REVISION:

1. ACADEMIC WRITING STYLE:
   - Remove any markdown-style formatting
   - Remove any code-style documentation
   - Use formal academic language and terminology
   - Maintain consistent technical writing style throughout

2. MATHEMATICAL FORMULATION:
   - Verify correctness of all mathematical notations and equations
   - Ensure consistent variable naming
   - Check equation numbering and references
   - Avoid using too long plain text in equations

3. ACADEMIC WRITING WITH MATH:
   - Ensure that all important technical modules and mechanisms are described with math equations and well-defined math notations, even they have been well-described using natural languages
   - Avoid writing too simple math equations in non-inline equations. To address such cases, you may display 2 or 3 correlated simple equations together, or show more in-depth details for the mechanism using equations.

4. CONTENT FOCUS:
   - Reduce explanations of commonly known concepts
   - Use \cite{{}} for well-established methods instead of detailed explanations. If you don't know real papers to cite, you may also simplly describe what kind of references you are referring to.
   - Concentrate on novel contributions and key technical components
   - Ensure proper balance between overview and technical depth

5. SECTION TITLES:
   - Replace generic subsection titles with context-specific ones
   - Emphasize novelty and technical focus in titles
   - Reflect the specific application domain and unique aspects
   Examples:
   - Instead of "Embedding Layer" → "Context-Aware Knowledge Graph Embedding"
   - Instead of "Attention Mechanism" → "Cross-Modal Attention for Knowledge Integration"
   - Instead of "Loss Function" → "Multi-Task Knowledge Distillation Objective"
   - But remember don't make the titles too long, just 3-6 words is fine.

Output the revised methodology section incorporating all these improvements while maintaining the core technical content. Reply your latex without any additional explanations."""

        return await self.gpt_client.chat(prompt=prompt)

    async def compose_section(self, agent_dir: str, model_dir: str, benchmark_path: str, target_paper: str) -> str:
        """
        主流程：组合所有步骤，生成最终的方法论章节。

        :param agent_dir: Agent输出文件所在目录
        :param model_dir: 模型代码目录
        :param benchmark_path: 基准数据路径（此处未直接使用，但保留接口）
        :param target_paper: 论文标识（用于缓存和输出）
        :return: 最终的方法论LaTeX文本
        """
        # 设置检查点目录（用于断点续传）
        checkpoint_dir = self.get_checkpoint_path(target_paper)
        os.makedirs(checkpoint_dir, exist_ok=True)
        
        # 定义需要读取的Agent文件列表（按顺序处理）
        agent_files = [
            'prepare_agent.json',
            'survey_agent.json',
            'coding_plan_agent.json',
            'machine_learning_agent.json',
            'judge_agent.json',
            'machine_learning_agent_iter_submit.json',
            'experiment_analysis_agent_iter_refine_1.json',
            'machine_learning_agent_iter_refine_1.json',
        ]
        # 读取所有模型代码
        combined_code = self.read_model_code(model_dir)

        # -------- 步骤1: 迭代生成/修订结构 --------
        structure = ""
        structure_checkpoint = self.load_checkpoint(target_paper, "structure")
        
        if structure_checkpoint:
            # 如果已有结构检查点，直接加载
            structure = structure_checkpoint["final_structure"]
            logging.info("Loaded structure from checkpoint")
        else:
            # 否则进行迭代生成
            for iteration in range(self.structure_iterations):
                logging.info(f"Structure iteration {iteration + 1}/{self.structure_iterations}")
                
                # 先基于代码生成/修订结构
                structure = await self.generate_or_revise_structure(
                    combined_code, structure, iteration + 1)

                # 然后依次基于每个Agent文件的内容更新结构
                for idx, agent_file in enumerate(tqdm(agent_files, desc="Processing agent files")):
                    with open(os.path.join(agent_dir, agent_file), 'r') as f:
                        content = json.load(f) 
                    structure = await self.generate_or_revise_structure(
                        json.dumps(content, indent=2), structure, iteration + 1)
                
                # 保存本次迭代的临时日志
                self.write_temp_log(structure, f"iteration_{iteration+1}_final")
            
            # 保存最终结构到检查点
            self.save_checkpoint(target_paper, "structure", {
                "final_structure": structure
            })

        # -------- 步骤2: 细化各个子章节 --------
        # 从结构中提取所有 \subsection 的名称
        subsections = [line.split('{')[1].split('}')[0] 
                    for line in structure.split('\n') 
                    if line.strip().startswith('\\subsection')]
        
        subsection_contents = {}
        subsection_checkpoint = self.load_checkpoint(target_paper, "subsections")
        
        if subsection_checkpoint:
            # 如果有子章节检查点，直接加载
            subsection_contents = subsection_checkpoint
            logging.info("Loaded subsection contents from checkpoint")
        else:
            # 否则逐个细化子章节
            for subsection_id, subsection in enumerate(tqdm(subsections, desc="Detailizing subsections")):
                methodology_part = ''  # 当前子章节累积的文本
                
                # 先基于代码内容细化
                methodology_part = await self.detailize_subsection(
                    structure, methodology_part, combined_code, subsection)
                self.write_temp_log(
                    methodology_part,
                    f"subsection_{subsection_id}_code"
                )
                
                # 再依次基于每个Agent文件内容进行增量细化
                for i, agent_file in enumerate(agent_files):
                    with open(os.path.join(agent_dir, agent_file), 'r') as f:
                        content = json.load(f)
                    methodology_part = await self.detailize_subsection(
                        structure, methodology_part, json.dumps(content, indent=2), subsection)
                    
                    self.write_temp_log(
                        methodology_part,
                        f"subsection_{subsection_id}_agent_{i}"
                    )
                    
                    # 每处理一个Agent后立即保存检查点，以防中断
                    subsection_contents[subsection] = methodology_part
                    self.save_checkpoint(target_paper, "subsections", subsection_contents)

        # -------- 步骤3: 融合所有子章节 --------
        # 保存融合前的子章节内容，用于调试
        self.write_temp_log(
            json.dumps(subsection_contents, indent=2),
            "pre_fusion_subsections"
        )
        
        # 调用基类的 fuse_subsections 方法（可能来自 SectionComposer）合并各子章节
        fused_methodology = await self.fuse_subsections(structure, subsection_contents)
        self.write_temp_log(fused_methodology, "post_fusion_methodology")

        # -------- 步骤4: 最终写作检查 --------
        final_methodology = await self.final_writing_checklist(fused_methodology)
        self.write_temp_log(final_methodology, "post_checklist_methodology")

        # -------- 保存最终结果 --------
        output_dir = f"{self.research_field}/target_sections/{self.normalize_title(target_paper)}"
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, "methodology.tex")
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(final_methodology)
        logging.info(f"Saved final methodology to {output_path}")

        return final_methodology


async def methodology_composing(research_field: str, instance_id: str):
    """
    异步入口函数，用于启动方法论撰写流程。

    :param research_field: 研究领域（如 "vq"）
    :param instance_id: 实例ID（如 "rotation_vq"）
    """
    # 设置日志
    setup_logging(research_field)
    
    # 创建撰写器实例（此处迭代次数设为1，可调整）
    composer = MethodologyComposer(research_field=research_field, structure_iterations=1)
    
    # 构建项目目录路径
    proj_dir = f'./paper_agent/{research_field}/{instance_id}/'
    # 查找最新的 cache_* 目录
    cache_dirs = [d for d in os.listdir(proj_dir) if d.startswith('cache_')]
    if not cache_dirs:
        raise ValueError("No cache directory found")
    agent_dir = os.path.join(proj_dir, cache_dirs[-1], 'agents')
    
    model_dir = os.path.join(proj_dir, 'workplace/project/model/')
    benchmark_path = f'./benchmark/final/{research_field}/{instance_id}.json'
    
    try:
        methodology = await composer.compose_section(
            agent_dir, model_dir, benchmark_path, instance_id)
        logging.info("Methodology composition completed")
    except Exception as e:
        logging.error(f"Error during methodology composition: {str(e)}")
        raise


if __name__ == "__main__":
    import argparse
    from dotenv import load_dotenv

    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

    parser = argparse.ArgumentParser(description="单独生成 methodology 章节")
    parser.add_argument("--research_field", type=str, default="vq")
    parser.add_argument("--instance_id", type=str, default="rotation_vq")
    args = parser.parse_args()
    asyncio.run(methodology_composing(args.research_field, args.instance_id))