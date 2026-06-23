import os
import json
import asyncio
import logging
from tqdm import tqdm
import sys

# 添加项目根目录到 sys.path，以便导入自定义模块
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from benchmark_collection.utils.openai_utils import GPTClient
from paper_agent.section_composer import SectionComposer, setup_logging


class RelatedWorkComposer(SectionComposer):
    """
    相关工作章节撰写器，继承自 SectionComposer。
    负责生成、优化和细化论文中“Related Work”部分的 LaTeX 结构及内容。
    """

    def __init__(self, research_field: str, structure_iterations: int = 3):
        """
        初始化相关工作撰写器。

        Args:
            research_field (str): 研究领域名称，用于路径和上下文。
            structure_iterations (int): 结构生成的迭代次数，默认为3。
        """
        super().__init__(research_field, "related_work", structure_iterations)

    async def generate_or_revise_structure(self, content: str, current_structure: str, iteration: int) -> str:
        """
        根据提供的素材生成或修订相关工作的章节结构（LaTeX 格式）。

        Args:
            content (str): 用于分析的内容（如代理输出或论文摘要）。
            current_structure (str): 当前已有的结构（可能为空或部分结构）。
            iteration (int): 当前迭代次数。

        Returns:
            str: 生成的 LaTeX 结构（包含章节和子章节及注释）。
        """
        prompt = f"""Based on the given content, generate or revise the related work structure, using latex format.
Current iteration: {iteration}/{self.structure_iterations}

Current structure (if exists):
{current_structure}

Content to analyze:
{content}

Guidelines for structure generation:
1. SECTION ORGANIZATION:
   - Main section should be "Related Work" (with latex command \section{{Related Work}})
   - Use 2-3 subsections for different research directions/categories
   - Group related papers logically under each subsection
   - Ensure proper flow from foundational to advanced topics

2. SECTION HIERARCHY:
   - Use subsections for major research directions
   - Group papers by methodology or approach
   - Maintain chronological order within groups when relevant

3. REQUIRED COMMENTS:
   Add latex comments (start with %) under each section/subsection to explain:

   For Related Work section:
   - Overview of the research landscape
   - Key research directions and their relationships
   - Evolution of the field
   - Connection to the proposed work

   For each subsection:
   - Key papers and their contributions
   - Technical approaches and methodologies
   - Current limitations and challenges
   - Relevance to the proposed work

4. STRUCTURE FORMAT:
   \section{{Related Work}}

   \subsection{{Related Research Direction 1}}
   % [Key approaches and limitations]
   % [Connection to modern approaches]
   
   \subsection{{Related Research Direction 2}}
   % [Key architectures and innovations]
   % [Remaining challenges]
   
   \subsection{{Related Research Direction 3}}
   % [Recent innovations]
   % [Future directions]

   % Do not use \subsubsection

Output only the LaTeX structure with comments as specified above."""

        # 调用 GPT 客户端生成结构
        return await self.gpt_client.chat(prompt=prompt)

    async def detailize_subsection(self, structure: str, current_text: str, content: str, subsection: str) -> str:
        """
        细化某一个子章节的内容，将新信息融入已有文本。

        Args:
            structure (str): 当前整体结构（包含所有子章节标题和注释）。
            current_text (str): 该子章节当前已有文本（可能为空）。
            content (str): 待融入的新内容（如论文原文或代理输出）。
            subsection (str): 子章节名称（例如 "Graph Neural Networks"）。

        Returns:
            str: 更新后的该子章节 LaTeX 文本。
        """
        writing_template = self.get_random_template()  # 随机获取一个写作模板

        prompt = f"""Write or revise the following subsection of the related work:
\subsection{{{subsection}}}

CURRENT TEXT (if any):
{current_text}

STRUCTURE INFORMATION:
{structure}

NEW CONTENT TO INCORPORATE:
{content}

REFERENCE WRITING TEMPLATE:
{writing_template}

Requirements for related work writing:
1. PAPER ORGANIZATION:
   - Group papers by methodology/approach
   - Present chronological development
   - Highlight key contributions
   - Show evolution of ideas

2. CRITICAL ANALYSIS:
   - Compare different approaches
   - Identify strengths and limitations
   - Discuss technical innovations
   - Note remaining challenges

3. WRITING STYLE:
   - Use clear transitions between papers
   - Maintain objective tone
   - Balance detail level
   - Ensure technical accuracy

4. CITATIONS:
   - Find as many references as you can from the new content
   - Don't cite papers that do not exist
   - Use proper citation format
   - Group related citations
   - Cite seminal works
   - Include recent developments

5. TECHNICAL CONTENT:
   - Focus on methodological aspects
   - Highlight key innovations
   - Discuss technical limitations
   - Connect to your work

Output the detailed LaTeX text for this subsection only."""

        return await self.gpt_client.chat(prompt=prompt)

    async def final_writing_checklist(self, related_work_text: str) -> str:
        """
        对生成的相关工作章节进行最终质量检查，并返回修订后的版本。

        Args:
            related_work_text (str): 当前相关工作章节的完整 LaTeX 文本。

        Returns:
            str: 经过检查与修正后的最终 LaTeX 文本。
        """
        prompt = f"""Review and revise the related work section following these academic writing guidelines:

Current related work text:
{related_work_text}

CHECKLIST FOR REVISION:

1. \section{{Related Work}} is directly followed by the subsections, without section-level text.
2. Each subsection first discusses the related works, and then shortly discusses the relative contribution of our work. No other content.
3. Discussion on related works should have at least two times the length of the discussion on the contribution of our work.
4. Each subsection should cite at least 4 papers, and at most 10 papers.
5. Each subsection should contains one to two paragraphs.
6. No equations
7. Properly cite the related works using the \cite{{}} command
8. List all reference papers with all publication information at the end, in the bibtex format.

Output the revised related work section incorporating all these improvements. Reply with LaTeX code only."""

        return await self.gpt_client.chat(prompt=prompt)

    def read_related_papers(self, papers_dir):
        """
        从指定目录读取所有相关论文文件（.txt 或 .json），返回内容列表。

        Args:
            papers_dir (str): 存放论文文件的目录路径。

        Returns:
            list: 每个元素为包含 'filename' 和 'content' 的字典。
        """
        papers_content = []
        for filename in os.listdir(papers_dir):
            if filename.endswith('.txt') or filename.endswith('.json'):
                try:
                    with open(os.path.join(papers_dir, filename), 'r', encoding='utf-8') as f:
                        content = f.read()
                        papers_content.append({
                            'filename': filename,
                            'content': content
                        })
                except Exception as e:
                    logging.error(f"Error reading paper file {filename}: {str(e)}")
        return papers_content

    async def compose_section(self, agent_dir: str, papers_dir: str, benchmark_path: str, target_paper: str) -> str:
        """
        完整的相关工作章节撰写流程：结构迭代生成 -> 逐个子章节细化 -> 融合 -> 最终检查。

        Args:
            agent_dir (str): 代理输出文件（JSON）所在目录。
            papers_dir (str): 相关论文文件所在目录。
            benchmark_path (str): 基准数据路径（本方法中未直接使用，保留接口）。
            target_paper (str): 目标论文标识（用于构建检查点路径）。

        Returns:
            str: 最终生成的相关工作章节完整 LaTeX 代码。
        """
        # ==================== 0. 初始化：创建检查点目录、定义代理文件、读取论文 ====================
        # 根据 target_paper 构建该论文专属的检查点目录，用于断点续跑
        checkpoint_dir = self.get_checkpoint_path(target_paper)
        os.makedirs(checkpoint_dir, exist_ok=True)

        # 指定需要读取的代理输出文件（JSON 格式，内含模型生成的半结构化内容）
        # 这里只启用与文献综述相关的代理文件，其他暂时注释掉
        agent_files = [
            'prepare_agent.json',
            'survey_agent.json',
            # 'coding_plan_agent.json',
            # 'machine_learning_agent.json',
            # 'judge_agent.json',
            # 'machine_learning_agent_iter_submit.json',
            # 'experiment_analysis_agent_iter_refine_1.json',
            # 'machine_learning_agent_iter_refine_1.json',
        ]

        # 从 papers_dir 中读取所有相关论文的原始内容（返回列表，每个元素可能包含标题、摘要、全文等）
        related_papers = self.read_related_papers(papers_dir)
        logging.info(f"Found {len(related_papers)} related papers in {papers_dir}")

        # ==================== 步骤1: 迭代生成/修订整体结构 ====================
        # 结构（structure）是一个 LaTeX 文本骨架，只包含 \section{Related Work} 及其下的 \subsection{...} 列表
        structure = ""
        # 尝试加载之前可能保存的结构检查点，实现中断恢复
        structure_checkpoint = self.load_checkpoint(target_paper, "structure")

        if structure_checkpoint:
            # 已有检查点：直接使用之前保存的最终结构，跳过迭代生成
            structure = structure_checkpoint["final_structure"]
            logging.info("Loaded structure from checkpoint")
        else:
            # 无检查点：进行多轮结构迭代（由 self.structure_iterations 控制轮次）
            for iteration in range(self.structure_iterations):
                logging.info(f"Structure iteration {iteration + 1}/{self.structure_iterations}")

                # 每一轮都将所有代理文件的内容依次喂给结构生成/修正方法
                for idx, agent_file in enumerate(tqdm(agent_files, desc="Processing agent files")):
                    # 读取代理输出的 JSON
                    with open(os.path.join(agent_dir, agent_file), 'r') as f:
                        content = json.load(f)
                    # 调用异步方法，传入当前结构、本次代理内容、迭代轮次，逐步修订整体结构
                    structure = await self.generate_or_revise_structure(
                        json.dumps(content, indent=2), structure, iteration + 1)

                # 每轮迭代结束后，保存一个临时日志文件，方便调试和观察中间结果
                self.write_temp_log(structure, f"iteration_{iteration+1}_final")

            # 迭代全部完成后，将最终结构存入检查点，下次运行可跳过此步
            self.save_checkpoint(target_paper, "structure", {
                "final_structure": structure
            })

        # ==================== 步骤2: 逐个子章节细化内容 ====================
        # 从结构中解析出所有 \subsection{...} 的子章节名称
        subsections = [line.split('{')[1].split('}')[0]
                    for line in structure.split('\n')
                    if line.strip().startswith('\\subsection')]

        subsection_contents = {}          # 用于存储每个子章节最终生成的内容文本
        # 尝试加载子章节内容检查点
        subsection_checkpoint = self.load_checkpoint(target_paper, "subsections")

        if subsection_checkpoint:
            # 已有检查点：直接恢复所有子章节内容，跳过细化过程
            subsection_contents = subsection_checkpoint
            logging.info("Loaded subsection contents from checkpoint")
        else:
            # 对每一个子章节单独进行内容生成
            for subsection_id, subsection in enumerate(tqdm(subsections, desc="Detailizing subsections")):
                related_work_part = ''    # 该子章节的累积文本，初值为空

                # ---- 2.1 先利用代理文件中的信息细化当前子章节 ----
                for i, agent_file in enumerate(agent_files):
                    with open(os.path.join(agent_dir, agent_file), 'r') as f:
                        content = json.load(f)
                    # 异步方法：在当前结构、已积累文本、新代理信息的基础上，细化名为 subsection 的子章节
                    related_work_part = await self.detailize_subsection(
                        structure, related_work_part, json.dumps(content, indent=2), subsection)

                    # 保存中间结果到临时日志，便于追踪每一步的变化
                    self.write_temp_log(
                        related_work_part,
                        f"subsection_{subsection_id}_agent_{i}"
                    )

                # ---- 2.2 再利用相关论文的原始内容继续细化同一个子章节 ----
                for i, paper in enumerate(tqdm(related_papers, desc=f"Processing related papers for subsection {subsection}")):
                    related_work_part = await self.detailize_subsection(
                        structure, related_work_part, paper['content'], subsection)

                    self.write_temp_log(
                        related_work_part,
                        f"subsection_{subsection_id}_paper_{i}"
                    )

                    # 每处理完一篇论文，就立即将当前子章节的内容保存到检查点（覆盖模式）
                    # 这保证了即使中途中断，已完成的子章节内容也不会丢失
                    subsection_contents[subsection] = related_work_part
                    self.save_checkpoint(target_paper, "subsections", subsection_contents)

        # ==================== 步骤3: 融合所有子章节 ====================
        # 记录融合前的各子章节完整内容，方便回溯
        self.write_temp_log(
            json.dumps(subsection_contents, indent=2),
            "pre_fusion_subsections"
        )

        # 调用融合方法，根据整体结构 structure 和每个子章节的内容，组装成一个完整的 Related Work 章节
        fused_related_work = await self.fuse_subsections(structure, subsection_contents)
        self.write_temp_log(fused_related_work, "post_fusion_related_work")

        # ==================== 步骤4: 最终质量检查与修订 ====================
        # 使用严格的学术写作清单对整合后的章节进行最终审查和润色（即上一轮对话中分析的 final_writing_checklist）
        final_related_work = await self.final_writing_checklist(fused_related_work)
        self.write_temp_log(final_related_work, "post_checklist_related_work")

        # ==================== 5. 保存最终输出 ====================
        # 构建输出目录： research_field/target_sections/<标准化的论文标题>/
        output_dir = f"{self.research_field}/target_sections/{self.normalize_title(target_paper)}"
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, "related_work.tex")

        # 将最终 LaTeX 代码写入文件
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(final_related_work)
        logging.info(f"Saved final related work to {output_path}")

        # 同时返回字符串给调用方
        return final_related_work


