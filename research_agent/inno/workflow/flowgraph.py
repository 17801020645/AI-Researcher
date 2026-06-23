from collections import defaultdict
import networkx as nx
import matplotlib.pyplot as plt
import json
from typing import Dict
from copy import deepcopy

class Graph:
    """
    一个支持节点属性、边属性、路径查找和合并的有向图类。
    主要用于工作流建模，支持从 JSON 文件或字典构建图，并生成工作流步骤。
    """
    def __init__(self):
        # 邻接表：key 为 node_id，value 为后继节点 ID 列表
        self.graph = defaultdict(list)
        # 自增节点 ID 计数器，用于分配唯一 ID
        self.node_id_counter = 0
        # 节点名称到节点 ID 的映射
        self.node_name_to_id = {}
        # 节点属性字典，key 为 node_id，value 为属性字典（必须包含 'node_name' 和 'node_id'）
        self.nodes = {}
        # 边属性字典，key 为 (u_id, v_id) 元组，value 为属性字典
        self.edge_attributes = {}

    # -------------------- 节点管理 --------------------
    def add_node(self, node_name, **attributes):
        """
        添加节点，若节点已存在则更新其属性。
        返回该节点的 node_id。
        
        Parameters:
            node_name (str): 节点名称。
            **attributes: 其他可选节点属性。
        """
        if node_name not in self.node_name_to_id:
            node_id = self.node_id_counter
            self.node_name_to_id[node_name] = node_id
            # 初始化节点属性
            node_attrs = {'node_name': node_name, 'node_id': node_id}
            node_attrs.update(attributes)
            self.nodes[node_id] = node_attrs
            self.node_id_counter += 1
        else:
            # 节点已存在，更新属性
            node_id = self.node_name_to_id[node_name]
            self.nodes[node_id].update(attributes)
        return self.node_name_to_id[node_name]

    def update_nodes(self, nodes):
        """批量添加或更新节点，nodes 为字典列表，每项包含 'node_name' 和可选的 'node_attrs'"""
        for node in nodes:
            self.add_node(node['node_name'], **node.get('node_attrs', {}))

    def update_node(self, node_name, **attributes):
        """更新指定节点的属性，节点必须存在"""
        assert node_name in self.node_name_to_id, f"Node {node_name} does not exist"
        node_id = self.node_name_to_id[node_name]
        self.nodes[node_id].update(attributes)

    # -------------------- 边管理 --------------------
    def add_edge(self, u, v, **node_attributes):
        """
        添加一条从 u 到 v 的有向边，同时可以通过 node_attributes 为 u 和 v 设置属性。
        
        Parameters:
            u (str): 起始节点名称。
            v (str): 目标节点名称。
            **node_attributes: 可包含 'u_attrs' 和 'v_attrs' 为节点属性，'edge_attrs' 为边属性。
        """
        u_id = self.add_node(u, **node_attributes.get('u_attrs', {}))
        v_id = self.add_node(v, **node_attributes.get('v_attrs', {}))
        self.graph[u_id].append(v_id)
        # 存储边属性
        self.edge_attributes[(u_id, v_id)] = node_attributes.get('edge_attrs', {})

    def add_edges(self, edges):
        """批量添加边，每条边可以是 (u, v) 或 (u, v, dict) 的格式"""
        for edge in edges:
            if len(edge) == 3:
                self.add_edge(edge[0], edge[1], **edge[2])
            else:
                self.add_edge(edge[0], edge[1])

    # -------------------- 环检测 --------------------
    def detect_cycle_util(self, v, visited, rec_stack):
        """DFS 辅助函数，用于检测从节点 v 出发是否存在环"""
        visited[v] = True
        rec_stack[v] = True

        for neighbor in self.graph[v]:
            if not visited[neighbor]:
                if self.detect_cycle_util(neighbor, visited, rec_stack):
                    return True
            elif rec_stack[neighbor]:
                return True

        rec_stack[v] = False
        return False

    def has_cycle(self):
        """检查图中是否包含环（包括所有节点，即使没有出边）"""
        # 收集所有节点（包括没有出边的节点）
        all_nodes = set(self.graph.keys())
        for neighbors in self.graph.values():
            all_nodes.update(neighbors)

        visited = {node: False for node in all_nodes}
        rec_stack = {node: False for node in all_nodes}

        for node in all_nodes:
            if not visited[node]:
                if self.detect_cycle_util(node, visited, rec_stack):
                    return True
        return False

    def find_cycles(self):
        """找出图中的所有环，返回每个环的节点 ID 列表"""
        cycles = []

        # 收集所有节点
        all_nodes = set(self.graph.keys())
        for neighbors in self.graph.values():
            all_nodes.update(neighbors)

        def dfs_cycle(node, visited, rec_stack, path):
            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            for neighbor in self.graph.get(node, []):
                if neighbor not in visited:
                    dfs_cycle(neighbor, visited, rec_stack, path)
                elif neighbor in rec_stack:
                    # 发现环，路径中从 neighbor 开始到当前节点构成一个环
                    cycle_start = path.index(neighbor)
                    cycles.append(path[cycle_start:].copy())

            path.pop()
            rec_stack.remove(node)

        visited = set()
        for node in all_nodes:
            if node not in visited:
                dfs_cycle(node, visited, set(), [])

        return cycles

    # -------------------- 路径查找与处理 --------------------
    def find_all_paths(self, start, end, max_cycle_repeat=2):
        """
        查找从 start 到 end 的所有路径，允许每个节点重复出现 max_cycle_repeat 次。
        会过滤掉包含重复子串的路径（避免无意义循环）。
        """
        start_id = self.add_node(start)
        end_id = self.add_node(end)

        def is_cycle_complete(path, node):
            """检查是否构成一个完整的循环（路径中最近一次出现的该节点到末尾构成一个环）"""
            if node not in path:
                return True
            last_idx = len(path) - 1
            while last_idx >= 0 and path[last_idx] != node:
                last_idx -= 1
            # 从最近一次出现到末尾的节点集合必须构成一个完整的环
            cycle_nodes = set(path[last_idx:])
            for i in range(last_idx, len(path) - 1):
                if path[i + 1] not in self.graph[path[i]]:
                    return False
            return True

        def is_valid_path(path):
            """检查路径是否包含重复的连续子序列（禁止无效循环）"""
            n = len(path)
            for length in range(2, n // 2 + 1):
                for i in range(n - 2 * length + 1):
                    if path[i:i + length] == path[i + length:i + 2 * length]:
                        return False
            return True

        def dfs(current, end, path, paths):
            path.append(current)
            if current == end:
                paths.append(path.copy())
            else:
                for neighbor in self.graph[current]:
                    count = path.count(neighbor)
                    if count < max_cycle_repeat and is_cycle_complete(path, neighbor):
                        dfs(neighbor, end, path, paths)
            path.pop()

        all_paths = []
        dfs(start_id, end_id, [], all_paths)

        # 将节点 ID 转换为节点名称
        all_paths_named = []
        for path in all_paths:
            named_path = [self.nodes[node]['node_name'] for node in path]
            all_paths_named.append(named_path)

        # 进一步过滤路径（去除可由更长路径生成的短路径）
        filtered_paths = self.filter_paths(all_paths_named)
        return filtered_paths

    def set_start(self, start):
        """设置工作流的起始节点，将其标记为红色方形"""
        self.start = start
        self.nodes[self.add_node(start)]['color'] = 'red'
        self.nodes[self.add_node(start)]['shape'] = 's'

    def set_end(self, end):
        """设置工作流的结束节点，将其标记为绿色三角形"""
        self.end = end
        self.nodes[self.add_node(end)]['color'] = 'green'
        self.nodes[self.add_node(end)]['shape'] = '^'

    def filter_paths(self, all_paths):
        """
        过滤路径：移除那些可以由更长路径通过重复子串生成的短路径。
        例如，若存在 S -> A -> B -> C -> D -> C -> D -> F -> Z，
        则移除 S -> A -> B -> C -> D -> F -> Z（它是前者的子序列）。
        """
        def is_subpath(short, long):
            """检查 short 是否是 long 的子序列（保持顺序）"""
            it = iter(long)
            return all(node in it for node in short)

        # 按路径长度降序排序，保留较长的路径
        sorted_paths = sorted(all_paths, key=lambda x: len(x), reverse=True)
        filtered = []

        for path in sorted_paths:
            if not any(is_subpath(path, existing) for existing in filtered):
                filtered.append(path)

        return filtered

    # -------------------- 可视化 --------------------
    def visualize(self):
        """使用 matplotlib 和 networkx 绘制有向图，支持节点颜色、形状和边属性"""
        G = nx.DiGraph()

        # 添加节点，并收集颜色和形状信息
        node_colors = []
        node_shapes = defaultdict(list)
        for node_id, attrs in self.nodes.items():
            label = attrs.get('node_name', f"Node{node_id}")
            shape = attrs.get('shape', 'o')  # 默认圆形
            node_shapes[shape].append(node_id)
            color = attrs.get('color', 'lightblue')
            node_colors.append(color)
            G.add_node(node_id, label=label)

        # 添加边
        for u, neighbors in self.graph.items():
            for v in neighbors:
                edge_attr = self.edge_attributes.get((u, v), {})
                G.add_edge(u, v, **edge_attr)

        # 获取标签和颜色映射
        labels = {node: attrs['node_name'] for node, attrs in self.nodes.items()}
        node_color_map = [attrs.get('color', 'lightblue') for node, attrs in self.nodes.items()]
        shapes = set(attrs.get('shape', 'o') for attrs in self.nodes.values())

        pos = nx.spring_layout(G, seed=42)  # 固定布局

        plt.figure(figsize=(12, 8))

        # 按不同形状分别绘制节点
        for shape in shapes:
            shaped_nodes = [node for node in self.nodes if self.nodes[node].get('shape', 'o') == shape]
            nx.draw_networkx_nodes(
                G, pos,
                nodelist=shaped_nodes,
                node_shape=shape,
                node_color=[self.nodes[node].get('color', 'lightblue') for node in shaped_nodes],
                node_size=1500,
                alpha=0.9
            )

        # 绘制标签
        nx.draw_networkx_labels(G, pos, labels, font_size=12, font_color='black')

        # 根据边属性设置边的颜色
        edge_colors = []
        for u, v in G.edges():
            edge_attr = self.edge_attributes.get((u, v), {})
            edge_colors.append(edge_attr.get('color', 'black'))

        # 绘制边，确保箭头显示
        nx.draw_networkx_edges(
            G, pos,
            edge_color=edge_colors,
            arrows=True,
            arrowstyle='->',
            arrowsize=20,
            connectionstyle='arc3,rad=0.1',  # 调整弧度避免箭头重叠
            width=2
        )

        plt.title("Visualization", fontsize=16)
        plt.axis('off')
        plt.tight_layout()
        plt.show()

    # -------------------- 路径合并 --------------------
    def merge_paths(self, paths):
        """
        将多条路径合并为一条，保留长路径，将短路径的独有片段插入到长路径的合适位置。
        合并时去除首尾的最长公共子串，然后将中间部分插入。
        """
        if not paths:
            return []

        # 按长度降序排序，以最长路径为基线
        paths_sorted = sorted(paths, key=lambda p: len(p), reverse=True)
        merged_path = paths_sorted[0].copy()

        # 构建有向图用于后续拓扑排序
        G = nx.DiGraph()
        for path in paths:
            for i in range(len(path) - 1):
                G.add_edge(path[i], path[i + 1])

        # 节点顺序映射，基于当前合并路径的位置
        node_order = {node: idx for idx, node in enumerate(merged_path)}

        for short_path in paths_sorted[1:]:
            # 找到与 merged_path 开头的最长公共子序列
            start_idx = 0
            while start_idx < len(short_path):
                if short_path[start_idx] in merged_path:
                    merged_idx = merged_path.index(short_path[start_idx])
                    j = 1
                    while (start_idx + j < len(short_path) and
                           merged_idx + j < len(merged_path) and
                           short_path[start_idx + j] == merged_path[merged_idx + j]):
                        j += 1
                    start_idx = start_idx + j - 1
                    break
                start_idx += 1

            # 找到与 merged_path 结尾的最长公共子序列
            end_idx = len(short_path) - 1
            while end_idx > start_idx:
                if short_path[end_idx] in merged_path:
                    merged_idx = merged_path.index(short_path[end_idx])
                    j = 1
                    while (end_idx - j > start_idx and
                           merged_idx - j >= 0 and
                           short_path[end_idx - j] == merged_path[merged_idx - j]):
                        j += 1
                    end_idx = end_idx - j + 1
                    break
                end_idx -= 1

            # 需要插入的中间序列（去掉首尾重叠部分）
            insert_sequence = short_path[start_idx+1:end_idx]

            if insert_sequence:
                # 找到插入位置：在 matched 节点之后
                insert_pos = merged_path.index(short_path[start_idx]) + 1

                # 为待插入节点计算一个基顺序（用于后续可能的位置判断）
                sequence_base_order = -1
                for node in insert_sequence:
                    if node in node_order:
                        sequence_base_order = max(sequence_base_order, node_order[node])

                if sequence_base_order == -1:
                    # 如果没有已知节点，根据拓扑顺序估算
                    pred_pos = node_order[short_path[start_idx]]
                    succ_pos = node_order[merged_path[insert_pos]]
                    sequence_base_order = (pred_pos + succ_pos) / 2

                # 检查 merged_path 中是否已存在完全相同的子序列，避免重复插入
                sequence_exists = False
                for i in range(len(merged_path) - len(insert_sequence) + 1):
                    if merged_path[i:i+len(insert_sequence)] == insert_sequence:
                        sequence_exists = True
                        break

                if not sequence_exists:
                    for node in insert_sequence:
                        merged_path.insert(insert_pos, node)
                        node_order[node] = sequence_base_order
                        insert_pos += 1

        return merged_path

    def get_node_predecessors_successors(self):
        """
        获取每个节点的直接前驱和直接后继。
        返回格式：{node_name: {'predecessors': set(), 'successors': set()}}
        """
        result = {}
        for node_id in self.nodes:
            node_name = self.nodes[node_id]['node_name']
            result[node_name] = {'predecessors': set(), 'successors': set()}

        for u_id, neighbors in self.graph.items():
            u_name = self.nodes[u_id]['node_name']
            for v_id in neighbors:
                v_name = self.nodes[v_id]['node_name']
                result[v_name]['predecessors'].add(u_name)
                result[u_name]['successors'].add(v_name)

        self.node_predecessors_successors = result
        return result

    # -------------------- 工作流生成 --------------------
    def path2workflow(self, path):
        """
        将一条合并后的路径转换为工作流步骤列表。
        每个步骤包含 agent_name、agent_tools、input、output、ops_agent_tools 等信息。
        """
        workflow_steps = []
        if not hasattr(self, 'node_predecessors_successors'):
            self.get_node_predecessors_successors()

        for node in path:
            # 跳过起始和结束节点
            if node == self.end or node == self.start:
                continue

            output_flag = False
            n_predecessors = self.node_predecessors_successors[node]['predecessors']
            n_successors = self.node_predecessors_successors[node]['successors']
            node_id = self.node_name_to_id[node]
            agent_tools = deepcopy(self.nodes[node_id].get('agent_tools', []))
            ops_agent_tools = deepcopy(self.nodes[node_id].get('ops_agent_tools', []))

            # 检查是否有后继是结束节点，如果是，则标记 output_flag
            for successor in n_successors:
                if successor == self.end:
                    output_flag = True
                    continue

            # 构建输入描述
            input_text = []
            for predecessor in n_predecessors:
                if predecessor == self.start:
                    input_text.append(f'Input {predecessor}')
                else:
                    input_text.append(f'The output of {predecessor} agent')
            input_text = ','.join(input_text)

            output_text = self.nodes[node_id].get('output', '')

            if output_flag:
                workflow_steps.append({
                    "agent_name": node,
                    "agent_tools": agent_tools,
                    "input": input_text,
                    "output": f"Output {self.end}",
                    "ops_agent_tools": ops_agent_tools
                })
            else:
                workflow_steps.append({
                    "agent_name": node,
                    "agent_tools": agent_tools,
                    "input": input_text,
                    "output": output_text,
                    "ops_agent_tools": ops_agent_tools
                })

        return workflow_steps

    def get_workflow_steps(self):
        """
        获取完整的工作流步骤：
        1. 找到所有路径（允许循环重复3次）
        2. 合并路径
        3. 转换为工作流步骤
        4. 精炼工作流（添加 transfer_to 工具）
        """
        paths = self.find_all_paths(self.start, self.end, max_cycle_repeat=3)
        merged_path = self.merge_paths(paths)
        workflow = self.path2workflow(merged_path)
        workflow = self.refine_workflow(workflow)
        return workflow

    def refine_workflow(self, workflow):
        """
        精炼工作流：为每个 agent 添加 transfer_to_{next_agent} 工具，
        确保 agent 能够将控制权传递给下一个 agent。
        """
        agent_dict = {}
        work_lens = len(workflow)
        for step in workflow:
            agent_dict[step['agent_name']] = set()

        for i in range(work_lens - 1):
            step_front = workflow[i]
            step_back = workflow[i + 1]
            for tool in step_front['agent_tools']:
                agent_dict[step_front['agent_name']].add(tool)
            for tool in step_back['agent_tools']:
                agent_dict[step_back['agent_name']].add(tool)
            # 添加转移工具
            agent_dict[step_front['agent_name']].add(
                'transfer_to_' + '_'.join(step_back['agent_name'].lower().split(' '))
            )

        # 更新每个步骤的 tools
        for i in range(work_lens):
            agent_name = workflow[i]['agent_name']
            workflow[i]['agent_tools'] = list(agent_dict[agent_name])
            self.nodes[self.node_name_to_id[agent_name]]['agent_tools'] = list(agent_dict[agent_name])

        return workflow

    # -------------------- 序列化与反序列化 --------------------
    @classmethod
    def from_json_file(cls, json_file):
        """从 JSON 文件加载图数据并构建 Graph 实例"""
        with open(json_file, 'r') as f:
            data = json.load(f)
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: Dict):
        """从字典构建 Graph 实例，字典需包含 'nodes' 和 'edges' 列表"""
        graph = cls()
        edges = [(edge['start'], edge['end']) for edge in data['edges']]
        start, end = None, None
        for node in data['nodes']:
            if node['is_start']:
                start = node['agent_name']
            if node['is_end']:
                end = node['agent_name']

        graph.set_start(start)
        graph.set_end(end)
        graph.add_edges(edges)
        node_attrs = [
            {
                'node_name': node['agent_name'],
                'node_attrs': {
                    'agent_tools': node.get('agent_tools', []),
                    'output': node.get('output', '')
                }
            } for node in data['nodes']
        ]
        graph.update_nodes(node_attrs)
        return graph

    def to_dict(self):
        """将当前图结构导出为字典，便于序列化"""
        graph_dict = {'nodes': [], 'edges': []}
        for node_id, node in self.nodes.items():
            graph_dict['nodes'].append({
                'agent_name': node['node_name'],
                'agent_tools': node.get('agent_tools', []),
                'output': node.get('output', ''),
                'is_start': self.start == node['node_name'],
                'is_end': self.end == node['node_name']
            })

        for u, v_list in self.graph.items():
            for v_id in v_list:
                graph_dict['edges'].append({
                    'start': self.nodes[u]['node_name'],
                    'end': self.nodes[v_id]['node_name']
                })
        return graph_dict