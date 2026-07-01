"""Audit which fields are available in tel_shop text."""
import asyncio, re, sys
sys.path.insert(0, "..")
from crawler.playwright_fetcher import PlaywrightFetcher
from bs4 import BeautifulSoup

async def main():
    async with PlaywrightFetcher(headless=True) as pf:
        html, _ = await pf.fetch_page(1)
        soup = BeautifulSoup(html, "lxml")
        dls = soup.select("dl[data-bg]")[:20]

        stats = {"rooms": 0, "area": 0, "floor_level": 0, "decoration": 0,
                 "orientation": 0, "total_floors": 0, "building_type": 0}

        for i, dl in enumerate(dls):
            tel = dl.select_one(".tel_shop")
            if not tel:
                print(f"{i+1}: NO tel_shop")
                continue
            text = tel.get_text(" ", strip=True)
            raw = str(tel)

            # Floor: "低层 (共1层)" or "高层 (共24层)"
            floor_match = re.search(r"(低层|中层|高层|底层|顶层)", text)
            total_match = re.search(r"共\s*(\d+)层", text)

            # Orientation
            orient_match = re.search(r"(南向|北向|南北|东南|西南|东北|西北|东向|西向)", text)

            # Decoration
            dec_match = re.search(r"(精装|简装|毛坯|豪装|中装|精装修|豪华装修|简单装修)", text)

            # Building type from link_rk
            bt_el = tel.select_one(".link_rk")
            bt = bt_el.get_text(strip=True) if bt_el else None

            rooms = bool(re.search(r"\d+室\d+厅", text))
            area = bool(re.search(r"[\d.]+\s*[㎡²O]", text))

            for k, v in [("rooms", rooms), ("area", area),
                         ("floor_level", bool(floor_match)),
                         ("decoration", bool(dec_match)),
                         ("orientation", bool(orient_match)),
                         ("total_floors", bool(total_match)),
                         ("building_type", bool(bt))]:
                if v:
                    stats[k] += 1

            if i < 10:
                print(f"DL{i+1}: {text[:200]}")
                if floor_match: print(f"  -> floor: {floor_match.group(0)}")
                if total_match: print(f"  -> total_floors: {total_match.group(1)}")
                if dec_match: print(f"  -> dec: {dec_match.group(0)}")
                if orient_match: print(f"  -> orient: {orient_match.group(0)}")
                if bt: print(f"  -> building_type: {bt}")
                print()

        print(f"\nField coverage in {len(dls)} listings:")
        for k, v in sorted(stats.items(), key=lambda x: -x[1]):
            pct = v / len(dls) * 100
            bar = "#" * int(pct / 5)
            print(f"  {k:15s}: {v:3d}/{len(dls)} ({pct:.0f}%) {bar}")

asyncio.run(main())
