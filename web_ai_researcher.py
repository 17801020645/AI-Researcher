from main_ai_researcher import main_ai_researcher
import os
import gradio as gr
import time
import json
import logging
import datetime
from typing import Tuple
import importlib
from dotenv import load_dotenv, set_key, find_dotenv, unset_key
import threading
import queue
import re
import random
import global_state
import base64

# 设置标准输出编码为UTF-8，避免中文乱码
os.environ["PYTHONIOENCODING"] = "utf-8"

# 如果需要使用代理，取消下面三行的注释
os.environ['https_proxy'] = 'http://100.68.161.73:3128'
os.environ['http_proxy'] = 'http://100.68.161.73:3128'
os.environ['no_proxy'] = 'localhost,127.0.0.1,0.0.0.0'

def setup_path():
    """创建日志目录并生成日志文件路径（用于特定的日志存储）"""
    logs_dir = os.path.join("casestudy_results", f'agent', 'logs')
    os.makedirs(logs_dir, exist_ok=True)

    current_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_file = os.path.join(logs_dir, f"gradio_log_{current_date}.log")
    return log_file


def setup_logging():
    """
    配置根日志记录器，同时输出到控制台和文件。
    返回日志文件的路径，并将其记录到 global_state.LOG_PATH。
    """
    logs_dir = os.path.join(os.path.dirname(__file__), "logs")
    os.makedirs(logs_dir, exist_ok=True)
    current_date = datetime.datetime.now().strftime("%Y-%m-%d %H-%M-%S")
    log_file = os.path.join(logs_dir, f"log_{current_date}.log")
    global_state.LOG_PATH = log_file

    root_logger = logging.getLogger()

    # 清除已有的处理器，防止重复记录
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    root_logger.setLevel(logging.INFO)

    file_handler = logging.FileHandler(log_file, encoding="utf-8", mode="a")
    file_handler.setLevel(logging.INFO)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    logging.info("Logging system initialized, log file: %s", log_file)
    # 屏蔽第三方库的冗余日志
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("LiteLLM").setLevel(logging.WARNING)
    return log_file


def return_log_file():
    """返回主日志文件路径，供下载按钮使用"""
    return LOG_FILE

def return_paper_file():
    """返回论文PDF文件路径（从环境变量中获取类别和实例ID）"""
    category = os.getenv("CATEGORY")
    instance_id = os.getenv("INSTANCE_ID")
    global PAPER_FILE
    PAPER_FILE = f'{category}/target_sections/{instance_id}/iclr2025_conference.pdf'
    return PAPER_FILE

def return_paper_log_file():
    """返回论文生成日志文件路径（已弃用？）"""
    return PAPER_LOG

def return_paper_log():
    """配置并返回论文代理的日志文件路径"""
    logs_dir = os.path.join(os.path.dirname(__file__), "paper_agent", "paper_logs")
    os.makedirs(logs_dir, exist_ok=True)

    current_date = datetime.datetime.now().strftime("%Y-%m-%d %H-%M-%S")
    log_file = os.path.join(logs_dir, f"rotated_vq_{current_date}.log")

    global_state.LOG_PATH = log_file

    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    root_logger.setLevel(logging.INFO)

    file_handler = logging.FileHandler(log_file, encoding="utf-8", mode="a")
    file_handler.setLevel(logging.INFO)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    logging.info("Logging system initialized, log file: %s", log_file)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("LiteLLM").setLevel(logging.WARNING)
    return log_file


def get_latest_log():
    """读取当前日志文件内容并复制到临时文件，供前端下载"""
    path2save = os.path.splitext(os.path.basename(LOG_FILE))[0]
    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            content = f.read()
        temp_file = f"{path2save}_copy.log"
        with open(temp_file, "w", encoding="utf-8") as f:
            f.write(content)
        return temp_file
    except Exception as e:
        print(f"Error reading log file: {e}")
        return None


def get_base64_image(image_path):
    """将图片编码为base64，用于在HTML中内嵌显示"""
    with open(image_path, "rb") as image_file:
        encoded = base64.b64encode(image_file.read()).decode("utf-8")
    return f"data:image/png;base64,{encoded}"


# ================== 全局变量 ==================
LOG_FILE = None
LOG_READ_FILE = None
PAPER_LOG = None
category = os.getenv("CATEGORY")
instance_id = os.getenv("INSTANCE_ID")

PAPER_FILE = f'{category}/target_sections/{instance_id}/iclr2025_conference.pdf'

LOG_QUEUE: queue.Queue = queue.Queue()          # 用于在线程间传递日志行
STOP_LOG_THREAD = threading.Event()             # 控制日志读取线程停止
CURRENT_PROCESS = None
STOP_REQUESTED = threading.Event()


