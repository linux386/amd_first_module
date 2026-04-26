import json
from pathlib import Path

path = Path(r"c:\Users\linux\OneDrive\notebook\amd_first_module\pre_module.ipynb")
nb = json.loads(path.read_text(encoding='utf-8'))
modified = False
for cell in nb.get('cells', []):
    if cell.get('cell_type') != 'code':
        continue
    source = ''.join(cell.get('source', []))
    if "all_stocks['code'].str.contains(r'[A-Za-z]', na=False)" in source:
        if "all_stocks['code'] = all_stocks['code'].astype(str)" not in source:
            if 'krx = all_stocks[~all_stocks[\'code\'].str.contains(r\'[A-Za-z\]', na=False)]' in source:
                source = source.replace(
                    "krx = all_stocks[~all_stocks['code'].str.contains(r'[A-Za-z]', na=False)]",
                    "all_stocks['code'] = all_stocks['code'].astype(str)\nkrx = all_stocks[~all_stocks['code'].str.contains(r'[A-Za-z]', na=False)]",
                )
                modified = True
            elif "all_stocks = all_stocks[~all_stocks['code'].str.contains(r'[A-Za-z]', na=False)].copy()" in source:
                source = source.replace(
                    "all_stocks = all_stocks[~all_stocks['code'].str.contains(r'[A-Za-z]', na=False)].copy()",
                    "all_stocks['code'] = all_stocks['code'].astype(str)\nall_stocks = all_stocks[~all_stocks['code'].str.contains(r'[A-Za-z]', na=False)].copy()",
                )
                modified = True
            elif "df = all_stocks[~all_stocks['code'].str.contains(r'[A-Za-z]', na=False)].copy()" in source:
                source = source.replace(
                    "df = all_stocks[~all_stocks['code'].str.contains(r'[A-Za-z]', na=False)].copy()",
                    "all_stocks['code'] = all_stocks['code'].astype(str)\ndf = all_stocks[~all_stocks['code'].str.contains(r'[A-Za-z]', na=False)].copy()",
                )
                modified = True
            cell['source'] = source.splitlines(keepends=True)

if not modified:
    raise SystemExit('No remaining all_stocks str.contains patterns were patched.')

path.write_text(json.dumps(nb, ensure_ascii=False, indent=1), encoding='utf-8')
print('Patched remaining all_stocks str.contains patterns')
