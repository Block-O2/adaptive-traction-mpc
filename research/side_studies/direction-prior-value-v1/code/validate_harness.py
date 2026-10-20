from pathlib import Path
import ast
root=Path(__file__).resolve().parent
files=sorted(root.glob('*.py'))
for p in files:ast.parse(p.read_text(),filename=str(p))
print('AST_OK',len(files))
