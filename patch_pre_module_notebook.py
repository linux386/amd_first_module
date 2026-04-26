import json
from pathlib import Path

path = Path(r"c:\Users\linux\OneDrive\notebook\amd_first_module\pre_module.ipynb")
raw = path.read_text(encoding="utf-8")
nb = json.loads(raw)
changed = False

patches = [
    (
        "all_stocks = pd.read_excel(KRX_FILE)\n    df = all_stocks[~all_stocks['code'].str.contains(r'[A-Za-z]', na=False)].copy()\n",
        "all_stocks = pd.read_excel(KRX_FILE)\n    all_stocks['code'] = all_stocks['code'].astype(str)\n    df = all_stocks[~all_stocks['code'].str.contains(r'[A-Za-z]', na=False)].copy()\n",
    ),
    (
        "new_stocks = new_stocks[~new_stocks['code'].str.contains('K|L|M', na=False)]\n",
        "new_stocks = new_stocks[~new_stocks['code'].astype(str).str.contains('K|L|M', na=False)]\n",
    ),
    (
        "new_stock = new_one[new_one.code.str.contains('K|L|M') == False]\n",
        "new_stock = new_one[new_one['code'].astype(str).str.contains('K|L|M') == False]\n",
    ),
    (
        "df = df[df.code.str.contains('K|L|M') == False]\n",
        "df = df[df['code'].astype(str).str.contains('K|L|M') == False]\n",
    ),
    (
        "all_stocks.columns = ['code', 'name']\nkrx = all_stocks[~all_stocks['code'].str.contains(r'[A-Za-z]', na=False)]\n",
        "all_stocks.columns = ['code', 'name']\nall_stocks['code'] = all_stocks['code'].astype(str)\nkrx = all_stocks[~all_stocks['code'].str.contains(r'[A-Za-z]', na=False)]\n",
    ),
]

for cell in nb.get('cells', []):
    if cell.get('cell_type') != 'code':
        continue
    source = ''.join(cell.get('source', []))
    new_source = source
    for old, new in patches:
        if old in new_source:
            new_source = new_source.replace(old, new)
            changed = True
    if new_source != source:
        cell['source'] = new_source.splitlines(keepends=True)

if not changed:
    raise SystemExit('No matching patterns were found in the notebook. Please verify the content.')

path.write_text(json.dumps(nb, ensure_ascii=False, indent=1), encoding='utf-8')
print('Notebook patched successfully')