# ================== 日志读取线程 ==================
def log_reader_thread(log_file):
    """
    后台线程，持续读取日志文件的新增内容，并将每行放入 LOG_QUEUE。
    用于实现实时日志更新。
    """
    try:
        with open(log_file, "r", encoding="utf-8") as f:
            f.seek(0, 2)   # 移动到文件末尾
            while not STOP_LOG_THREAD.is_set():
                line = f.readline()
                if line:
                    LOG_QUEUE.put(line)
                else:
                    time.sleep(0.1)
    except Exception as e:
        logging.error(f"Exception occurred in background log reader thread: {str(e)}")


# ================== 日志解析核心函数 ==================
def parse_logs_incrementally(logs, state_list, last_index):
    """
    增量解析日志行，将原始的日志文本转换为结构化的对话列表。
    主要处理状态机：识别用户输入、助手回复、工具调用、工具执行等。
    返回更新后的 state_list（对话列表）和新的 last_index。

    参数:
        logs: 日志行列表（新增加的部分）
        state_list: 当前已有的对话列表，元素为 (user_msg, bot_msg) 元组
        last_index: 上次处理的日志行索引

    返回:
        (更新后的state_list, 新的last_index)
    """
    # 用于去重的集合，避免重复添加相同的对话对
    existing_inputs = set()
    existing_pairs = set()
    for input_text, output_text in state_list:
        existing_pairs.add((input_text.strip(), output_text.strip()))
        existing_inputs.add(input_text.strip())

    conversations = []          # 临时存放解析出的完整对话
    current_convo = None        # 当前正在构建的对话对象
    state = "idle"              # 状态机初始状态

    new_logs = logs[last_index:]   # 只处理新增部分
    new_last_index = last_index + len(new_logs)

    # 定义需要显示的工具名称（白名单）
    allowed_tools = {
        "execute_command", "run_python", "create_file",
        "write_file", "list_files", "gen_code_tree_structure"
    }

    def adjust_markdown_headers(content):
        """
        调整markdown标题级别，将1-3级标题提升为4-6级，
        避免与页面主标题冲突，保持视觉层次。
        """
        lines = content.split('\n')
        adjusted_lines = []
        for line in lines:
            if line.strip().startswith('#'):
                header_level = 0
                for char in line:
                    if char == '#':
                        header_level += 1
                    else:
                        break
                if header_level <= 3:
                    adjusted_line = '#' * (header_level + 3) + line[header_level:]
                    adjusted_lines.append(adjusted_line)
                else:
                    adjusted_lines.append(line)
            else:
                adjusted_lines.append(line)
        return '\n'.join(adjusted_lines)

    # ---------- 状态机解析 ----------
    for line in new_logs:
        line = line.strip()

        # 检测到新对话的开始（用户任务或助手消息）
        if "Receive Task" in line or "Assistant Message" in line:
            if current_convo:
                conversations.append(current_convo)
            current_convo = {
                "user_time": None,
                "user_content": "",
                "assistant_time": None,
                "assistant_role": None,
                "assistant_content": "",
                "tool_calls_time": None,
                "tool_calls_content": "",
                "tool_execution_time": None,
                "tool_execution_content": "",
                "current_tool_name": None
            }
            if "Receive Task" in line:
                state = "await_user_time"
            else:
                state = "await_assistant_time"

        elif current_convo is not None:
            # 等待用户时间戳
            if state == "await_user_time" and line.startswith("["):
                current_convo["user_time"] = line.strip("[]")
                state = "await_user_input"
            # 等待用户输入内容
            elif state == "await_user_input" and line.lower().startswith("receiveing the task:"):
                state = "user_content"
            elif state == "user_content" and not line.startswith("*"):
                current_convo["user_content"] += line + "\n"

            # 等待助手时间戳
            elif state == "await_assistant_time" and line.startswith("["):
                current_convo["assistant_time"] = line.strip("[]")
                state = "await_assistant_role"
            # 解析助手角色和内容
            elif state == "await_assistant_role":
                if ":" in line:
                    parts = line.split(":", 1)
                    role = parts[0].strip()
                    content_line = parts[1].strip() + "\n"
                else:
                    role = "assistant"
                    content_line = line + "\n"
                current_convo["assistant_role"] = role
                current_convo["assistant_content"] += content_line
                state = "assistant_content"
            # 继续读取助手内容，直到遇到特殊标记
            elif state == "assistant_content":
                if "Tool Calls" in line:
                    state = "await_tool_calls_time"
                elif "Tool Execution" in line:
                    state = "await_tool_execution_time"
                elif "End Turn" in line:
                    conversations.append(current_convo)
                    current_convo = None
                    state = "idle"
                else:
                    current_convo["assistant_content"] += line + "\n"

            # 工具调用时间戳
            elif state == "await_tool_calls_time" and line.startswith("["):
                current_convo["tool_calls_time"] = line.strip("[]")
                state = "tool_calls_content"
            # 工具调用内容
            elif state == "tool_calls_content":
                if "Tool Execution" in line:
                    state = "await_tool_execution_time"
                elif "End Turn" in line:
                    conversations.append(current_convo)
                    current_convo = None
                    state = "idle"
                else:
                    current_convo["tool_calls_content"] += line + "\n"
                    # 尝试提取工具名称
                    if "tool execution:" in line.lower():
                        tool_name = line.split(":")[-1].strip()
                        current_convo["current_tool_name"] = tool_name

            # 工具执行时间戳
            elif state == "await_tool_execution_time" and line.startswith("["):
                current_convo["tool_execution_time"] = line.strip("[]")
                state = "tool_execution_content"
            # 工具执行结果
            elif state == "tool_execution_content":
                if "End Turn" in line:
                    conversations.append(current_convo)
                    current_convo = None
                    state = "idle"
                else:
                    current_convo["tool_execution_content"] += line + "\n"

    # 如果还有未结束的对话，将其加入
    if current_convo:
        conversations.append(current_convo)

    # ---------- 将解析出的对话转换为UI可用的格式 ----------
    for convo in conversations:
        section_input = ""
        section_output = ""

        if convo["user_content"].strip():
            section_input = f"### 🙋 User ({convo['user_time']})\n```markdown\n{convo['user_content'].strip()}\n```"
        else:
            section_input = ""

        input_clean = section_input.strip()

        # 如果该输入尚未存在，则先添加一个占位
        if (input_clean, "") not in existing_pairs:
            state_list.append((input_clean, ""))
            existing_inputs.add(input_clean)
            existing_pairs.add((input_clean, ""))

        output_parts = []

        # 助手回复
        if convo["assistant_content"].strip():
            assistant_content = convo["assistant_content"].strip()
            if assistant_content.lower() == "none":
                assistant_content = ""
            output_parts.append(
                f"### 🤖 {convo['assistant_role']} ({convo['assistant_time']})\n{adjust_markdown_headers(assistant_content)}"
            )
        # 工具调用（显示为python代码块）
        if convo["tool_calls_content"].strip():
            output_parts.append(
                f"### 🛠️ Tool Calls\n```python\n{convo['tool_calls_content'].strip()}\n```"
            )

        # 工具执行结果（仅白名单内工具，显示为markdown代码块）
        if convo["tool_execution_content"].strip():
            tool_name = convo.get("current_tool_name", "")
            if not tool_name:
                for line in convo["tool_execution_content"].split('\n'):
                    if "tool execution:" in line.lower():
                        tool_name = line.split(":")[-1].strip()
                        break
            if tool_name in allowed_tools:
                tool_execution_content = convo["tool_execution_content"].strip()
                output_parts.append(
                    f"### ⚙️ Tool Execution\n```markdown\n{tool_execution_content}\n```"
                )

        if output_parts:
            section_output = "\n\n".join(output_parts)
            # 更新已有的占位条目
            for i in reversed(range(len(state_list))):
                user, bot = state_list[i]
                if user.strip() == input_clean and not bot.strip():
                    new_pair = (user, section_output.strip())
                    if new_pair not in existing_pairs:
                        state_list[i] = new_pair
                        existing_pairs.add(new_pair)
                    break

    return state_list, new_last_index


