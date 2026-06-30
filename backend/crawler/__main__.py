"""
爬虫 CLI 工具：用于测试和运行爬虫。

用法:
  # 测试单个请求
  python -m crawler test-fetch --slug yubei --page 1
  python -m crawler test-fetch-detail --listing-id 1234567890

  # 测试解析
  python -m crawler test-parse-list --slug yubei --page 1
  python -m crawler test-parse-detail --listing-id 1234567890

  # 测试字体
  python -m crawler test-font --font-url https://img.fang.com/font/house2.woff
  python -m crawler calibrate-font --font-url https://img.fang.com/font/house2.woff

  # 爬取
  python -m crawler crawl --districts 1,2,3
  python -m crawler crawl --all

  # 状态
  python -m crawler status
"""

import argparse
import asyncio
import sys
from pathlib import Path

# 确保 backend/ 在 sys.path 中（从项目根目录运行时）
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


def _get_session_factory():
    """懒加载 database 模块（避免在 CLI 子命令不需要时初始化）。"""
    from app.database import async_session
    return async_session


# ============================================================
# 子命令: test-fetch
# ============================================================

async def cmd_test_fetch(args):
    """测试列表页抓取"""
    from crawler.fetcher import Fetcher
    from crawler.parsers import ListParser

    async with Fetcher() as fetcher:
        print(f"Fetching list page: slug={args.slug}, page={args.page} ...")
        html = await fetcher.fetch_list_page(args.slug, args.page)

        if args.output:
            Path(args.output).write_text(html, encoding="utf-8")
            print(f"[OK] Saved to {args.output} ({len(html)} bytes)")
        else:
            print(f"[OK] Got {len(html)} bytes")
            ids = ListParser.parse_listing_ids(html)
            count = ListParser.parse_total_count(html)
            print(f"     Total count: {count}")
            print(f"     IDs on page: {len(ids)}")
            if ids:
                print(f"     First 5 IDs: {ids[:5]}")


async def cmd_test_fetch_detail(args):
    """测试详情页抓取"""
    from crawler.fetcher import Fetcher

    async with Fetcher() as fetcher:
        print(f"Fetching detail page: listing_id={args.listing_id} ...")
        html = await fetcher.fetch_detail_page(args.listing_id)

        if args.output:
            Path(args.output).write_text(html, encoding="utf-8")
            print(f"[OK] Saved to {args.output} ({len(html)} bytes)")
        else:
            print(f"[OK] Got {len(html)} bytes")
            # 检查是否有字体引用
            import re
            fonts = re.findall(r"url\(['\"]?(//[^'\")]*?\.woff[^'\")]*)['\"]?\)", html)
            if fonts:
                print(f"     Font URLs found: {fonts[:3]}")


# ============================================================
# 子命令: test-parse-list
# ============================================================

async def cmd_test_parse_list(args):
    """测试列表页解析"""
    from crawler.fetcher import Fetcher
    from crawler.parsers import ListParser

    async with Fetcher() as fetcher:
        print(f"Fetching & parsing list page: slug={args.slug}, page={args.page} ...")
        html = await fetcher.fetch_list_page(args.slug, args.page)

    ids = ListParser.parse_listing_ids(html)
    total = ListParser.parse_total_count(html)
    has = ListParser.has_listings(html)

    print(f"  Total count : {total}")
    print(f"  IDs found   : {len(ids)}")
    print(f"  Has listings: {has}")
    if ids:
        print(f"  Sample IDs  : {ids[:10]}")


# ============================================================
# 子命令: test-parse-detail
# ============================================================

async def cmd_test_parse_detail(args):
    """测试详情页解析"""
    from crawler.fetcher import Fetcher
    from crawler.parsers import DetailParser

    if args.file:
        html = Path(args.file).read_text(encoding="utf-8")
        source_url = "file://" + args.file
        listing_id = args.listing_id or "test"
    else:
        async with Fetcher() as fetcher:
            html = await fetcher.fetch_detail_page(args.listing_id)
        source_url = f"https://cq.esf.fang.com/chushou/{args.listing_id}.htm"
        listing_id = args.listing_id

    parser = DetailParser(listing_id, source_url)
    parsed = parser.parse(html)

    print("── ParsedListing ──")
    for field_name, value in vars(parsed).items():
        if value is not None:
            print(f"  {field_name}: {value!r}")


