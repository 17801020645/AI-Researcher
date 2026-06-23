from typing import Dict
import json
from research_agent.inno.workflow import Graph
from litellm import completion

def transfer_fschema_to_dict(fschema: Dict) -> Dict:
    """
    将前端传入的图结构数据 (fschema) 转换为工作流图所需的字典格式。

    参数:
        fschema: 包含节点和连接信息的前端 schema 数据。

    返回:
        一个包含 'nodes' 和 'edges' 的字典，可直接用于构建工作流图。
    """
    graph_dict = {}
    graph_dict['nodes'] = []  # 存储所有节点信息
    graph_dict['edges'] = []  # 存储所有边信息
    node_id_name_map = {}     # 用于将节点的 key 映射到 agent_name (type)
    fschema_data = fschema['data']
    
    # 遍历前端 schema 中的节点，构建节点列表
    for node in fschema_data['nodes']:
        graph_dict['nodes'].append({
            'agent_name': node['type'],          # 节点对应的代理名称
            "agent_tools": [],                   # 代理工具初始为空
            "input": "",                         # 输入初始为空
            "output": "",                        # 输出初始为空
            "is_start": node['type'] == 'start', # 是否为开始节点
            "is_end": node['type'] == 'end'      # 是否为结束节点
        }.copy())
        node_id_name_map[node['key']] = node['type']  # 记录 key 到名称的映射
    
    # 遍历连接信息，构建边列表
    for edge in fschema_data['connections']:
        graph_dict['edges'].append({
            'start': node_id_name_map[edge['from']],  # 边起始节点名称
            'end': node_id_name_map[edge['to']]       # 边结束节点名称
        }.copy())
    
    return graph_dict


def complete_workflow(workflow: Dict, description: str) -> Dict:
    """
    利用大模型将给定的工作流图补全为更详细的工作流图。

    主要是为每个节点补充 'agent_tools'、'input' 和 'output' 字段，
    并为边增加 'description' 字段。

    参数:
        workflow: 初步的工作流字典，包含 'nodes' 和 'edges'。
        description: 对工作流的自然语言描述，用于指导大模型补全。

    返回:
        补全后的工作流字典，结构与输入类似但字段更丰富。
    """
    # 系统提示，设定大模型的角色
    workflow_prompt = \
f"""
You are a workflow designer which can complete the workflow graph I give you to a more detailed workflow graph.
"""
    # 用户提示，提供待补全的工作流和描述，以及具体要求
    user_prompt = \
f"""
I have a workflow: {json.dumps(workflow, indent=4)}
The description of the workflow is: {description}
You should complete the workflow graph in the following way: 
1. Add "agent_tools" in each node only based on the description.
2. Add "input" and "output" in each node to make the workflow more clear.
3. Make sure other fields of the workflow keep the same.
"""
    messages = [
        {"role": "system", "content": workflow_prompt},
        {"role": "user", "content": user_prompt}
    ]
    
    # 定义期望的 JSON 输出格式，确保大模型返回的数据结构符合预期
    response_format = {
        "type": "json_schema",
        "json_schema": {
            "name": "graph",
            "schema": {
                "type": "object",
                "properties": {
                    "nodes": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "agent_name": {"type": "string"},
                                "agent_tools": {"type": "array", "items": {"type": "string"}}, 
                                "input": {"type": "string"},
                                "output": {"type": "string"},
                                "is_start": {"type": "boolean"},
                                "is_end": {"type": "boolean"}
                            },
                            "required": ["agent_name", "agent_tools", "input", "output", "is_start", "is_end"],
                            "additionalProperties": False
                        }
                    },
                    "edges": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "start": {"type": "string"},
                                "end": {"type": "string"},
                                "description": {"type": "string"}  # 为边增加描述字段
                            },
                            "required": ["start", "end", "description"],
                            "additionalProperties": False
                        }
                    }
                },
                "required": ["nodes", "edges"],
                "additionalProperties": False
            },
            "strict": True  # 要求模型严格遵循 schema
        }
    }
    
    # 调用大模型补全工作流
    response = completion(
        model='gpt-4o-2024-08-06',
        messages=messages,
        response_format=response_format
    )
    
    # 解析模型返回的 JSON 字符串为字典并返回
    return json.loads(response.choices[0].message.content)


if __name__ == '__main__':
    import os
    # 设置 OpenAI API 密钥（实际使用时应从安全的地方获取，避免硬编码）
    os.environ['OPENAI_API_KEY'] = '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'
    
    # 加载前端生成的图结构文件
    with open('/Users/tangjiabin/Documents/reasoning/metachain/chaingraph/common_ragflow-2024.json', 'r') as f:
        fschema = json.load(f)
    
    # 将前端图结构转换为初步的工作流字典
    graph_dict = transfer_fschema_to_dict(fschema)
    
    # 根据工作流字典构建图对象并可视化（展示初始状态）
    g = Graph.from_dict(graph_dict)
    g.visualize()
    
    # 定义工作流描述文本
    description = (
        "The workflow is a common workflow for the RAG system. "
        "It consists of Query Rewriter Agent, Retriever Agent, Reranker Agent, and Generator Agent. "
        "The input of the workflow is a user query, the path of target document is given by the user. "
        "Retriever Agent have `save_to_vectordb` tool to save the document to the vector database, "
        "and have `retrieve_from_vectordb` tool to retrieve the document from the vector database. "
        "Reranker Agent have `rerank` tool to rerank the retrieved documents."
    )
    
    # 调用大模型补全工作流，为节点和边添加详细信息
    graph_dict = complete_workflow(graph_dict, description)
    
    # 打印补全后的工作流字典（便于查看结果）
    print(json.dumps(graph_dict, indent=4))