def get_latest_logs(max_lines=500, state=None, queue_source=None, last_index=0):
    """
    从队列或直接读取日志文件，获取最新日志并解析成对话列表。
    若队列有数据则优先取队列，否则读取文件全部内容。
    返回 (更新后的state_list, 新的last_index)。
    """
    logs = []
    log_queue = queue_source if queue_source else LOG_QUEUE
    temp_queue = queue.Queue()
    temp_logs = []

    # 从队列中取出所有日志（非阻塞）
    try:
        while not log_queue.empty():
            log = log_queue.get_nowait()
            temp_logs.append(log)
            temp_queue.put(log)
    except queue.Empty:
        pass

    logs = temp_logs

    # 如果队列为空或文件更新，则从文件读取全部内容（作为后备）
    if LOG_FILE and os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                all_lines = f.readlines()
                logs = all_lines   # 覆盖队列数据，保证完整
        except Exception as e:
            error_msg = f"Error reading log file: {str(e)}"
            logging.error(error_msg)
            if not logs:
                logs = [error_msg]

    if not logs:
        return state, 0

    # 过滤掉包含 "- INFO -" 的日志行（可能是系统内部日志，避免干扰解析）
    filtered_logs = []
    for log in logs:
        if "- INFO -" not in log:
            filtered_logs.append(log)

    if not filtered_logs:
        return state, 0

    final_contents, updated_index = parse_logs_incrementally(filtered_logs, state, last_index)
    return final_contents, updated_index


