"""Fetch district codes from fang.com desktop site - outputs clean mapping."""
import asyncio, re, json
import httpx

async def main():
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        resp = await client.get("https://cq.esf.fang.com/", headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130.0.0.0 Safari/537.36"
        })
        # resp.text is auto-decoded, but page is GBK - use resp.content
        content = resp.content
        html = content.decode('gbk', errors='replace')

        # Extract district links: <a href="/house-a{N}/">NAME</a>
        # Look for the district section
        dist_section = html[html.find('id="district"'):html.find('id="district"') + 5000]

        districts = {}
        for m in re.finditer(r'<a[^>]*href="/house-a(\d+)/"[^>]*>\s*(\S+?)\s*</a>', dist_section):
            code = m.group(1)
            name = m.group(2).strip()
            if name and len(name) >= 2:
                districts[name] = code

        # Also look in broader area
        if len(districts) < 30:
            for m in re.finditer(r'<a[^>]*href="/house-a(\d+)/"[^>]*>\s*([一-鿿]{2,8})\s*</a>', html):
                code = m.group(1)
                name = m.group(2).strip()
                if name and name not in districts:
                    districts[name] = code

        print(f"Found {len(districts)} districts:")
        for name, code in sorted(districts.items(), key=lambda x: int(x[1])):
            print(f"  '{name}': '{code}',")

        with open('fang_district_codes.json', 'w', encoding='utf-8') as f:
            json.dump(districts, f, ensure_ascii=False, indent=2)

        # Also extract the broader district list (including the top navigation)
        all_dists = {}
        for m in re.finditer(r'<a[^>]*href="/house-a(\d+)/"[^>]*>\s*([一-鿿]{2,12})\s*</a>', html):
            code = m.group(1)
            name = m.group(2).strip()
            if name and name not in all_dists:
                all_dists[name] = code

        print(f"\nAll district links: {len(all_dists)}")
        for name, code in sorted(all_dists.items(), key=lambda x: int(x[1])):
            print(f"  '{name}': '{code}',")

asyncio.run(main())
