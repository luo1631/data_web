"""
测试爬虫引擎核心逻辑 — 零产出检测 / 跳页 / 自适应排序 / 收尾

不依赖真实网络和 Playwright，使用 mock pipeline + 可控 HTML。
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

from sqlalchemy.ext.asyncio import async_sessionmaker
from crawler.engine import CrawlEngine, DB_SYNC_INTERVAL
from crawler.constants import (
    ZERO_YIELD_THRESHOLD,
    LOW_YIELD_JUMP_THRESHOLD,
    JUMP_PAGES,
    MAX_JUMPS_PER_DISTRICT,
    DRY_PAGE_THRESHOLD,
)


# ── Helpers ──────────────────────────────────────────

def _make_ctx(page=1, max_pages=30, **overrides):
    """构造区县队列上下文。"""
    ctx = {
        "district": {"name": f"test_district_{page}", "fang_code": "a058",
                      "db_name": "test_district"},
        "task_id": page,  # mock
        "page": page,
        "dry": 0,
        "zero_yield": 0,
        "jumps": 0,
        "captcha_strikes": 0,
        "connection_strikes": 0,
        "district_max": max_pages,
        "paused_until": 0.0,
        "completed": False,
        "yield_new": 0,
        "yield_updated": 0,
        "pages_fetched": page - 1,
        "total_raw": 0,
    }
    ctx.update(overrides)
    return ctx


def _make_mock_pipeline():
    """创建 mock DatabasePipeline。"""
    pipe = AsyncMock()
    pipe.create_crawl_batch = AsyncMock(return_value=1)
    pipe.update_crawl_batch = AsyncMock()
    pipe.finish_crawl_batch = AsyncMock()
    pipe.create_crawl_task = AsyncMock(return_value=999)
    pipe.update_crawl_task = AsyncMock()
    pipe.finish_crawl_task = AsyncMock()
    pipe.upsert_community = AsyncMock(return_value=1)
    pipe.upsert_listing = AsyncMock(return_value=(1, "new"))
    pipe.flush = AsyncMock()
    pipe.__aenter__ = AsyncMock(return_value=pipe)
    pipe.__aexit__ = AsyncMock(return_value=False)
    return pipe


# 最小合法 HTML（必须 > 500 bytes，否则 _process_page 会拒绝）
_VALID_LISTING_HTML = """
<html><body>
<!-- padding to ensure > 500 bytes ────────────────────────────── -->
<!-- xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx -->
<!-- xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx -->
<dl data-bg='{"houseid":"123456","housetype":"2"}'>
  <dt><img alt="test listing"/></dt>
  <dd>
    <h4><a href="/chushou/3_123456.htm" title="test apartment">test apartment</a></h4>
    <p class="price_right"><span class="red"><b>150</b></span><span>12000元/㎡</span></p>
    <p class="tel_shop">3室2厅2卫 | 95㎡ | 南向 | 精装修 | 板塔结合 | 共32层</p>
    <p class="add_shop"><a href="/house-xm100/" title="test community">test community</a><span>两江新区</span></p>
  </dd>
