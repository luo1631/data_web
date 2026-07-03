"""
爬虫 CLI — cq.esf.fang.com 桌面站。

用法:
  python -m crawler crawl --max-pages 30
  python -m crawler crawl --incremental
  python -m crawler status
  python -m crawler incremental
  python -m crawler update-ages
"""

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

# 确保所有 logger 输出到 stdout，实时可见
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stdout,
    force=True,
)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


def _get_session_factory():
    from app.database import async_session
    return async_session


# ── crawl ──────────────────────────────────────────

async def cmd_crawl(args):
    from crawler.engine import CrawlEngine

    engine = CrawlEngine(_get_session_factory())
    batch_type = "incremental" if args.incremental else "full"
    district_filter = None
    if args.districts:
        district_filter = [d.strip() for d in args.districts.split(",") if d.strip()]
    print(
        f"Starting {batch_type} crawl, max_pages={args.max_pages}"
        + (f", districts={district_filter}" if district_filter else "")
        + (", no-early-stop" if args.no_early_stop else "")
    )

    try:
        result = await engine.crawl_all(
            batch_type=batch_type,
            max_pages=args.max_pages,
            district_filter=district_filter,
            no_early_stop=args.no_early_stop,
        )
        print("\n── Done ──")
        for k, v in result.items():
            print(f"  {k}: {v}")
    except KeyboardInterrupt:
        print("\n[STOP] Interrupted, progress saved.")
        engine.stop()
    except Exception as e:
        print(f"\n[FATAL] {e}")
        engine.stop()


# ── anjuke crawl ────────────────────────────────────

async def cmd_anjuke(args):
    from crawler.anjuke_engine import AnjukeCrawlEngine

    engine = AnjukeCrawlEngine(_get_session_factory())
    area_filter = None
    if args.areas:
        area_filter = [a.strip() for a in args.areas.split(",") if a.strip()]
    print(
        f"Starting anjuke crawl, max_pages={args.max_pages}"
        + (f", areas={area_filter}" if area_filter else "")
        + (", no-early-stop" if args.no_early_stop else "")
    )

    try:
        result = await engine.crawl_all(
            batch_type="full",
            max_pages=args.max_pages,
            area_filter=area_filter,
            no_early_stop=args.no_early_stop,
        )
        print("\n── Done ──")
        for k, v in result.items():
            print(f"  {k}: {v}")
    except KeyboardInterrupt:
        print("\n[STOP] Interrupted, progress saved.")
        engine.stop()
    except Exception as e:
        print(f"\n[FATAL] {e}")
        engine.stop()


# ── incremental / update-ages / status ──────────────

async def cmd_incremental(args):
    from scheduler.jobs import run_weekly_incremental_crawl
    print("[Incremental] Starting...")
    try:
        result = await run_weekly_incremental_crawl()
        print("[Incremental] Done:", result)
    except Exception as e:
        print(f"[Incremental] Failed: {e}")
        raise


async def cmd_update_ages(_args):
    from scheduler.jobs import run_daily_listing_age_update
    print("[UpdateAges] Starting...")
    try:
        await run_daily_listing_age_update()
        print("[UpdateAges] Done")
    except Exception as e:
        print(f"[UpdateAges] Failed: {e}")
        raise


async def cmd_status(_args):
    from sqlalchemy import select, desc
    from app.models import CrawlBatch, CrawlTask

    async with _get_session_factory() as db:
        result = await db.execute(
            select(CrawlBatch).order_by(desc(CrawlBatch.id)).limit(5))
        batches = result.scalars().all()

        if not batches:
            print("No crawl batches yet.")
            return

        for batch in batches:
            print(f"── Batch #{batch.id} ──")
            print(f"  Type: {batch.type}  Status: {batch.status}")
            print(f"  Started:  {batch.started_at}")
            print(f"  Finished: {batch.finished_at}")
            print(f"  New: {batch.new_listings}  Updated: {batch.updated_listings}")
            if batch.error_summary:
                try:
                    errs = json.loads(batch.error_summary) if isinstance(batch.error_summary, str) else batch.error_summary
                    print(f"  Errors: {len(errs) if isinstance(errs, list) else 0}")
                except Exception:
                    pass
            print()

            tasks_result = await db.execute(
                select(CrawlTask).where(CrawlTask.batch_id == batch.id).limit(5))
            for t in tasks_result.scalars().all():
                print(f"    Task #{t.id}  District: {t.district_id}  "
                      f"Status: {t.status}  Pages: {t.page_start}-{t.page_end}  "
                      f"Listings: {t.listings_found}")


# ── main ───────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="房天下爬虫 (cq.esf.fang.com 桌面站)")
    sub = parser.add_subparsers(dest="command")

    p = sub.add_parser("crawl", help="运行爬虫")
    p.add_argument("--max-pages", type=int, default=30, help="最大翻页数")
    p.add_argument("--incremental", action="store_true")
    p.add_argument("--districts", type=str, default=None, help="限定区县名，逗号分隔 (如: 渝中,两江新区)")
    p.add_argument("--no-early-stop", action="store_true", help="禁用零产出跳页和提前终止（首次全量爬取用）")
    p.set_defaults(func=cmd_crawl)

    p = sub.add_parser("anjuke", help="运行安居客爬虫")
    p.add_argument("--max-pages", type=int, default=100, help="最大翻页数")
    p.add_argument("--areas", type=str, default=None, help="限定子区域，逗号分隔 (如: yuzhong-daping,nanana-nanping)")
    p.add_argument("--no-early-stop", action="store_true", help="禁用零产出跳页和提前终止")
    p.set_defaults(func=cmd_anjuke)

    p = sub.add_parser("status", help="查看爬取进度")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("incremental", help="增量爬取 (定时任务)")
    p.add_argument("--max-pages", type=int, default=2)
    p.set_defaults(func=cmd_incremental)

    p = sub.add_parser("update-ages", help="更新房源龄期 (定时任务)")
    p.set_defaults(func=cmd_update_ages)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return
    asyncio.run(args.func(args))


if __name__ == "__main__":
    main()
