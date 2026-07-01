"""Analyze desktop listing HTML structure - writes to file to avoid encoding issues."""
import re

with open('homepage.html', 'rb') as f:
    content = f.read()

# Decode as GBK
html = content.decode('gbk', errors='replace')

# Find listing container
m = re.search(r'class="shop_list', html)
if not m:
    print('shop_list not found')
    exit(1)

# Extract 15000 chars from shop_list
start = m.start()
end = min(len(html), start + 15000)
chunk = html[start:end]

# Find individual listing blocks - they seem to be <dl> tags
# Let's find the first complete <dl>...</dl> that contains /chushou/
dl_start = None
for m in re.finditer(r'<dl', chunk):
    # Find matching </dl>
    depth = 1
    pos = m.end()
    while depth > 0 and pos < len(chunk):
        next_open = chunk.find('<dl', pos)
        next_close = chunk.find('</dl>', pos)
        if next_close == -1:
            break
        if next_open != -1 and next_open < next_close:
            depth += 1
            pos = next_open + 3
        else:
            depth -= 1
            pos = next_close + 5

    dl = chunk[m.start():pos]
    if '/chushou/' in dl:
        # Clean up
        dl_clean = re.sub(r'\s+', ' ', dl)
        with open('listing_block_1.txt', 'w', encoding='utf-8') as f:
            f.write(dl_clean)
        print(f'First listing block ({len(dl)} chars) saved to listing_block_1.txt')

        # Extract structured fields from this block
        print('\n=== Extracted Fields ===')

        # house_id from /chushou/X_Y.htm
        hid = re.search(r'/chushou/(\d+_\d+)\.htm', dl)
        if hid:
            print(f'house_id: {hid.group(1)}')

        # title from <a class="plotTit" or similar
        title = re.search(r'<a[^>]*title="([^"]+)"[^>]*>', dl)
        if title:
            print(f'title: {title.group(1)}')

        # price - total
        tp = re.search(r'<span[^>]*class="[^"]*red[^"]*"[^>]*>\s*[<b>]*\s*(\d+)\s*[</b>]*\s*</span>\s*万', dl)
        if tp:
            print(f'total_price: {tp.group(1)}万')

        # price - unit
        up = re.search(r'(\d+)\s*元/[平P㎡]', dl)
        if up:
            print(f'unit_price: {up.group(1)}元/㎡')

        # rooms
        rooms = re.search(r'(\d+)室(\d+)厅(\d+)卫', dl)
        if rooms:
            print(f'layout: {rooms.group(1)}室{rooms.group(2)}厅{rooms.group(3)}卫')

        # area
        area = re.search(r'([\d.]+)\s*[㎡²]', dl)
        if area:
            print(f'area: {area.group(1)}㎡')

        # orientation
        orients = ['南', '北', '南北', '东南', '西南', '东北', '西北', '东', '西']
        for o in orients:
            if o + '向' in dl or o + '北' in dl[:500] or '朝' + o in dl:
                print(f'orientation: {o}')
                break

        # decoration
        for dec in ['精装', '简装', '豪装', '毛坯', '中装']:
            if dec in dl:
                print(f'decoration: {dec}')
                break

        # floor
        for fl in ['低楼层', '中楼层', '高楼层', '底层', '中层', '高层']:
            if fl in dl:
                print(f'floor_level: {fl}')
                break

        # community name
        comm = re.search(r'<a[^>]*href="/house-xm\d+/"[^>]*title="([^"]+)"[^>]*>', dl)
        if comm:
            print(f'community_name: {comm.group(1)}')

        # building type
        for bt in ['板楼', '塔楼', '板塔结合', '独栋', '联排', '双拼', '叠拼', '平层']:
            if bt in dl:
                print(f'building_type: {bt}')
                break

        # address
        addr = re.search(r'<span[^>]*>([^<]{5,50})</span>\s*</p>\s*<p[^>]*class="[^"]*label', dl)
        if addr:
            print(f'address: {addr.group(1).strip()}')

        break

# Also dump the raw bytes of the first listing
# Find the first <dl that contains /chushou/
dl_byte_start = content.find(b'<dl', content.find(b'shop_list'))
if dl_byte_start > 0:
    dl_byte_end = content.find(b'</dl>', dl_byte_start) + 5
    raw_dl = content[dl_byte_start:dl_byte_end]
    # Write raw bytes
    with open('listing_block_raw.txt', 'wb') as f:
        f.write(raw_dl)
    print(f'\nRaw bytes ({len(raw_dl)} bytes) saved to listing_block_raw.txt')

# Save shop_list section as raw bytes for analysis
shop_byte_start = content.find(b'shop_list')
shop_byte_end = min(len(content), shop_byte_start + 30000)
with open('shop_list_section.html', 'wb') as f:
    f.write(content[shop_byte_start:shop_byte_end])
print('\nshop_list section saved to shop_list_section.html')
