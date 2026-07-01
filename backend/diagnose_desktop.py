"""
桌面站诊断脚本：探测 cq.esf.fang.com 当前页面结构和分页机制。

运行方式:
  cd backend
  python diagnose_desktop.py

输出:
  - 保存 HTML 到 backend/diagnosis/ 目录
  - 打印每个 URL 的响应摘要
"""

import asyncio
import json
import os
import sys
import re
import httpx
from pathlib import Path

# 确保 crawler 模块可导入
sys.path.insert(0, str(Path(__file__).parent))

OUTPUT_DIR = Path(__file__).parent / "diagnosis"
OUTPUT_DIR.mkdir(exist_ok=True)

DESKTOP_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/130.0.0.0 Safari/537.36"
)

# =======================================================
# 待探测的 URL 列表
# =======================================================
URLS_TO_TEST = {
    # 1. 桌面站首页
    "homepage": "https://cq.esf.fang.com/",
    # 2. 老版 URL 模式（不同分页参数变体）
    "old_pattern_p1": "https://cq.esf.fang.com/housing/house/list/yubei__0_0_0_0_1_0_0_0/",
    "old_pattern_p2": "https://cq.esf.fang.com/housing/house/list/yubei__0_0_0_0_2_0_0_0/",
    # 3. 尝试新版 URL
    "esf_root": "https://cq.esf.fang.com/esf/",
    # 4. 可能的分页模式
    "page_search_p1": "https://cq.esf.fang.com/housing/house/list/__0_0_0_0_1_0_0_0/",
    # 5. 尝试不带 slug 的模式
    "short_url_p1": "https://cq.esf.fang.com/housing/__0_0_0_0_1_0_0_0/",
    # 6. 尝试 /esf/ 子路径
    "esf_list": "https://cq.esf.fang.com/esf/housing/",
}


def save_html(label: str, html: str, status: int, url: str) -> None:
    """保存 HTML 采样"""
    filepath = OUTPUT_DIR / f"{label}.html"
    # 写入带元信息的 HTML
    header = f"<!-- status={status} url={url} -->\n"
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(header + html)
    size_kb = len(html.encode("utf-8")) / 1024
    print(f"  [SAVED] {filepath}  ({size_kb:.1f} KB)")


def quick_summary(html: str) -> dict:
    """快速提取 HTML 中的关键信息"""
    info = {
        "has_listings": False,
        "listing_count": 0,
        "pagination_links": [],
        "font_face_urls": [],
        "csrf_tokens": [],
        "ajax_urls": [],
        "total_listing_text": "",
        "district_links": [],
        "encoding": None,
    }

    # 检测编码声明
    m = re.search(r'charset=["\']?([a-zA-Z0-9_-]+)', html, re.I)
    if m:
        info["encoding"] = m.group(1)

    # 房源链接 (多种可能的模式)
    listing_patterns = [
        r'href="(/chushou/\d+[^"]*\.html?)"',    # 老版
        r'href="(/esf/[^"]+)"',                    # 新版
        r'href="(/house/[^"]+)"',
    ]
    seen = set()
    for pat in listing_patterns:
        for m in re.finditer(pat, html, re.I):
            link = m.group(1)
            if link not in seen:
                seen.add(link)
                if len(seen) <= 5:
                    info["listing_links"] = info.get("listing_links", []) + [link]
    info["listing_count"] = len(seen)

    # 分页链接
    pagination_patterns = [
        r'href="([^"]*page[=%](\d+)[^"]*)"',
        r'href="([^"]*__0_0_0_0_(\d+)_0_0_0_[^"]*)"',
        r'href="([^"]*[/?]p[=/-](\d+)[^"]*)"',
    ]
    for pat in pagination_patterns:
        for m in re.finditer(pat, html, re.I):
            info["pagination_links"].append({"url": m.group(1), "page": m.group(2)})

    # @font-face 字体
    for m in re.finditer(r"@font-face\s*\{[^}]*src:\s*url\(([^)]+)\)", html, re.I):
        info["font_face_urls"].append(m.group(1))

    # CSRF token
    for m in re.finditer(r'csrf[_-]?token["\']?\s*[=:]\s*["\']([^"\']+)', html, re.I):
        info["csrf_tokens"].append(m.group(1))

    # AJAX API 端点
    for m in re.finditer(r'(?:url|api|ajax|fetch)\s*["\']\s*:\s*["\']([^"\']+(?:api|ajax|data|search)[^"\']*)', html, re.I):
        info["ajax_urls"].append(m.group(1))

    # 总数文本
    m = re.search(r'(?:共|共计|找到|约)\s*(\d[\d,]*)\s*(?:套|条|房源)', html)
    if m:
        info["total_listing_text"] = m.group(0)

    # 区县链接
    for m in re.finditer(r'href="([^"]*(?:yubei|jiangbei|yuzhong|nanan|shapingba|jiulongpo|banan|dadukou|beibei)[^"]*)"', html, re.I):
        info["district_links"].append(m.group(1))

    return info


