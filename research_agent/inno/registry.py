from typing import Callable, Dict, Any, Union, Literal, List, Optional
from dataclasses import dataclass, asdict
import inspect

# 存储已注册函数的元信息的轻量数据类
@dataclass
class FunctionInfo:
    """用于存储函数相关元信息的数据类"""
    name: str                       # 函数注册名称
    func: Callable                  # 函数对象本身（不可序列化）
    args: List[str]                 # 参数名列表
    docstring: Optional[str]        # 文档字符串
    body: str                       # 函数体源代码（去除装饰器与定义头）
    return_type: Optional[str]      # 返回类型注解的字符串表示

    def to_dict(self) -> dict:
        """转换为字典，排除不可序列化的 func 字段"""
        d = asdict(self)
        d.pop('func')  # 移除 func 字段
        return d
    
    @classmethod
    def from_dict(cls, data: dict) -> 'FunctionInfo':
        """从字典重建对象，若缺少 func 则填充默认值 None"""
        if 'func' not in data:
            data['func'] = None  # 或其他默认值
        return cls(**data)


class Registry:
    """单例注册中心，管理工具和代理两类可调用对象及其元信息"""
    _instance = None
    _registry: Dict[str, Dict[str, Callable]] = {
        "tools": {},   # 工具函数字典，键为名称，值为可调用对象
        "agents": {}   # 代理函数字典
    }
    _registry_info: Dict[str, Dict[str, FunctionInfo]] = {
        "tools": {},   # 工具函数的元信息字典
        "agents": {}   # 代理函数的元信息字典
    }
    
    def __new__(cls):
        """实现单例模式，确保全局只有一个 Registry 实例"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def register(self, 
                type: Literal["tool", "agent"],
                name: str = None):
        """
        通用装饰器工厂：根据类型将函数注册为工具或代理，并自动提取函数元信息。
        Args:
            type: 注册类型，"tool" 或 "agent"
            name: 可选的自定义注册名称，默认使用原始函数名
        Returns:
            decorator: 实际用于包装函数的装饰器
        """
        def decorator(func: Callable):
            nonlocal name
            if name is None:
                name = func.__name__  # 默认使用函数名作为注册名称
            
            # 提取函数签名
            signature = inspect.signature(func)
            args = list(signature.parameters.keys())  # 参数名列表
            
            # 获取文档字符串
            docstring = inspect.getdoc(func)
            
            # 获取函数体源代码（去除装饰器和 def 行）
            source_lines = inspect.getsource(func)
            body_lines = source_lines.split('\n')[1:]  # 跳过装饰器行（假设第一行是 @装饰器）
            # 继续跳过可能存在的其他装饰器和函数定义行
            while body_lines and (body_lines[0].strip().startswith('@') or 'def ' in body_lines[0]):
                body_lines = body_lines[1:]
            body = '\n'.join(body_lines)
            
            # 提取返回类型注解
            return_type = None
            if signature.return_annotation != inspect.Signature.empty:
                return_type = str(signature.return_annotation)
            
            # 构建函数信息对象
            func_info = FunctionInfo(
                name=name,
                func=func,
                args=args,
                docstring=docstring,
                body=body,
                return_type=return_type
            )
            
            # 按类型存入对应的注册表
            registry_type = f"{type}s"  # "tools" 或 "agents"
            self._registry[registry_type][name] = func
            self._registry_info[registry_type][name] = func_info
            return func  # 返回原函数，不改变其行为
        return decorator
    
    @property
    def tools(self) -> Dict[str, Callable]:
        """获取所有已注册的工具函数字典"""
        return self._registry["tools"]
    
    @property
    def agents(self) -> Dict[str, Callable]:
        """获取所有已注册的代理函数字典"""
        return self._registry["agents"]
    
    @property
    def tools_info(self) -> Dict[str, FunctionInfo]: 
        """获取所有工具函数的元信息字典"""
        return self._registry_info["tools"]
    
    @property
    def agents_info(self) -> Dict[str, FunctionInfo]: 
        """获取所有代理函数的元信息字典"""
        return self._registry_info["agents"]


# 创建全局单例注册表实例，方便外部引用
registry = Registry()

# 便捷装饰器：注册工具
def register_tool(name: str = None):
    """装饰器：将被装饰函数注册为工具"""
    return registry.register(type="tool", name=name)

# 便捷装饰器：注册代理
def register_agent(name: str = None):
    """装饰器：将被装饰函数注册为代理"""
    return registry.register(type="agent", name=name)