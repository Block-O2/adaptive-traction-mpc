"""冻结原array_items函数body的纯stdlib载入器；不执行原模块顶层。"""
import ast
import gzip
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace


def make_reader(path,expected_source_sha256):
    path=Path(path);source=path.read_text()
    assert hashlib.sha256(path.read_bytes()).hexdigest()==expected_source_sha256
    tree=ast.parse(source,filename=str(path))
    found=[node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=='array_items']
    assert len(found)==1 and not found[0].decorator_list
    function=found[0]
    # 原function AST/body逐节点保留；不执行task_bootstrap、numpy、main。
    executable=ast.fix_missing_locations(ast.Module(body=[function],type_ignores=[]))
    scope={'gzip':gzip,'json':json,'__builtins__':{'len':len,'ValueError':ValueError},'__name__':'_v8_exact_array_items_stdlib_only'}
    exec(compile(executable,str(path),'exec'),scope)
    return SimpleNamespace(array_items=scope['array_items'],original_function_AST_sha256=hashlib.sha256(ast.dump(function,include_attributes=False).encode()).hexdigest(),original_module_top_level_executed=False)