# ================== 模块描述字典 ==================
MODULE_DESCRIPTIONS = {
    "Detailed Idea Description": "At this level, users provide comprehensive descriptions of their specific research ideas. The system processes these detailed inputs to develop implementation strategies based on the user's explicit requirements. Examples 1-2 are the templates of this mode.",
    "Reference-Based Ideation": "This simpler level involves users submitting reference papers without a specific idea in mind. The user query typically follows the format: "'"I have some reference papers, please come up with an innovative idea and implement it with these papers."'" The system then analyzes the provided references to generate and develop novel research concepts. Examples 3-4 are the templates of this mode.",
    "Paper Generation Agent": "Once all research and experimental work is finished, employ this agent for paper generation",
}

# 默认的环境变量模板（用于初始化 .env 文件）
DEFAULT_ENV_TEMPLATE = """#===========================================
# MODEL & API 
# (See https://docs.camel-ai.org/key_modules/models.html#)
#===========================================

# OPENAI API (https://platform.openai.com/api-keys)
OPENAI_API_KEY='Your_Key'
# OPENAI_API_BASE_URL=""

# Azure OpenAI API
# AZURE_OPENAI_BASE_URL=""
# AZURE_API_VERSION=""
# AZURE_OPENAI_API_KEY=""
# AZURE_DEPLOYMENT_NAME=""


# Qwen API (https://help.aliyun.com/zh/model-studio/developer-reference/get-api-key)
QWEN_API_KEY='Your_Key'

# DeepSeek API (https://platform.deepseek.com/api_keys)
DEEPSEEK_API_KEY='Your_Key'

#===========================================
# Tools & Services API
#===========================================

# Google Search API (https://coda.io/@jon-dallas/google-image-search-pack-example/search-engine-id-and-google-api-key-3)
GOOGLE_API_KEY='Your_Key'
SEARCH_ENGINE_ID='Your_ID'

# Chunkr API (https://chunkr.ai/)
CHUNKR_API_KEY='Your_Key'

# Firecrawl API (https://www.firecrawl.dev/)
FIRECRAWL_API_KEY='Your_Key'
#FIRECRAWL_API_URL="https://api.firecrawl.dev"
"""


# ================== 输入验证 ==================
def validate_input(question: str) -> bool:
    """验证用户问题是否有效（非空）"""
    if not question or question.strip() == "":
        return False
    return True


# ================== 核心执行函数 ==================
def run_ai_researcher(question: str, reference: str, example_module: str) -> Tuple[str, str, str]:
    """
    调用 main_ai_researcher 执行研究任务。
    返回 (结果文本, token统计信息, 状态信息)。
    """
    global CURRENT_PROCESS

    if not validate_input(question):
        logging.warning("User submitted invalid input")
        return ("Please enter a valid question", "0", "❌ Error: Invalid input question")

    try:
        load_dotenv(find_dotenv(), override=True)
        logging.info(f"Processing question: '{question}', using module: {example_module}")

        if example_module not in MODULE_DESCRIPTIONS:
            logging.error(f"User selected an unsupported module: {example_module}")
            return (
                f"Selected module '{example_module}' is not supported",
                "0",
                "❌ Error: Unsupported module",
            )

        # 调用主研究函数
        try:
            answer = main_ai_researcher(question, reference, example_module)
            logging.info("Sucessully Runing AI Researcher")
        except Exception as e:
            logging.error(f"Error occurred while running Researcher: {str(e)}")
            return (
                f"Error occurred while running Researcher: {str(e)}",
                "0",
                f"❌ Error: Run failed - {str(e)}",
            )

        token_info = None
        if not isinstance(token_info, dict):
            token_info = {}

        completion_tokens = token_info.get("completion_token_count", 0)
        prompt_tokens = token_info.get("prompt_token_count", 0)
        total_tokens = completion_tokens + prompt_tokens

        logging.info(
            f"Processing completed, token usage: completion={completion_tokens}, prompt={prompt_tokens}, total={total_tokens}"
        )

        return (
            answer,
            f"Completion tokens: {completion_tokens:,} | Prompt tokens: {prompt_tokens:,} | Total: {total_tokens:,}",
            "✅ Successfully completed",
        )

    except Exception as e:
        logging.error(f"Uncaught error occurred while processing the question: {str(e)}")
        return (f"Error occurred: {str(e)}", "0", f"❌ Error: {str(e)}")


def update_module_description(module_name: str) -> str:
    """根据所选模块返回对应的描述文本"""
    return MODULE_DESCRIPTIONS.get(module_name, "No description available")


# ================== 环境变量管理 ==================
# 存储从前端配置的环境变量（优先级最高）
WEB_FRONTEND_ENV_VARS: dict[str, str] = {}

def init_env_file():
    """若 .env 不存在，则用默认模板创建"""
    dotenv_path = find_dotenv()
    if not dotenv_path:
        with open(".env", "w") as f:
            f.write(DEFAULT_ENV_TEMPLATE)
        dotenv_path = find_dotenv()
    return dotenv_path

