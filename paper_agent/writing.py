# ==================== 导入必要的模块 ====================
# 各章节撰写模块（基于模板）
from paper_agent.methodology_composing_using_template import methodology_composing
from paper_agent.related_work_composing_using_template import related_work_composing
from paper_agent.experiments_composing import experiments_composing
from paper_agent.introduction_composing import introduction_composing
from paper_agent.conclusion_composing import conclusion_composing
from paper_agent.abstract_composing import abstract_composing

import asyncio          # 异步IO支持
import argparse         # 命令行参数解析
from paper_agent.writing_fix import clean_tex_files_in_folder, process_tex_file  # LaTeX清理与处理工具
from paper_agent.tex_writer import compile_latex_project  # LaTeX项目编译工具


# ==================== 核心撰写流程（异步） ====================
async def writing(research_field: str, instance_id: str):
    """
    按顺序执行论文各章节的撰写任务，然后进行LaTeX文件清理、引用处理及编译。

    Args:
        research_field (str): 研究领域名称（用于定位目录）
        instance_id (str): 实例标识（如方法名称，用于区分不同实验）
    """
    # ---------- 按顺序生成各个章节 ----------
    # 方法部分（Methodology）
    await methodology_composing(research_field, instance_id)
    # 相关工作（Related Work）
    await related_work_composing(research_field, instance_id)
    # 实验部分（Experiments）
    await experiments_composing(research_field, instance_id)
    # 引言（Introduction）
    await introduction_composing(research_field, instance_id)
    # 结论（Conclusion）
    await conclusion_composing(research_field, instance_id)
    # 摘要（Abstract）——通常最后撰写，以确保覆盖全文要点
    await abstract_composing(research_field, instance_id)

    # ---------- 后处理与编译 ----------
    # 设定目标文件夹路径（存放所有章节TeX文件）
    target_folder = f"{research_field}/target_sections/{instance_id}"

    # 清理文件夹中多余的临时文件或不合规的TeX标记
    clean_tex_files_in_folder(target_folder)

    # 处理相关工作的参考文献引用：将文中引用与bib文件关联，修正格式
    tex_file_path = f'{research_field}/target_sections/{instance_id}/related_work.tex'
    bib_file_path = f'{research_field}/target_sections/{instance_id}/iclr2025_conference.bib'
    process_tex_file(tex_file_path, bib_file_path)

    # 编译整个LaTeX项目，生成最终PDF
    project_directory = f'{research_field}/target_sections/{instance_id}'
    main_file = "iclr2025_conference.tex"   # 主TeX文件（通常包含所有章节）
    compile_latex_project(project_directory, main_file)


# ==================== 命令行入口 ====================
if __name__ == "__main__":
    # 解析命令行参数，允许用户指定研究领域和实例ID
    parser = argparse.ArgumentParser(description="自动生成论文各章节并编译为PDF")
    parser.add_argument("--research_field", type=str, default="vq",
                        help="研究领域名称（默认为'vq'）")
    parser.add_argument("--instance_id", type=str, default="rotation_vq",
                        help="实例标识（默认为'rotation_vq'）")
    args = parser.parse_args()

    # 启动异步撰写流程
    asyncio.run(writing(args.research_field, args.instance_id))