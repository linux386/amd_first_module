from pathlib import Path

path = Path(r'c:\Users\linux\OneDrive\notebook\amd_first_module\pre_module.ipynb')
text = path.read_text(encoding='utf-8')
replacements = [
    (
        '    "    new_stocks = new_stocks[~new_stocks[\'code\'].str.contains(\'K|L|M\', na=False)]\\n",\\n',
        '    "    new_stocks = new_stocks[~new_stocks[\'code\'].astype(str).str.contains(\'K|L|M\', na=False)]\\n",\\n',
    ),
    (
        '    "    df = df[df.code.str.contains(\'K|L|M\') == False]\\n",\\n',
        '    "    df = df[df[\'code\'].astype(str).str.contains(\'K|L|M\') == False]\\n",\\n',
    ),
    (
        '    "new_stock = new_one[new_one.code.str.contains(\'K|L|M\') == False]\\n",\\n',
        '    "new_stock = new_one[new_one[\'code\'].astype(str).str.contains(\'K|L|M\') == False]\\n",\\n',
    ),
    (
        '    "    all_stocks = pd.read_excel(KRX_FILE)\\n",\\n    "    df = all_stocks[~all_stocks[\'code\'].str.contains(r\'[A-Za-z]\', na=False)].copy()\\n",\\n',
        '    "    all_stocks = pd.read_excel(KRX_FILE)\\n",\\n    "    all_stocks[\'code\'] = all_stocks[\'code\'].astype(str)\\n",\\n    "    df = all_stocks[~all_stocks[\'code\'].str.contains(r\'[A-Za-z]\', na=False)].copy()\\n",\\n',
    ),
    (
        '    "all_stocks.columns = [\'code\', \'name\']\\n",\\n    "krx = all_stocks[~all_stocks[\'code\'].str.contains(r\'[A-Za-z\]', na=False)]\\n",\\n',
        '    "all_stocks.columns = [\'code\', \'name\']\\n",\\n    "all_stocks[\'code\'] = all_stocks[\'code\'].astype(str)\\n",\\n    "krx = all_stocks[~all_stocks[\'code\'].str.contains(r\'[A-Za-z\]', na=False)]\\n",\\n',
    ),
]
for old, new in replacements:
    count = text.count(old)
    print('Replacing', repr(old[:80]), 'count', count)
    if count == 0:
        raise ValueError('Pattern not found: ' + repr(old[:80]))
    text = text.replace(old, new)
path.write_text(text, encoding='utf-8')
print('Finished patching')