def load_env_vars():
    """
    加载环境变量，并返回字典，每个值为 (value, source) 元组。
    优先级：前端配置 > .env文件 > 系统环境变量。
    """
    dotenv_path = init_env_file()
    load_dotenv(dotenv_path, override=True)

    env_file_vars = {}
    with open(dotenv_path, "r") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                if "=" in line:
                    key, value = line.split("=", 1)
                    env_file_vars[key.strip()] = value.strip().strip("\"'")

    system_env_vars = {
        k: v
        for k, v in os.environ.items()
        if k not in env_file_vars and k not in WEB_FRONTEND_ENV_VARS
    }

    env_vars = {}
    # 系统环境（最低优先级）
    for key, value in system_env_vars.items():
        env_vars[key] = (value, "System")
    # .env 文件（中等优先级）
    for key, value in env_file_vars.items():
        env_vars[key] = (value, ".env file")
    # 前端配置（最高优先级）
    for key, value in WEB_FRONTEND_ENV_VARS.items():
        env_vars[key] = (value, "Frontend configuration")
        os.environ[key] = value

    return env_vars

def save_env_vars(env_vars):
    """将环境变量字典保存到 .env 文件"""
    try:
        dotenv_path = init_env_file()
        for key, value_data in env_vars.items():
            if key and key.strip():
                if isinstance(value_data, tuple):
                    value = value_data[0]
                else:
                    value = value_data
                set_key(dotenv_path, key.strip(), value.strip())
        load_dotenv(dotenv_path, override=True)
        global_state.START_FLAG = False
        global_state.FIRST_MAIN = False
        return True, "Environment variables have been successfully saved!"
    except Exception as e:
        return False, f"Error saving environment variables: {str(e)}"

def add_env_var(key, value, from_frontend=True):
    """添加或更新单个环境变量，同时更新 .env 和 os.environ"""
    try:
        if not key or not key.strip():
            return False, "Variable name cannot be empty"
        key = key.strip()
        value = value.strip()
        if from_frontend:
            WEB_FRONTEND_ENV_VARS[key] = value
            os.environ[key] = value
        dotenv_path = init_env_file()
        set_key(dotenv_path, key, value)
        load_dotenv(dotenv_path, override=True)
        return True, f"Environment variable {key} has been successfully added/updated!"
    except Exception as e:
        return False, f"Error adding environment variable: {str(e)}"

def delete_env_var(key):
    """删除环境变量（从 .env, 前端字典, os.environ）"""
    try:
        if not key or not key.strip():
            return False, "Variable name cannot be empty"
        key = key.strip()
        dotenv_path = init_env_file()
        unset_key(dotenv_path, key)
        if key in WEB_FRONTEND_ENV_VARS:
            del WEB_FRONTEND_ENV_VARS[key]
        if key in os.environ:
            del os.environ[key]
        return True, f"Environment variable {key} has been successfully deleted!"
    except Exception as e:
        return False, f"Error deleting environment variable: {str(e)}"

def is_api_related(key: str) -> bool:
    """判断环境变量名是否与API密钥相关（用于显示过滤）"""
    api_keywords = [
        "api", "key", "token", "secret", "password",
        "openai", "qwen", "deepseek", "google", "search",
        "hf", "hugging", "chunkr", "firecrawl",
        "category", "instance_id", "task_level", "container_name",
        "workplace_name", "cache_path", "port", "max_iter_times"
    ]
    return any(keyword in key.lower() for keyword in api_keywords)

def get_api_guide(key: str) -> str:
    """根据环境变量名返回对应的API获取链接"""
    key_lower = key.lower()
    if "openai" in key_lower:
        return "https://platform.openai.com/api-keys"
    elif "qwen" in key_lower or "dashscope" in key_lower:
        return "https://help.aliyun.com/zh/model-studio/developer-reference/get-api-key"
    elif "deepseek" in key_lower:
        return "https://platform.deepseek.com/api_keys"
    elif "google" in key_lower:
        return "https://coda.io/@jon-dallas/google-image-search-pack-example/search-engine-id-and-google-api-key-3"
    elif "search_engine_id" in key_lower:
        return "https://coda.io/@jon-dallas/google-image-search-pack-example/search-engine-id-and-google-api-key-3"
    elif "chunkr" in key_lower:
        return "https://chunkr.ai/"
    elif "firecrawl" in key_lower:
        return "https://www.firecrawl.dev/"
    else:
        return ""

def update_env_table():
    """生成环境变量表格数据（仅显示API相关变量，并提供获取链接）"""
    env_vars = load_env_vars()
    api_env_vars = {k: v for k, v in env_vars.items() if is_api_related(k)}
    result = []
    for k, v in api_env_vars.items():
        guide = get_api_guide(k)
        guide_link = (
            f"<a href='{guide}' target='_blank' class='guide-link'>🔗 获取</a>"
            if guide
            else ""
        )
        result.append([k, v[0], guide_link])
    return result

