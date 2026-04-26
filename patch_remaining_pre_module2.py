import json
from pathlib import Path

path = Path(r"c:\Users\linux\OneDrive\notebook\amd_first_module\pre_module.ipynb")
nb = json.loads(path.read_text(encoding='utf-8'))
modified = False
for cell in nb.get('cells', []):
    if cell.get('cell_type') != 'code':
        continue
    source = ''.join(cell.get('source', []))
    if "all_stocks['code'].str.contains(r'[A-Za-z]', na=False)" in source and "all_stocks['code'] = all_stocks['code'].astype(str)" not in source:
        old1 = "krx = all_stocks[~all_stocks['code'].str.contains(r'[A-Za-z]', na=False)]"
        old2 = "all_stocks = all_stocks[~all_stocks['code'].str.contains(r'[A-Za-z]', na=False)].copy()"
        old3 = "df = all_stocks[~all_stocks['code'].str.contains(r'[A-Za-z]', na=False)].copy()"
        if old1 in source:
            source = source.replace(old1, "all_stocks['code'] = all_stocks['code'].astype(str)\n" + old1)
            modified = True
        if old2 in source:
            source = source.replace(old2, "all_stocks['code'] = all_stocks['code'].astype(str)\n" + old2)
            modified = True
        if old3 in source:
            source = source.replace(old3, "all_stocks['code'] = all_stocks['code'].astype(str)\n" + old3)
            modified = True
        if modified:
            cell['source'] = source.splitlines(keepends=True)

if not modified:
    raise SystemExit('No remaining all_stocks str.contains patterns were patched.')

path.write_text(json.dumps(nb, ensure_ascii=False, indent=1), encoding='utf-8')
print('Patched remaining all_stocks str.contains patterns')
