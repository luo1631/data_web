"""Explore the AJAX listing API endpoints."""
import httpx, asyncio, re, json

async def main():
    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        # Seed homepage for cookies
        resp = await client.get('https://cq.esf.fang.com/', headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/130.0.0.0 Safari/537.36'
        })
        html = resp.text

        # Extract pageConfig values
        print("=== pageConfig ===")
        config = {}
        for m in re.finditer(r"pageConfig\.(\w+)\s*=\s*['\"]?([^'\";]+)['\"]?", html):
            config[m.group(1)] = m.group(2)
        for k, v in sorted(config.items()):
            print(f"  {k}: {v}")

        # The key AJAX endpoints found
        base_url = "https://cq.esf.fang.com"
        endpoints = [
            "/asynclist/EsfListAjax/getNewHouse",
            "/asynclist/commoncontroller/getLoginUserInfo",
            "/asynclist/EsfListAjax/getList",        # guess
            "/asynclist/EsfListAjax/getHouseList",    # guess
            "/asynclist/EsfListAjax/search",          # guess
        ]

        # Get csrfToken from cookies
        csrf = None
        for cookie in client.cookies.jar:
            if cookie.name == 'csrfToken':
                csrf = cookie.value
        print(f"\ncsrfToken: {csrf}")

        print("\n=== TESTING AJAX ENDPOINTS ===")
        for endpoint in endpoints:
            url = base_url + endpoint
            try:
                resp = await client.get(url, headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/130.0.0.0 Safari/537.36',
                    'Referer': 'https://cq.esf.fang.com/',
                    'X-Requested-With': 'XMLHttpRequest',
                    'Accept': 'application/json, text/javascript, */*; q=0.01',
                })
                bot = 'check.3g' in str(resp.url)
                content_preview = resp.text[:200]
                print(f"\n  {endpoint}")
                print(f"    status={resp.status_code} bot={bot} content={content_preview}")
            except Exception as e:
                print(f"\n  {endpoint}")
                print(f"    ERROR: {e}")
            await asyncio.sleep(2)

        # Also test the newhouse endpoint with parameters
        print("\n=== getNewHouse with POST params ===")
        try:
            resp = await client.post(
                base_url + "/asynclist/EsfListAjax/getNewHouse",
                data={"city": "cq", "page": "2"},
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/130.0.0.0 Safari/537.36',
                    'Referer': 'https://cq.esf.fang.com/',
                    'X-Requested-With': 'XMLHttpRequest',
                }
            )
            print(f"  status={resp.status_code} content={resp.text[:300]}")
        except Exception as e:
            print(f"  ERROR: {e}")

asyncio.run(main())