async def related_work_composing(research_field: str, instance_id: str):
    """
    异步入口函数，用于启动相关工作章节的撰写流程。

    Args:
        research_field (str): 研究领域。
        instance_id (str): 论文实例标识（通常为论文标题或唯一 ID）。
    """
    setup_logging(research_field)  # 配置日志

    composer = RelatedWorkComposer(research_field=research_field, structure_iterations=1)

    # 构造项目目录路径（注意：这里使用了相对路径，可根据实际情况调整）
    proj_dir = f'./paper_agent/{research_field}/{instance_id}/'
    # 查找以 'cache_' 开头的子目录，取最新（按字母序最后一个）作为代理输出目录
    cache_dirs = [d for d in os.listdir(proj_dir) if d.startswith('cache_')]
    if not cache_dirs:
        raise ValueError("No cache directory found")
    agent_dir = os.path.join(proj_dir, cache_dirs[-1], 'agents')

    # 基准数据路径（本示例中未使用，但保留作为接口）
    benchmark_path = f'./benchmark/final/{research_field}/{instance_id}.json'
    papers_dir = os.path.join(proj_dir, 'workplace', 'papers')

    try:
        related_work = await composer.compose_section(
            agent_dir, papers_dir, benchmark_path, instance_id)
        logging.info("Related work composition completed")
    except Exception as e:
        logging.error(f"Error during related work composition: {str(e)}")
        raise


if __name__ == "__main__":
    # 程序入口：运行异步撰写函数
    asyncio.run(related_work_composing())