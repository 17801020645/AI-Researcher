import os
import json
import logging
from datetime import datetime
import random
from abc import ABC, abstractmethod
from typing import Dict, List, Optional
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from benchmark_collection.utils.openai_utils import GPTClient


def setup_logging(research_field):
    """为方法论组合过程初始化日志系统。"""
    os.makedirs(f"{research_field}/temp", exist_ok=True)
    os.makedirs(f"{research_field}/target_sections", exist_ok=True)
    os.makedirs(f"{research_field}/methodology_checkpoints", exist_ok=True)
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(f'{research_field}/methodology_composition.log'),
            logging.StreamHandler()]
    )


class SectionComposer(ABC):
    """用于撰写论文特定章节的抽象基类。

    提供加载基准数据、管理检查点、选择写作模板和融合子章节等通用工具。
    子类必须实现抽象方法以定义章节特定的生成逻辑。

    属性:
        gpt_client (GPTClient): 与语言模型交互的客户端。
        structure_iterations (int): 结构优化迭代次数。
        research_field (str): 研究领域标识符（用于文件路径）。
        section_name (str): 正在撰写的章节名称（如 'methodology'）。
        timestamp (str): 用于日志和临时文件的时间戳字符串。
    """

    def __init__(self, research_field: str, section_name: str,
                 structure_iterations: int = 3, gpt_model='gpt-4o-mini-2024-07-18'):
        """初始化 SectionComposer。

        参数:
            research_field: 研究领域标识，用于构建目录路径。
            section_name: 目标章节名称（如 'introduction'）。
            structure_iterations: 结构优化的最大迭代次数。
            gpt_model: GPTClient 使用的 GPT 模型标识。
        """
        self.gpt_client = GPTClient(model=gpt_model)
        self.structure_iterations = structure_iterations
        self.research_field = research_field
        self.section_name = section_name
        
        # 创建必要的目录
        self.setup_directories()
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    def setup_directories(self):
        """创建检查点、模板和输出所需的所有目录。"""
        directories = [
            f"{self.research_field}/temp",
            f"{self.research_field}/target_sections",
            f"{self.research_field}/{self.section_name}_checkpoints",
            f"{self.research_field}/writing_templates/{self.section_name}"
            # 如果需要，可取消下面这行的注释
            # f"{self.research_field}/target_sections/{self.section_name}"
        ]
        for directory in directories:
            os.makedirs(directory, exist_ok=True)

    def write_temp_log(self, content: str, step: str):
        """将中间结果写入带时间戳的临时日志文件。

        参数:
            content: 要写入的文本内容。
            step: 表示当前处理步骤的标签。
        """
        filename = f"{self.research_field}/temp/{self.timestamp}_{step}.log"
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(content)
        logging.info(f"已将中间结果写入 {filename}")

    def get_checkpoint_path(self, target_paper: str) -> str:
        """返回用于存储目标论文检查点的目录路径。

        参数:
            target_paper: 目标论文的标题。

        返回:
            表示检查点目录路径的字符串。
        """
        normalized_title = self.normalize_title(target_paper)
        return f"{self.research_field}/{self.section_name}_checkpoints/{normalized_title}"

    def save_checkpoint(self, target_paper: str, step: str, data: dict):
        """将字典保存为特定步骤的检查点 JSON 文件。

        参数:
            target_paper: 目标论文的标题。
            step: 处理步骤名（用作文件名）。
            data: 要存储的可序列化数据。
        """
        checkpoint_dir = self.get_checkpoint_path(target_paper)
        os.makedirs(checkpoint_dir, exist_ok=True)
        
        checkpoint_file = os.path.join(checkpoint_dir, f"{step}.json")
        with open(checkpoint_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        logging.info(f"已保存检查点: {checkpoint_file}")

    def load_checkpoint(self, target_paper: str, step: str) -> Optional[Dict]:
        """加载先前保存的检查点（如果存在）。

        参数:
            target_paper: 目标论文的标题。
            step: 处理步骤名。

        返回:
            检查点字典，如果未找到则返回 None。
        """
        checkpoint_file = os.path.join(
            self.get_checkpoint_path(target_paper), 
            f"{step}.json"
        )
        if os.path.exists(checkpoint_file):
            with open(checkpoint_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return None

    def normalize_title(self, title: str) -> str:
        """将论文标题转换为文件系统安全的名称。

        将空格替换为下划线，并转换为小写。

        参数:
            title: 原始论文标题。

        返回:
            适合文件/目录名称的规范化字符串。
        """
        return '_'.join(title.lower().split())

    def load_benchmark_data(self, json_path: str, target_paper: str) -> List[Dict]:
        """从基准数据中加载与目标论文关联的源论文。

        参数:
            json_path: 基准 JSON 文件的路径。
            target_paper: 要查找的目标论文标题。

        返回:
            源论文字典列表。如果未找到则返回空列表。
        """
        with open(json_path, 'r') as f:
            data = json.load(f)
        
        # 查找与目标论文匹配的条目（不区分大小写）
        for item in data:
            if item['target'].lower() == target_paper.lower():
                return item['source_papers']
        return []

    def get_random_template(self) -> str:
        """从该章节的模板目录中随机选择一个写作模板。

        返回:
            所选模板的内容字符串。如果没有可用模板则返回空字符串。
        """
        template_dir = f"{self.research_field}/writing_templates/{self.section_name}"
        template_files = [f for f in os.listdir(template_dir) if f.endswith('_template.txt')]
        if not template_files:
            logging.warning("未找到任何模板，将在无模板的情况下继续。")
            return ""
        
        selected_template = random.choice(template_files)
        try:
            with open(os.path.join(template_dir, selected_template), 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            logging.error(f"读取模板 {selected_template} 时出错: {str(e)}")
            return ""

    @abstractmethod
    async def generate_or_revise_structure(self, content: str, current_structure: str,
                                          iteration: int) -> str:
        """为章节生成新的结构或修订现有结构。

        子类必须实现此方法以定义迭代逻辑。

        参数:
            content: 可用内容（如源论文摘要）。
            current_structure: 当前结构（开始时可以为空）。
            iteration: 当前迭代次数。

        返回:
            生成或修订后的章节结构字符串。
        """
        pass

    @abstractmethod
    async def detailize_subsection(self, structure: str, current_text: str,
                                   content: str, subsection: str) -> str:
        """将特定子章节扩展为详细文本。

        参数:
            structure: 整体章节结构。
            current_text: 子章节的当前文本（可能为空）。
            content: 用于生成的可用内容。
            subsection: 要详细描述的子章节标识。

        返回:
            给定子章节的详细文本。
        """
        pass

    @abstractmethod
    async def final_writing_checklist(self, section_text: str) -> str:
        """使用检查清单对完整章节进行最终修订。

        参数:
            section_text: 要修订的完整章节文本。

        返回:
            修订后的章节文本。
        """
        pass

    async def fuse_subsections(self, structure: str, subsection_contents: Dict[str, str]) -> str:
        """将单独详细的子章节合并为一个连贯的章节。

        每个子章节的内容将被严格保留；只添加必要的 LaTeX 格式和结构元素。

        参数:
            structure: 计划好的章节结构。
            subsection_contents: 从子章节标识符到其文本的映射。

        返回:
            完整的融合后章节字符串。
        """
        # 构建提示词，要求模型严格保留内容
        prompt = f"""Combine the following subsections into a complete {self.section_name} section according to the established structure.
    The content of each subsection MUST BE PRESERVED EXACTLY as provided.

    Established structure:
    {structure}

    Subsection contents:
    {json.dumps(subsection_contents, indent=2)}

    Requirements:
    1. STRICT CONTENT PRESERVATION:
    - Keep ALL content within each subsection exactly as provided
    - Maintain all LaTeX commands, equations, and formatting
    - Preserve all citations and references

    2. STRUCTURE ADHERENCE:
    - Follow the established structure exactly
    - Include all section/subsection/subsubsection headers
    - Maintain the hierarchy of sections
    - Keep all comments from the structure

    3. FUSION GUIDELINES:
    - Only add necessary LaTeX formatting for proper section combination
    - Do not modify any technical content
    - Ensure proper spacing between sections
    - Maintain consistent formatting throughout

    Output the complete {self.section_name} section with all subsections properly combined."""

        return await self.gpt_client.chat(prompt=prompt)

    @abstractmethod
    async def compose_section(self, agent_dir: str, model_dir: str,
                              benchmark_path: str, target_paper: str) -> str:
        """为目标论文撰写整个章节的主入口方法。

        子类必须协调整个生成过程（结构、子章节详细描述、融合以及最终检查清单）。

        参数:
            agent_dir: 包含代理相关数据的目录。
            model_dir: 包含模型相关数据的目录。
            benchmark_path: 基准 JSON 文件的路径。
            target_paper: 目标论文的标题。

        返回:
            撰写完成的章节字符串。
        """
        pass