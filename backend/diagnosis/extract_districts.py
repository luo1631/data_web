"""Extract district code mapping from the saved homepage HTML."""
import re, json

with open('homepage.html', 'rb') as f:
    content = f.read()

# Extract district links from raw bytes
# Pattern: <a ... href="/house-a{N}/" ...>DISTRICT_NAME</a>
# where DISTRICT_NAME is 2-6 Chinese characters encoded in GBK
pattern = re.compile(
    rb'<a[^>]*href="/house-a(\d+)/"[^>]*>'
    rb'\s*([\x80-\xff]{2,18})\s*'
    rb'</a>'
)

districts = {}
for m in pattern.finditer(content):
    code = m.group(1).decode('ascii')
    name_gbk = m.group(2)
    try:
        name = name_gbk.decode('gbk')
    except:
        name = f'DECODE_ERR_{code}'
    if name.strip():
        districts[code] = name.strip()

# Sort by code
for code in sorted(districts.keys(), key=lambda x: (len(x), x)):
    print(f'  a{code:8s} = {districts[code]}')

print(f'\nTotal: {len(districts)} districts')

with open('district_map_clean.json', 'w', encoding='utf-8') as f:
    json.dump(districts, f, ensure_ascii=False, indent=2)
print('Saved to district_map_clean.json')
