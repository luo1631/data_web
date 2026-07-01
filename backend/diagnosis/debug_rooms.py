"""Debug room count extraction from desktop listing pages."""
import asyncio, re, sys, json
sys.path.insert(0, '..')
from crawler.fetcher import Fetcher

async def main():
    async with Fetcher() as fetcher:
        html, url = await fetcher.fetch_list_page('058', 1)
        print(f'URL: {url}')
        print(f'HTML size: {len(html)}')

        # Find tel_shop sections
        pattern = r'<p\s+class="tel_shop"[^>]*>(.*?)</p>'
        matches = re.findall(pattern, html, re.DOTALL)
        print(f'Found {len(matches)} tel_shop paragraphs')

        for i, m in enumerate(matches[:3]):
            clean = re.sub(r'<[^>]+>', ' | ', m)  # Replace tags with pipes
            clean = re.sub(r'\s+', ' ', clean).strip()
            print(f'\n--- tel_shop #{i+1} ---')
            print(clean[:500])

        # Check for room patterns in the whole HTML
        # Try different flavors
        for pat in [
            r'(\d+)室(\d+)厅(\d+)卫',
            r'(\d+)室(\d+)厅',
            r'卧室[：:]\s*(\d+)',
            r'(\d+)个卧室',
            r'户型[：:]\s*(\S+)',
        ]:
            found = re.findall(pat, html)
            if found:
                print(f'\nPattern "{pat}": {found[:5]}')

if __name__ == '__main__':
    asyncio.run(main())
