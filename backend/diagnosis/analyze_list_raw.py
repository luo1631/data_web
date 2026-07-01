"""Extract listing data directly from raw GBK bytes and save to file."""
import re

with open('diagnosis/homepage.html', 'rb') as f:
    content = f.read()

# Find the shop_list section
shop_start = content.find(b'shop_list')
shop_chunk = content[shop_start:shop_start + 30000]

# Find first <dl that has /chushou/
dl_start = shop_chunk.find(b'<dl', shop_chunk.find(b'/chushou/') - 500)
# Find the first <dl above this
search_start = dl_start - 2000
prev_dl = shop_chunk.rfind(b'<dl class="clearfix', 0, dl_start)
if prev_dl > 0:
    dl_start = prev_dl

# Find matching </dl>
depth = 1
pos = dl_start + 3
while depth > 0 and pos < len(shop_chunk) - 5:
    if shop_chunk[pos:pos+3] == b'<dl':
        depth += 1
        pos += 3
    elif shop_chunk[pos:pos+5] == b'</dl>':
        depth -= 1
        if depth == 0:
            pos += 5
            break
        pos += 5
    else:
        pos += 1

raw_dl = shop_chunk[dl_start:pos]

with open('diagnosis/listing_raw.txt', 'wb') as f:
    f.write(raw_dl)

# Now decode properly and extract
dl = raw_dl.decode('gbk', errors='replace')

with open('diagnosis/listing_decoded.txt', 'w', encoding='utf-8') as f:
    f.write(dl)

# Extract all data
print('=== LISTING DATA EXTRACTION ===\n')

# Title
title_m = re.search(r'<a[^>]*title="([^"]+)"', dl)
title = title_m.group(1) if title_m else 'N/A'
print(f'title: {title}')

# Price
price_m = re.search(r'<b>(\d+)</b>\s*万', dl)
total_price = price_m.group(1) if price_m else 'N/A'
print(f'total_price: {total_price}万')

unit_m = re.search(r'<span[^>]*>(\d+)\s*元/[平P㎡]', dl)
unit_price = unit_m.group(1) if unit_m else 'N/A'
print(f'unit_price: {unit_price}元/㎡')

# Room count
room_m = re.search(r'(\d+)室(\d+)厅(\d+)卫', dl)
if room_m:
    print(f'layout: {room_m.group(1)}室{room_m.group(2)}厅{room_m.group(3)}卫')
else:
    # Try "卧室：N个"
    bed_m = re.search(r'卧室[：:](\d+)个', dl)
    if bed_m:
        print(f'bedrooms: {bed_m.group(1)}')
    print(f'layout: not found in standard format')

# Area
area_m = re.search(r'([\d.]+)\s*[㎡²]', dl)
area = area_m.group(1) if area_m else 'N/A'
print(f'area: {area}㎡')

# Orientation
for o in ['南北', '东南', '西南', '东北', '西北', '东西', '南', '北', '东', '西']:
    if o + '向' in dl:
        print(f'orientation: {o}')
        break

# Building type
bt_m = re.search(r'<a class="link_rk"[^>]*>([^<]+)</a>', dl)
building_type = bt_m.group(1) if bt_m else 'N/A'
print(f'building_type: {building_type}')

# Community name
comm_m = re.search(r'<a[^>]*href="/house-xm\d+/"[^>]*title="([^"]+)"', dl)
community_name = comm_m.group(1) if comm_m else 'N/A'
print(f'community_name: {community_name}')

# Address
addr_m = re.search(r'<a[^>]*href="/house-xm\d+/"[^>]*>.*?</a>\s*<span[^>]*>([^<]+)</span>', dl, re.DOTALL)
address = addr_m.group(1).strip() if addr_m else 'N/A'
print(f'address: {address}')

# Floor info
for fl in ['低楼层', '中楼层', '高楼层', '底层', '中层', '高层']:
    if fl in dl:
        print(f'floor_level: {fl}')
        break
else:
    print(f'floor_level: not found explicitly')

# Decoration
for dec in ['精装', '简装', '豪装', '毛坯', '中装', '其他']:
    if dec in dl:
        print(f'decoration: {dec}')
        break
else:
    print(f'decoration: not found explicitly')

# Tags from label section
labels = re.findall(r'<span[^>]*>([^<]{1,20})</span>', dl)
print(f'tags: {labels}')

# House ID
hid_m = re.search(r'/chushou/(\d+_\d+)\.htm', dl)
house_id = hid_m.group(1) if hid_m else 'N/A'
print(f'house_id: {house_id}')

# Full text dump for manual inspection
all_text = re.sub(r'<[^>]+>', ' ', dl)
all_text = re.sub(r'\s+', ' ', all_text)
print(f'\n=== FULL TEXT ===')
print(all_text[:500])
