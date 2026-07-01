"""Check detail page for font encryption."""
import asyncio, re, httpx

DESKTOP_UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130.0.0.0 Safari/537.36'

async def main():
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        url = 'https://cq.esf.fang.com/chushou/3_204649634.htm'
        resp = await client.get(url, headers={'User-Agent': DESKTOP_UA})

        print(f'status={resp.status_code}, size={len(resp.text)/1024:.1f}KB')
        print(f'Content-Type: {resp.headers.get("content-type", "?")}')

        # Check for @font-face
        ff = re.findall(r'@font-face\s*\{[^}]*\}', resp.text, re.I | re.DOTALL)
        print(f'\n@font-face blocks found: {len(ff)}')
        for i, f in enumerate(ff):
            print(f'  [{i}] {f[:300]}')

        # Check font file URLs
        fonts = re.findall(r'(https?://[^\"\'\s]+\.(?:woff2?|ttf|eot))', resp.text, re.I)
        print(f'\nFont file URLs: {fonts}')

        # Check clear text prices
        clear_prices = re.findall(r'<span[^>]*>\s*([\d.]+)\s*万\s*</span>', resp.text)
        print(f'\nClear text prices on detail page: {clear_prices[:10]}')

        # Check for encrypted chars (PUA range)
        pua = re.findall(r'[-]+', resp.text)
        print(f'\nPUA (Private Use Area) chars found: {len(pua)}')
        if pua:
            print(f'  Samples: {pua[:5]}')

        # Check for base64 encoded fonts
        b64 = re.findall(r'base64,([A-Za-z0-9+/=]{50,500})', resp.text)
        print(f'\nBase64 encoded font data: {len(b64)} blocks')

        # Look for price-related sections
        for label, pat in [
            ('total_price_div', r'<div[^>]*class=\"[^\"]*price[^\"]*\"[^>]*>(.*?)</div>'),
            ('price_span', r'<span[^>]*class=\"[^\"]*price[^\"]*\"[^>]*>(.*?)</span>'),
            ('total_price', r'(?:总价|total[Pp]rice).{0,50}'),
        ]:
            matches = re.findall(pat, resp.text, re.I | re.DOTALL)
            print(f'\n{label}: {matches[:3]}')

        with open('detail_sample.html', 'w', encoding='utf-8') as f:
            f.write(resp.text)
        print('\nSaved detail_sample.html')

asyncio.run(main())