async def fetch_url(client: httpx.AsyncClient, label: str, url: str) -> tuple[str, str, int, bool]:
    """尝试获取一个 URL，返回 (label, html, status, success)"""
    print(f"\n[SCAN] [{label}] {url}")
    try:
        resp = await client.get(url, headers={"User-Agent": DESKTOP_UA})
        status = resp.status_code
        html = resp.text
        size_kb = len(resp.content) / 1024

        # 检测重定向
        redirect_info = ""
        if resp.history:
            redirect_info = f" (redirected via {len(resp.history)} hops: {' -> '.join(str(r.status_code) for r in resp.history)})"

        print(f"  OK status={status}{redirect_info}, size={size_kb:.1f}KB, encoding={resp.encoding}")

        if status >= 400:
            return label, "", status, False

        save_html(label, html, status, url)
        summary = quick_summary(html)
        print(f"  [CHART] listings found: {summary['listing_count']}")
        print(f"  [CHART] pagination links: {summary['pagination_links'][:5]}")
        print(f"  [CHART] @font-face: {len(summary['font_face_urls'])}")
        print(f"  [CHART] CSRF tokens: {len(summary['csrf_tokens'])}")
        print(f"  [CHART] AJAX URLs: {summary['ajax_urls'][:3]}")
        print(f"  [CHART] Total text: {summary['total_listing_text']}")
        print(f"  [CHART] District links: {summary['district_links'][:5]}")
        if summary.get("listing_links"):
            print(f"  [CHART] Sample listing links: {summary['listing_links'][:5]}")
        if summary["encoding"]:
            print(f"  [CHART] Declared charset: {summary['encoding']}")

        # 保存摘要
        with open(OUTPUT_DIR / f"{label}_summary.json", "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)

        return label, html, status, True

    except httpx.TimeoutException:
        print(f"  ERR TIMEOUT")
        return label, "", 0, False
    except Exception as e:
        print(f"  ERR ERROR: {type(e).__name__}: {e}")
        return label, "", 0, False


async def main():
    print("=" * 70)
    print("[HOME] 房天下桌面站 (cq.esf.fang.com) 诊断工具")
    print("=" * 70)

    # === 步骤 1: 先访问首页播种 Cookie ===
    print("\n" + "-" * 70)
    print("步骤 1: 播种 Cookie")
    print("-" * 70)

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(30.0),
        follow_redirects=True,
        headers={
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
        },
    ) as client:
        # 先访问首页
        try:
            resp = await client.get("https://cq.esf.fang.com/", headers={"User-Agent": DESKTOP_UA})
            cookies = dict(client.cookies)
            print(f"  Cookie count: {len(cookies)}")
            for name, value in cookies.items():
                val_preview = str(value)[:50] + ("..." if len(str(value)) > 50 else "")
                print(f"    {name}: {val_preview}")
        except Exception as e:
            print(f"  WARN  Cookie seed failed: {e}")

        # === 步骤 2: 测试各个 URL ===
        print("\n" + "-" * 70)
        print("步骤 2: URL 探测")
        print("-" * 70)

        results = {}
        for label, url in URLS_TO_TEST.items():
            label_out, html, status, ok = await fetch_url(client, label, url)
            results[label] = {"status": status, "ok": ok, "size": len(html)}
            await asyncio.sleep(2.0)  # 请求间隔

        # === 步骤 3: 如果有分页链接，进一步探测 ===
        print("\n" + "-" * 70)
        print("步骤 3: 深度分页测试")
        print("-" * 70)

        # 从结果中找可能的分页模式
        any_pages = False
        for label in URLS_TO_TEST:
            summary_path = OUTPUT_DIR / f"{label}_summary.json"
            if summary_path.exists():
                with open(summary_path) as f:
                    s = json.load(f)
                if s["pagination_links"]:
                    any_pages = True
                    print(f"\n  来源: {label}")
                    for pl in s["pagination_links"][:3]:
                        page_url = pl["url"]
                        if not page_url.startswith("http"):
                            page_url = "https://cq.esf.fang.com" + page_url
                        print(f"    测试第 {pl['page']} 页: {page_url}")
                        await asyncio.sleep(1.5)
                        try:
                            resp2 = await client.get(page_url, headers={"User-Agent": DESKTOP_UA})
                            pg_summary = quick_summary(resp2.text)
                            print(f"      status={resp2.status_code}, listings={pg_summary['listing_count']}")
                            save_html(f"paginated_{label}_p{pl['page']}", resp2.text, resp2.status_code, page_url)
                            # 对比第一页确认是否真的翻页了
                            if label in results and results[label]["ok"]:
                                with open(OUTPUT_DIR / f"{label}.html", encoding="utf-8") as f:
                                    first_html = f.read()
                                # 简单对比: 房源链接是否不同
                                m1 = re.findall(r'href="(/chushou/\d+[^"]*)"', first_html)
                                m2 = re.findall(r'href="(/chushou/\d+[^"]*)"', resp2.text)
                                overlap = set(m1) & set(m2)
                                print(f"      第1页有 {len(m1)} 条, 第{pl['page']}页有 {len(m2)} 条, 重叠 {len(overlap)} 条")
                                if overlap == set(m1) and len(m1) > 0:
                                    print(f"      WARN 内容完全相同！分页未生效")
                                elif overlap == set(m2) and len(m2) > 0:
                                    print(f"      WARN 内容完全相同！分页未生效")
                                else:
                                    print(f"      OK 内容不同，分页成功！")
                        except Exception as e:
                            print(f"      ERR {e}")

        if not any_pages:
            print("  WARN: No pagination links found - may be AJAX or JS-rendered")

    # === 步骤 4: 总结 ===
    print("\n" + "=" * 70)
    print("[LIST] 诊断总结")
    print("=" * 70)
    print(f"\n所有 HTML 文件已保存到: {OUTPUT_DIR}")
    print(f"请检查 {OUTPUT_DIR}/*.html 中的实际页面结构。")
    print("\n如果有页面成功返回房源数据，请把该 HTML 文件发给我分析。")

    for label in URLS_TO_TEST:
        r = results.get(label, {})
        status = r.get("status", "?")
        ok = "OK" if r.get("ok") else "ERR"
        print(f"  {ok} [{label}] status={status} size={r.get('size', 0)/1024:.1f}KB")


if __name__ == "__main__":
    asyncio.run(main())