def save_env_table_changes(data):
    """
    保存环境变量表格中的更改：添加、修改或删除变量。
    参数 data 可以是 pandas.DataFrame 或 list/dict。
    """
    try:
        logging.info(f"Starting to process environment variable table data, type: {type(data)}")
        current_env_vars = load_env_vars()
        processed_keys = set()

        import pandas as pd
        if isinstance(data, pd.DataFrame):
            columns = data.columns.tolist()
            logging.info(f"DataFrame column names: {columns}")
            for index, row in data.iterrows():
                if len(columns) >= 3:
                    key = row[0] if isinstance(row, pd.Series) else row.iloc[0]
                    value = row[1] if isinstance(row, pd.Series) else row.iloc[1]
                    if key and str(key).strip():
                        logging.info(f"Processing environment variable: {key} = {value}")
                        add_env_var(key, str(value))
                        processed_keys.add(key)
        elif isinstance(data, dict):
            if "data" in data:
                rows = data["data"]
            elif "values" in data:
                rows = data["values"]
            elif "value" in data:
                rows = data["value"]
            else:
                rows = []
                for key, value in data.items():
                    if key not in ["headers", "types", "columns"]:
                        rows.append([key, value])
            if isinstance(rows, list):
                for row in rows:
                    if isinstance(row, list) and len(row) >= 2:
                        key, value = row[0], row[1]
                        if key and str(key).strip():
                            add_env_var(key, str(value))
                            processed_keys.add(key)
        elif isinstance(data, list):
            for row in data:
                if isinstance(row, list) and len(row) >= 2:
                    key, value = row[0], row[1]
                    if key and str(key).strip():
                        add_env_var(key, str(value))
                        processed_keys.add(key)
        else:
            logging.error(f"Unknown data format: {type(data)}")
            return f"❌ Save failed: Unknown data format {type(data)}"

        # 删除表格中未出现的API相关变量
        api_related_keys = {k for k in current_env_vars.keys() if is_api_related(k)}
        keys_to_delete = api_related_keys - processed_keys
        for key in keys_to_delete:
            logging.info(f"Deleting environment variable: {key}")
            delete_env_var(key)

        return "✅ Environment variables have been successfully saved"
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logging.error(f"Error saving environment variables: {str(e)}\n{error_details}")
        return f"❌ Save failed: {str(e)}"

def get_env_var_value(key):
    """获取环境变量的实际值（前端配置优先）"""
    if key in WEB_FRONTEND_ENV_VARS:
        return WEB_FRONTEND_ENV_VARS[key]
    return os.environ.get(key, "")