# ============================================================
# 子命令: test-font
# ============================================================

async def cmd_test_font(args):
    """测试字体下载和解析"""
    from crawler.fetcher import Fetcher
    from crawler.parsers import FontDecryptor
    from crawler.constants import FONT_MAPPING_CACHE
    import hashlib

    async with Fetcher() as fetcher:
        print(f"Downloading font: {args.font_url}")
        font_bytes = await fetcher.download_font_file(args.font_url)
        md5 = hashlib.md5(font_bytes).hexdigest()
        print(f"  Size: {len(font_bytes)} bytes")
        print(f"  MD5:  {md5}")
        print()

        glyphs = FontDecryptor.parse_font_glyphs(font_bytes)
        print(f"Encrypted glyphs found: {len(glyphs)}")
        for gname, char in sorted(glyphs.items()):
            print(f"  {gname:<25} → U+{ord(char):04X}  ({char})")

        if md5 in FONT_MAPPING_CACHE:
            print(f"\n[OK] Font is cached! Mapping:")
            for k, v in FONT_MAPPING_CACHE[md5].items():
                print(f"  {k!r} → {v!r}")
        else:
            print(f"\n[WARN] Font NOT cached. Run 'calibrate-font' to add mapping.")


# ============================================================
# 子命令: calibrate-font
# ============================================================

async def cmd_calibrate_font(args):
    """交互式字体标定工具"""
    from crawler.fetcher import Fetcher
    from crawler.parsers import FontDecryptor
    from crawler.constants import FONT_MAPPING_CACHE
    import hashlib

    async with Fetcher() as fetcher:
        print(f"Downloading font: {args.font_url}")
        font_bytes = await fetcher.download_font_file(args.font_url)
        md5 = hashlib.md5(font_bytes).hexdigest()
        print(f"MD5: {md5}")

        if md5 in FONT_MAPPING_CACHE:
            print("[OK] This font is already cached.")
            return

        glyphs = FontDecryptor.parse_font_glyphs(font_bytes)
        chars = sorted({chr(u) for u in FontDecryptor.parse_font_glyphs.__defaults__ or []}) if False else []

        # 显示字形供标定
        print(f"\nEncrypted glyphs ({len(glyphs)}):")
        glyph_list = sorted(glyphs.items())
        for i, (gname, char) in enumerate(glyph_list):
            print(f"  [{i}] {gname:<25} char={char!r}")

        print(
            "\n请在浏览器中打开任意房天下房源详情页，"
            "对照渲染后的价格数字，为每个字符输入对应的数字 (0-9)。"
            "\n如果某个字符不在价格中出现，直接按回车跳过。\n"
        )

        mapping: dict[str, str] = {}
        for i, (gname, char) in enumerate(glyph_list):
            digit = input(f"  [{i}] {char!r} → 数字? ").strip()
            if digit and digit.isdigit() and 0 <= int(digit) <= 9:
                mapping[char] = digit

        if mapping:
            FONT_MAPPING_CACHE[md5] = mapping
            print(f"\n[OK] 已添加 {len(mapping)} 条映射。")
            print("请将以下内容追加到 backend/crawler/constants.py 的 FONT_MAPPING_CACHE:")
            print(f"    \"{md5}\": {{")
            for k, v in sorted(mapping.items()):
                print(f"        {k!r}: {v!r},")
            print("    },")
        else:
            print("\n未添加任何映射。")


# ============================================================
# 子命令: crawl
# ============================================================

async def cmd_crawl(args):
    """运行爬虫"""
    from crawler.engine import CrawlEngine

    async_session = _get_session_factory()
    engine = CrawlEngine(async_session)

    district_ids = None
    if not args.all:
        district_ids = [int(x.strip()) for x in args.districts.split(",")]

    print(f"Starting {'full' if not district_ids else 'partial'} crawl...")
    print(f"Districts: {district_ids or 'ALL (38)'}")
    print()

    try:
        result = await engine.crawl_all(
            district_ids=district_ids,
            batch_type=args.type,
            max_pages=args.max_pages,
        )
        print("\n── Crawl Complete ──")
        for k, v in result.items():
            print(f"  {k}: {v}")
    except KeyboardInterrupt:
        print("\n[STOP] Interrupted. Progress saved to database.")
        engine.stop()
    except Exception as e:
        print(f"\n[FATAL] {e}")
        engine.stop()


