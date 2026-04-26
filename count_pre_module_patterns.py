from pathlib import Path

p = Path(r"c:\Users\linux\OneDrive\notebook\amd_first_module\pre_module.ipynb")
t = p.read_text(encoding='utf-8')
patterns = [
    'new_one.code.str.contains',
    "new_one['code'].astype(str).str.contains('K|L|M')",
    'df.code.str.contains',
    "df['code'].astype(str).str.contains('K|L|M')",
    "all_stocks['code'].str.contains(r'[A-Za-z]', na=False)",
    "all_stocks['code'] = all_stocks['code'].astype(str)",
]
for pat in patterns:
    print(pat, t.count(pat))