# ================== Gradio UI 构建 ==================
def create_ui():
    """创建 Gradio 界面，包含输入区、对话记录和环境变量管理标签页"""

    def clear_log_file():
        """清空日志文件内容（保留文件）"""
        try:
            if LOG_FILE and os.path.exists(LOG_FILE):
                open(LOG_FILE, "w").close()
                logging.info("Log file has been cleared")
                while not LOG_QUEUE.empty():
                    try:
                        LOG_QUEUE.get_nowait()
                    except queue.Empty:
                        break
                return ""
            else:
                return ""
        except Exception as e:
            logging.error(f"Error clearing log file: {str(e)}")
            return ""

    # ----- 实时处理函数（用于Run按钮） -----
    def process_with_live_logs(question, reference, module_name, state, last_index):
        """
        在后台运行研究任务，并实时将日志输出到前端。
        使用生成器不断 yield 更新状态和对话记录。
        """
        global CURRENT_PROCESS

        result_queue = queue.Queue()

        def process_in_background():
            try:
                result = run_ai_researcher(question, reference, module_name)
                result_queue.put(result)
            except Exception as e:
                result_queue.put(
                    (f"Error occurred: {str(e)}", "0", f"❌ Error: {str(e)}")
                )

        # 过滤完全空的对话对
        def filter_empty_conversations(conversations):
            filtered = []
            for user_msg, bot_msg in conversations:
                user_empty = not user_msg.strip() if user_msg else True
                bot_empty = not bot_msg.strip() if bot_msg else True
                if user_empty and bot_empty:
                    continue
                processed_user = user_msg if not user_empty else None
                processed_bot = bot_msg if not bot_empty else None
                filtered.append((processed_user, processed_bot))
            return filtered

        # 启动后台线程
        bg_thread = threading.Thread(target=process_in_background)
        CURRENT_PROCESS = bg_thread
        bg_thread.start()

        scroll_script = None  # 可用于滚动控制

        # 循环等待后台线程完成，期间不断刷新日志显示
        while bg_thread.is_alive():
            logs2, updated_index = get_latest_logs(500, state, LOG_QUEUE, last_index)
            filtered_logs = filter_empty_conversations(logs2)
            yield (
                state,
                "<span class='status-indicator status-running'></span> Processing...",
                filtered_logs,
                scroll_script,
                updated_index
            )
            time.sleep(1)

        # 任务完成后获取结果并最后一次更新日志
        if not result_queue.empty():
            result = result_queue.get()
            answer, token_count, status = result

            logs2, updated_index = get_latest_logs(500, state, LOG_QUEUE, last_index)
            filtered_logs = filter_empty_conversations(logs2)

            if "错误" in status:
                status_with_indicator = f"<span class='status-indicator status-error'></span> {status}"
            else:
                status_with_indicator = f"<span class='status-indicator status-success'></span> {status}"

            yield token_count, status_with_indicator, filtered_logs, scroll_script, updated_index
        else:
            logs2, updated_index = get_latest_logs(500, state, LOG_QUEUE, last_index)
            filtered_logs = filter_empty_conversations(logs2)
            yield (
                state,
                "<span class='status-indicator status-error'></span> Terminated",
                filtered_logs,
                None,
                updated_index
            )

    # ----- 构建 UI 布局 -----
    with gr.Blocks(theme=gr.themes.Soft(primary_hue="amber")) as app:

        # 显示logo和标题
        image_base64 = get_base64_image("assets/logo.png")
        gr.HTML(
            f"""
            <div style="display: flex; align-items: center; gap: 16px;">
                <img src="{image_base64}" alt="模型图片" style="width: 100px; height: auto;">
                <div style="display: flex; flex-direction: column;">
                    <h2 style="margin: 0;">AI-Researcher: Autonomous Scientific Innovation</h2>
                    <br>
                    <p style="margin: 0;">Welcome to AI-Researcher🤗 AI-Researcher introduces a revolutionary breakthrough in Automated</p>
                    <p style="margin: 0;">Scientific Discovery🔬, presenting a new system that fundamentally Reshapes the Traditional Research Paradigm.</p>
                </div>
            </div>
            """
        )

        # 自定义CSS样式
        gr.HTML("""
            <style>
            /* 样式省略，保持原样 */
            </style>
        """)

        # 主布局：左列输入区 + 右列标签页
        with gr.Row():
            with gr.Column(scale=0.5):
                question_input = gr.Textbox(
                    lines=5, max_lines=10,
                    placeholder="Please enter your questions...",
                    label="Prompt",
                    value="Write a hello world python file and save it in local file",
                )
                reference_input = gr.Textbox(
                    lines=5, max_lines=10,
                    placeholder="Please enter your reference papers...",
                    label="Reference",
                    value="1. Attention is all you need. ",
                )
                module_dropdown = gr.Dropdown(
                    choices=list(MODULE_DESCRIPTIONS.keys()),
                    value="Detailed Idea Description",
                    label="Select Mode",
                    interactive=True,
                )
                module_description = gr.Textbox(
                    lines=3, max_lines=5,
                    value=MODULE_DESCRIPTIONS["Detailed Idea Description"],
                    label="Mode Description",
                    interactive=False,
                )
                with gr.Row():
                    run_button = gr.Button("Run", variant="primary")
                status_output = gr.HTML(
                    value="<span class='status-indicator status-success'></span> Ready",
                    label="状态",
                )

                # 示例输入
                examples = [
                    [
                        "1. The proposed model designed in this paper is designed to improve the performance of Vector Quantized Variational AutoEncoders (VQ-VAEs) by addressing issues with gradient propagation through the non-differentiable vector quantization layer.\n\n2. The core methodologies utilized include:\n   - **Rotation and Rescaling Transformation**: ...",
                        "1. Title: Neural discrete representation learning; ..."
                    ],
                    [
                        "gnn",
                        "Title: Graph Neural Networks: A Review of Methods and Applications; ..."
                    ],
                    # ... 其他示例省略
                ]
                with gr.Row(elem_classes="scrolling-example"):
                    gr.Examples(examples=examples, inputs=[question_input, reference_input])

                gr.Markdown("""
                ### Example Description：
                1️⃣ Examples 1-2: For **Detailed Idea Description** Mode <br>
                2️⃣ Examples 3-4: For **Reference-Based Ideation** Mode <br>
                ...
                """)

                gr.HTML("""
                        <div class="footer" id="about">
                            <h3>AI-Researcher: Autonomous Scientific Innovation</h3>
                            <p>© 2025 HKUDS. MIT license <a href="https://github.com/HKUDS/AI-Researcher" target="_blank">GitHub</a></p>
                        </div>
                    """)

            # 右侧标签页
            with gr.Tabs():
                # 对话记录标签
                with gr.TabItem("Conversation Record"):
                    with gr.Group():
                        log_display2 = gr.Chatbot(
                            elem_id="chat-log",
                            elem_classes="log-display"
                        )
                        state = gr.State([])
                        last_index = gr.State(0)
                        scroll_trigger = gr.HTML("", visible=False)
                    with gr.Row():
                        download_research_logs = gr.Button("Extract research log files")
                        download_paper_logs = gr.Button("Extract paper log files")
                        download_paper = gr.Button("Extract paper")
                        file_output = gr.File(label="click to download", elem_classes="custom-file")

                # 环境变量管理标签
                with gr.TabItem("Environment Variable Management", id="env-settings"):
                    with gr.Group(elem_classes="env-manager-container"):
                        gr.Markdown("""
                            ## Environment Variable Management
                            Set model API keys and other service credentials here...
                            """)
                        with gr.Row():
                            with gr.Column(scale=3):
                                with gr.Group(elem_classes="env-controls"):
                                    gr.Markdown("""
                                    <div style="background-color: #e7f3fe; border-left: 6px solid #2196F3; padding: 10px; margin: 15px 0; border-radius: 4px;">
                                      <strong>Tip:</strong> Please make sure to run cp .env_template .env to create a local .env file...
                                    </div>
                                    """)
                                    env_table = gr.Dataframe(
                                        headers=["Variable Name", "Value", "Retrieval Guide"],
                                        datatype=["str", "str", "html"],
                                        row_count=10,
                                        col_count=(3, "fixed"),
                                        value=update_env_table,
                                        label="API Keys and Environment Variables",
                                        interactive=True,
                                        elem_classes="env-table",
                                    )
                                    gr.Markdown("""
                                    <div style="background-color: #fff3cd; border-left: 6px solid #ffc107; padding: 10px; margin: 15px 0; border-radius: 4px;">
                                    <strong>Operation Guide</strong>:
                                    <ul>
                                      <li><strong>Edit Variable</strong>: Click directly on the "Value" cell</li>
                                      <li><strong>Add Variable</strong>: Enter a new variable name and value in a blank row</li>
                                      <li><strong>Delete Variable</strong>: Clear the variable name to delete that row</li>
                                      <li><strong>Get API Key</strong>: Click on the link in the "Retrieval Guide" column</li>
                                    </ul>
                                    </div>
                                    """)
                                    with gr.Row(elem_classes="env-buttons"):
                                        save_env_button = gr.Button("💾 Save Changes", variant="primary")
                                        refresh_button = gr.Button("🔄 Refresh List")
                                    env_status = gr.HTML(label="Operation Status", value="", elem_classes="env-status")

        # ---------- 事件绑定 ----------
        run_button.click(
            fn=process_with_live_logs,
            inputs=[question_input, reference_input, module_dropdown, state, last_index],
            outputs=[state, status_output, log_display2, scroll_trigger, last_index],
        )

        module_dropdown.change(
            fn=update_module_description,
            inputs=module_dropdown,
            outputs=module_description,
        )

        # 下载按钮（返回文件路径）
        download_research_logs.click(fn=return_log_file, outputs=file_output)
        download_paper_logs.click(fn=return_log_file, outputs=file_output)
        download_paper.click(fn=return_paper_file, outputs=file_output)

        # 环境变量保存与刷新
        save_env_button.click(
            fn=save_env_table_changes,
            inputs=[env_table],
            outputs=[env_status],
        ).then(fn=update_env_table, outputs=[env_table])

        refresh_button.click(fn=update_env_table, outputs=[env_table])

    return app


