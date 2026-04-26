import json
from pathlib import Path

path = Path(r"c:\Users\linux\OneDrive\notebook\amd_first_module\pre_module.ipynb")
nb = json.loads(path.read_text(encoding='utf-8'))
search = "all_stocks['code'].str.contains(r'[A-Za-z]', na=False)"
for idx, cell in enumerate(nb.get('cells', []), 1):
    if cell.get('cell_type') != 'code':
        continue
    source = ''.join(cell.get('source', []))
    if search in source:
        print('CELL', idx)
        for line in source.splitlines():
            if search in line:
                print(line)
        print('---')
