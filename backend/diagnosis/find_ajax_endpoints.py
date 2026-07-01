"""Search homepage HTML for AJAX pagination endpoints."""
import httpx, asyncio, re, json

async def main():
    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        resp = await client.get('https://cq.esf.fang.com/', headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130.0.0.0 Safari/537.36'
        })
        html = resp.text

        # Find ALL URL-like strings in script blocks
        scripts = re.findall(r'<script[^>]*>(.*?)</script>', html, re.DOTALL)
        print(f"Found {len(scripts)} inline scripts\n")

        for i, script in enumerate(scripts):
            if not script.strip():
                continue
            # Look for interesting patterns
            interesting = False
            for kw in ['api', 'ajax', 'fetch', 'page', 'search', 'list', 'house', 'esf', 'fang', 'url']:
                if kw in script.lower():
                    interesting = True
                    break
            if not interesting:
                continue

            print(f"=== Script #{i+1} ({len(script)} chars) ===")
            # Extract URLs
            urls = re.findall(r"""['\"]([^'\"]*(?:api|ajax|search|list|page|house|esf)[^'\"]*)['\"]""", script, re.I)
            for u in urls[:10]:
                print(f"  URL: {u[:200]}")
            # Extract function calls with 'page' param
            funcs = re.findall(r'(\w+Page\w*|\w+page\w*|goPage|nextPage|loadMore|fetchList|getList)\s*\(', script, re.I)
            for f in funcs:
                print(f"  FUNC: {f}")
            print()

        # Also check external script sources
        print("=== EXTERNAL SCRIPTS ===")
        for m in re.finditer(r'<script[^>]*src="([^"]+)"', html):
            src = m.group(1)
            if any(kw in src.lower() for kw in ['esf', 'house', 'search', 'list', 'page', 'fang']):
                print(f"  {src[:200]}")

        # Look at the pagination section more carefully
        page_section = re.search(r'class="page_box".*?</div>\s*</div>', html, re.DOTALL)
        if page_section:
            print(f"\n=== PAGINATION HTML ===\n{page_section.group(0)[:1000]}")

        # Check response headers for any clues
        print(f"\n=== RESPONSE HEADERS ===")
        for k, v in resp.headers.items():
            print(f"  {k}: {v}")

asyncio.run(main())