# ================== 启动主函数 ==================
def main():
    """
    应用入口：
     1. 初始化日志系统
     2. 启动后台日志读取线程
     3. 初始化 .env 文件
     4. 构建并启动 Gradio 应用
    """
    try:
        global LOG_FILE, LOG_READ_FILE
        LOG_FILE = setup_logging()
        LOG_READ_FILE = setup_path()

        # 启动日志读取线程（daemon 保证随主程序退出）
        log_thread = threading.Thread(
            target=log_reader_thread, args=(LOG_FILE,), daemon=True
        )
        log_thread.start()
        logging.info("Log reading thread started")

        init_env_file()
        app = create_ui()

        app.queue()
        allowed_paths = [os.path.dirname(LOG_FILE)]
        app.launch(
            share=False,
            server_port=7039,
            server_name="127.0.0.1",
            allowed_paths=allowed_paths,
            show_error=True,
            quiet=False,
            favicon_path="assets/logo.png"
        )

    except Exception as e:
        logging.error(f"Error occurred while starting the application: {str(e)}")
        print(f"Error occurred while starting the application: {str(e)}")
        import traceback
        traceback.print_exc()

    finally:
        STOP_LOG_THREAD.set()
        STOP_REQUESTED.set()
        logging.info("Application closed")


if __name__ == "__main__":
    main()