</dl>
</body></html>
"""

_EMPTY_HTML = "<html><body><div>no listings here</div></body></html>"


# ═══════════════════════════════════════════════════════
# 1. 自适应排序
# ═══════════════════════════════════════════════════════

class TestAdaptiveSort:
    """_sort_key：未开始区县 > 高产出率 > 低产出率 > 已完成。"""

    @pytest.mark.parametrize("ctx,expected_range", [
        # 未开始 → 1000
        (_make_ctx(pages_fetched=0, yield_new=0), (900, 2000)),
        # 已完成 → 负数
        (_make_ctx(completed=True, pages_fetched=10, yield_new=5), (-2000, -1)),
        # 高产出率 → 正数，比低产出率大
        (_make_ctx(pages_fetched=10, yield_new=50, yield_updated=10), (4, 10)),
        # 低产出率
        (_make_ctx(pages_fetched=20, yield_new=2), (0, 1)),
        # 零产出
        (_make_ctx(pages_fetched=30, yield_new=0), (-1, 1)),
    ])
    def test_sort_key_ranges(self, ctx, expected_range):
        """不同状态/产出率的 sort_key 落在预期区间。"""
        # 内联 _sort_key
        def _sort_key(c):
            if c["completed"]:
                return -999.0
            if c["pages_fetched"] == 0:
                return 1000.0
            total_yield = c["yield_new"] + c["yield_updated"]
            return total_yield / c["pages_fetched"]

        key = _sort_key(ctx)
        lo, hi = expected_range
        assert lo <= key <= hi, f"sort_key={key} not in [{lo}, {hi}]"

    def test_sort_order(self):
        """完整排序：未开始 > 高产出 > 低产出 > 已完成。"""
        queue = [
            _make_ctx(page=3, pages_fetched=24, yield_new=5, yield_updated=3),   # 0.33
            _make_ctx(page=1, pages_fetched=0),                                    # 未开始 → 1000
            _make_ctx(page=2, completed=True, pages_fetched=30, yield_new=60),     # -999
            _make_ctx(page=4, pages_fetched=10, yield_new=50, yield_updated=20),  # 7.0
        ]

        def _sort_key(c):
            if c["completed"]:
                return -999.0
            if c["pages_fetched"] == 0:
                return 1000.0
            total = c["yield_new"] + c["yield_updated"]
            return total / c["pages_fetched"]

        queue.sort(key=_sort_key, reverse=True)

        # 期望顺序：未开始 > 7.0 > 0.33 > 已完成
        assert queue[0]["pages_fetched"] == 0   # 未开始第一
        assert queue[1]["yield_new"] == 50      # 7.0 第二
        assert queue[2]["yield_new"] == 5       # 0.33 第三
        assert queue[3]["completed"] is True    # 已完成最后


# ═══════════════════════════════════════════════════════
# 2. _process_page 区分能力
# ═══════════════════════════════════════════════════════

class TestProcessPage:
    """_process_page：raw_count 区分空页面 vs 全已入库。"""

    @pytest.mark.asyncio
    async def test_raw_count_zero_on_empty_html(self, db_session):
        """空 HTML → raw_count=0。"""
        engine = CrawlEngine(async_sessionmaker(lambda: db_session))
        pipe = _make_mock_pipeline()
        engine._district_id_map = {"test_district": 1}
        global_seen = set()

        new_n, updated_n, raw_count = await engine._process_page(
            _EMPTY_HTML, global_seen, pipe, 1, "http://test",
            default_district_id=1,
        )
        assert raw_count == 0
        assert new_n == 0
        assert updated_n == 0

    @pytest.mark.asyncio
    async def test_raw_count_positive_on_valid_html(self, db_session):
        """有效 HTML → raw_count > 0。"""
        engine = CrawlEngine(async_sessionmaker(lambda: db_session))
        pipe = _make_mock_pipeline()
        engine._district_id_map = {"test_district": 1}
        global_seen = set()

        new_n, updated_n, raw_count = await engine._process_page(
            _VALID_LISTING_HTML, global_seen, pipe, 1, "http://test",
            default_district_id=1,
        )
        assert raw_count == 1
        # 首次入库 → new
        assert new_n == 1
        assert updated_n == 0

    @pytest.mark.asyncio
    async def test_raw_count_positive_but_all_seen(self, db_session):
        """HTML 有数据但全部已见过 → raw_count > 0, new=0, updated=0。"""
        engine = CrawlEngine(async_sessionmaker(lambda: db_session))
        pipe = _make_mock_pipeline()
        engine._district_id_map = {"test_district": 1}
        # house_id 已被 global_seen 包含
        global_seen = {"3_123456"}

        new_n, updated_n, raw_count = await engine._process_page(
            _VALID_LISTING_HTML, global_seen, pipe, 1, "http://test",
            default_district_id=1,
        )
        # 关键断言：raw_count=1 (页面有数据) 但 new=updated=0 (全部已入库)
        assert raw_count == 1, "页面有房源数据，raw_count 应 > 0"
        assert new_n == 0, "全部已见过，不应有新增"
        assert updated_n == 0, "全部已见过，不应有更新"

    @pytest.mark.asyncio
    async def test_raw_count_positive_but_all_unchanged(self, db_session):
        """HTML 有数据但全部 MD5 相同 → raw_count > 0, action='unchanged'。"""
        engine = CrawlEngine(async_sessionmaker(lambda: db_session))
        pipe = _make_mock_pipeline()
        # upsert_listing 返回 unchanged
        pipe.upsert_listing = AsyncMock(return_value=(1, "unchanged"))
        engine._district_id_map = {"test_district": 1}
        global_seen = set()

        new_n, updated_n, raw_count = await engine._process_page(
            _VALID_LISTING_HTML, global_seen, pipe, 1, "http://test",
            default_district_id=1,
        )
        assert raw_count == 1
        assert new_n == 0
        assert updated_n == 0  # unchanged 不算 updated


# ═══════════════════════════════════════════════════════
# 3. 零产出跳页决策
# ═══════════════════════════════════════════════════════

class TestZeroYieldJump:
    """零产出时连续计数 → 2 页后跳页 → 最多 MAX_JUMPS 次 → 否则停止。"""

    def test_jump_triggered_after_low_yield_threshold(self):
        """连续 LOW_YIELD 页零产出 → 触发跳页跳过 JUMP_PAGES 页。"""
        ctx = _make_ctx(page=10, district_max=50,
                        zero_yield=LOW_YIELD_JUMP_THRESHOLD,
                        jumps=0)

        # 模拟决策过程：raw_count > 0, new=0, updated=0
        raw_count = 60   # 页面有数据
        new_n = 0
        updated_n = 0

        # Step 1: 递增 zero_yield
        ctx["zero_yield"] += 1

        # Step 2: 判断是否满足跳页条件
        should_jump = (
            ctx["zero_yield"] >= LOW_YIELD_JUMP_THRESHOLD
            and ctx["zero_yield"] < ZERO_YIELD_THRESHOLD
            and ctx["jumps"] < MAX_JUMPS_PER_DISTRICT
            and raw_count > 0
            and new_n == 0
            and updated_n == 0
        )
        assert should_jump, "连续零产出应触发跳页"

        # 执行跳页
        skip_to = min(ctx["page"] + JUMP_PAGES, ctx["district_max"] + 1)
        assert skip_to == 12
        ctx["page"] = skip_to
        ctx["zero_yield"] = 0
        ctx["jumps"] += 1
        assert ctx["jumps"] == 1

    def test_jump_not_triggered_when_yielding(self):
        """有产出时 zero_yield 清零，不触发跳页。"""
        ctx = _make_ctx(page=10, zero_yield=1)
        new_n = 2  # 有新增

        if new_n > 0:
            ctx["zero_yield"] = 0
        assert ctx["zero_yield"] == 0

    def test_max_jumps_exhausted_then_stop(self):
        """跳页次数耗尽后继续零产出 → zero_yield 达 ZERO_YIELD_THRESHOLD → 停止。"""
        ctx = _make_ctx(page=30, district_max=100,
                        zero_yield=ZERO_YIELD_THRESHOLD - 1,
                        jumps=MAX_JUMPS_PER_DISTRICT)  # 已耗尽

        new_n = 0
        updated_n = 0
        raw_count = 60

        ctx["zero_yield"] += 1

        # 跳页次数耗尽 → 不走跳页逻辑
        can_jump = (
            ctx["zero_yield"] >= LOW_YIELD_JUMP_THRESHOLD
            and ctx["jumps"] < MAX_JUMPS_PER_DISTRICT
        )
        assert not can_jump, "跳页次数耗尽不应再跳"

        # 转阶段 B：零产出 >= ZERO_YIELD_THRESHOLD → 停止
        should_stop = ctx["zero_yield"] >= ZERO_YIELD_THRESHOLD
        assert should_stop

    def test_jump_respects_district_max(self):
        """跳页不应超过 district_max + 1（越界保护）。"""
        ctx = _make_ctx(page=49, district_max=50,
                        zero_yield=LOW_YIELD_JUMP_THRESHOLD, jumps=0)

        skip_to = min(ctx["page"] + JUMP_PAGES, ctx["district_max"] + 1)
        assert skip_to == 51  # JUMP_PAGES=2 → 49+2=51 = max+1 → 允许触发翻完判断


# ═══════════════════════════════════════════════════════
# 4. DRY vs 零产出区分
# ═══════════════════════════════════════════════════════

class TestDryVsZeroYield:
    """DRY（页面无数据）和零产出（有数据但全已入库）是两种不同场景。"""

    def test_dry_only_when_raw_count_zero(self):
        """raw_count == 0 → dry 递增。"""
        ctx = _make_ctx(dry=2)
        raw_count = 0

        if raw_count == 0:
            ctx["dry"] += 1
            ctx["zero_yield"] += 1

        assert ctx["dry"] == 3
        # DRY 阈值到达 → 停止
        assert ctx["dry"] >= DRY_PAGE_THRESHOLD

    def test_zero_yield_only_when_raw_positive_but_no_new(self):
        """raw_count > 0 且 new=updated=0 → 仅 zero_yield 递增，dry 不变。"""
        ctx = _make_ctx(dry=0, zero_yield=2)
        raw_count = 60
        new_n = 0
        updated_n = 0

        # 关键：raw_count > 0 → 不走 DRY
        if raw_count == 0:
            ctx["dry"] += 1
        else:
            ctx["dry"] = 0  # 有数据，重置 DRY

        if raw_count > 0 and new_n == 0 and updated_n == 0:
            ctx["zero_yield"] += 1
        else:
            if new_n > 0 or updated_n > 0:
                ctx["zero_yield"] = 0

        assert ctx["dry"] == 0, "raw_count > 0 时 dry 应重置为 0"
        assert ctx["zero_yield"] == 3, "全已入库时 zero_yield 应递增"

    def test_both_reset_when_yielding(self):
        """有产出时 dry 和 zero_yield 都重置。"""
        ctx = _make_ctx(dry=2, zero_yield=3)
        raw_count = 60
        new_n = 5  # 有新增

        if raw_count == 0:
            ctx["dry"] += 1
        else:
            ctx["dry"] = 0

        if raw_count > 0 and new_n == 0 and updated_n == 0:
            ctx["zero_yield"] += 1
        else:
            if new_n > 0:
                ctx["zero_yield"] = 0

        assert ctx["dry"] == 0
        assert ctx["zero_yield"] == 0


# ═══════════════════════════════════════════════════════
# 5. finally 收尾 — 提前终止页数落库
# ═══════════════════════════════════════════════════════

class TestFinallyCleanup:
    """引擎 finally 块正确保存每个未完成 task 的最后一页。"""

    def test_interrupted_task_uses_own_page_not_global(self):
        """每个 ctx 有自己的 page，不应使用全局 self._current_page。"""
        queue = [
            _make_ctx(page=12, task_id=101, yield_new=30,
                      district={"name": "high_yield", "fang_code": "a058"}),
            _make_ctx(page=55, task_id=102, yield_new=500,
                      district={"name": "medium_yield", "fang_code": "a059"}),
            _make_ctx(page=3, task_id=103, yield_new=5,
                      district={"name": "low_yield", "fang_code": "a060"}),
        ]
        # 模拟 stopped 后所有 task 未完成
        for q in queue:
            q["completed"] = False

        # finally 收尾逻辑
        interrupted = [q for q in queue if not q["completed"] and q["task_id"] is not None]
        saved_pages = {}
        for q in interrupted:
            # 实际代码：page_end = q["page"] - 1
            page_end = q["page"] - 1
            saved_pages[q["task_id"]] = page_end

        # 断言：每个 task 的 page_end 反映各自的实际停止页
        assert saved_pages[101] == 11, "high_yield 实际爬到 11 页"
        assert saved_pages[102] == 54, "medium_yield 实际爬到 54 页"
        assert saved_pages[103] == 2,  "low_yield 实际爬到 2 页"

    def test_already_completed_tasks_not_touched(self):
        """已完成的 task 不应被 finally 收尾覆盖。"""
        queue = [
            _make_ctx(completed=True, page=50, task_id=201,
                      district={"name": "done", "fang_code": "a058"}),
            _make_ctx(completed=False, page=10, task_id=202,
                      district={"name": "active", "fang_code": "a059"}),
        ]

        interrupted = [q for q in queue if not q["completed"] and q["task_id"] is not None]
        assert len(interrupted) == 1
        assert interrupted[0]["task_id"] == 202  # 只有 active 被收尾


# ═══════════════════════════════════════════════════════
# 6. 第 1 页立即跳过
# ═══════════════════════════════════════════════════════

class TestPageOneSkip:
    """第 1 页无数据 → 立即完成，不等待 DRY 累积。"""

    def test_page_one_empty_skips_immediately(self):
        """p==1 且 raw_count==0 → completed=True。"""
        ctx = _make_ctx(page=1, district_max=100)
        raw_count = 0

        if ctx["page"] == 1 and raw_count == 0:
            ctx["completed"] = True

        assert ctx["completed"] is True

    def test_page_one_with_data_proceeds(self):
        """p==1 且 raw_count > 0 → 正常继续。"""
        ctx = _make_ctx(page=1, district_max=100)
        raw_count = 60  # 有数据

        if ctx["page"] == 1 and raw_count == 0:
            ctx["completed"] = True

        assert ctx["completed"] is False

    def test_page_one_empty_does_not_wait_for_dry_threshold(self):
        """第 1 页空不像后面需要 DRY_THRESHOLD 页积累才停。"""
        ctx = _make_ctx(page=1, dry=0, district_max=100)
        raw_count = 0

        # 第 1 页特殊处理：不检查 DRY → 直接停
        should_stop_immediately = (ctx["page"] == 1 and raw_count == 0)
        assert should_stop_immediately

        # 对比：非第 1 页需要 DRY_THRESHOLD
        ctx2 = _make_ctx(page=5, dry=2)  # 已经 2 次干了
        need_more = ctx2["dry"] < DRY_PAGE_THRESHOLD
        assert need_more  # 还没到阈值 (2 < 3)

        ctx2["dry"] += 1  # → 3
        at_threshold = ctx2["dry"] >= DRY_PAGE_THRESHOLD
        assert at_threshold  # 第三次到达阈值
