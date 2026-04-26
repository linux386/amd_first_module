import json
from pathlib import Path

path = Path(r"c:\Users\linux\OneDrive\notebook\amd_first_module\pre_module.ipynb")
nb = json.loads(path.read_text(encoding="utf-8"))
for idx, cell in enumerate(nb.get('cells', []), 1):
    if cell.get('cell_type') != 'code':
        continue
    source = ''.join(cell.get('source', []))
    if "astype(str).str.contains('K|L|M'" in source:
        print('FOUND KLM in cell', idx)
        print(source)
        print('-----')
    if "all_stocks['code'] = all_stocks['code'].astype(str)" in source:
        print('FOUND all_stocks cast in cell', idx)
        print(source)
        print('-----')
    if "new_one['code'].astype(str).str.contains('K|L|M')" in source:
        print('FOUND new_one cast in cell', idx)
        print(source)
        print('-----')
    if "df['code'].astype(str).str.contains('K|L|M')" in source:
        print('FOUND df cast in cell', idx)
        print(source)
        print('-----')