# ============================================================
# 子命令: status
# ============================================================

async def cmd_status(_args):
    """查看最近的爬取批次状态"""
    from sqlalchemy import select, desc
    from app.models import CrawlBatch, CrawlTask

    async_session = _get_session_factory()
    async with async_session() as db:
        result = await db.execute(
            select(CrawlBatch).order_by(desc(CrawlBatch.id)).limit(5)
        )
        batches = result.scalars().all()

        if not batches:
            print("No crawl batches found.")
            return

        for batch in batches:
            print(f"── Batch #{batch.id} ──")
            print(f"  Type: {batch.type}  Status: {batch.status}")
            print(f"  Started:  {batch.started_at}")
            print(f"  Finished: {batch.finished_at}")
            print(f"  Tasks: {batch.completed_tasks}/{batch.total_tasks}")
            print(f"  New: {batch.new_listings}  "
                  f"Updated: {batch.updated_listings}  "
                  f"Removed: {batch.removed_listings}")
            print()

            # 任务明细
            tasks_result = await db.execute(
                select(CrawlTask).where(CrawlTask.batch_id == batch.id)
            )
            for task in tasks_result.scalars().all():
                print(f"    Task #{task.id}  "
                      f"District: {task.district_id}  "
                      f"Status: {task.status}  "
                      f"Pages: {task.page_start}-{task.page_end}  "
                      f"Listings: {task.listings_found}")


# ============================================================
# main
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="房天下爬虫 CLI — 测试与运行"
    )
    sub = parser.add_subparsers(dest="command")

    # test-fetch
    p = sub.add_parser("test-fetch", help="测试列表页抓取")
    p.add_argument("--slug", required=True, help="区县 slug (如 yubei)")
    p.add_argument("--page", type=int, default=1, help="页码")
    p.add_argument("--output", help="保存 HTML 到文件")
    p.set_defaults(func=cmd_test_fetch)

    # test-fetch-detail
    p = sub.add_parser("test-fetch-detail", help="测试详情页抓取")
    p.add_argument("--listing-id", required=True, help="房天下房源 ID")
    p.add_argument("--output", help="保存 HTML 到文件")
    p.set_defaults(func=cmd_test_fetch_detail)

    # test-parse-list
    p = sub.add_parser("test-parse-list", help="测试列表页解析")
    p.add_argument("--slug", required=True, help="区县 slug")
    p.add_argument("--page", type=int, default=1, help="页码")
    p.set_defaults(func=cmd_test_parse_list)

    # test-parse-detail
    p = sub.add_parser("test-parse-detail", help="测试详情页解析")
    p.add_argument("--listing-id", default="test", help="房源 ID")
    p.add_argument("--file", help="从文件读取 HTML（离线测试）")
    p.set_defaults(func=cmd_test_parse_detail)

    # test-font
    p = sub.add_parser("test-font", help="测试字体解析")
    p.add_argument("--font-url", required=True, help="字体文件 URL")
    p.set_defaults(func=cmd_test_font)

    # calibrate-font
    p = sub.add_parser("calibrate-font", help="交互式字体标定")
    p.add_argument("--font-url", required=True, help="字体文件 URL")
    p.set_defaults(func=cmd_calibrate_font)

    # crawl
    p = sub.add_parser("crawl", help="运行爬虫")
    p.add_argument("--districts", help="逗号分隔的区县 ID (如 1,2,3)")
    p.add_argument("--all", action="store_true", help="爬取全部 38 区县")
    p.add_argument("--type", default="full", choices=["full", "incremental"])
    p.add_argument("--max-pages", type=int, default=100, help="每区县最大页数")
    p.set_defaults(func=cmd_crawl)

    # status
    p = sub.add_parser("status", help="查看爬取进度")
    p.set_defaults(func=cmd_status)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return

    asyncio.run(args.func(args))


if __name__ == "__main__":
    main()
