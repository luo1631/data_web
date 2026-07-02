"""区县映射验证: fang_code → 实际页面标题 + 解析器快照测试"""

import json
import re
import pytest
from bs4 import BeautifulSoup


# ============================================================
# 区县映射验证 — fang_code 是否返回预期区县
# ============================================================

# 从 constants 映射 fang_code → 预期 DB 区县名
def _get_code_to_db_name():
    from crawler.constants import ACTIVE_DISTRICTS
    return {d["fang_code"]: d["db_name"] for d in ACTIVE_DISTRICTS}


class TestDistrictMapping:
    """验证 fang_code 与实际页面标题中的区县名一致。

    注意: 此测试需要网络访问 fang.com，仅在明确启用时运行。
    运行方式: pytest tests/test_district_mapping.py -m "network" --run-network
    """

    @pytest.mark.network
    @pytest.mark.parametrize("fang_code,expected_db_name", [
        ("a058", "两江新区"),
        ("a056", "渝中区"),
        ("a059", "南岸区"),
        ("a060", "沙坪坝区"),
        ("a061", "九龙坡区"),
        ("a064", "巴南区"),
        ("a062", "大渡口区"),
        ("a063", "北碚区"),
    ])
    def test_fang_code_title_matches(self, fang_code, expected_db_name):
        """fang_code 页面 title 应包含对应区县关键词。"""
        import httpx, asyncio

        async def _check():
            url = f"https://cq.esf.fang.com/house-{fang_code}/"
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as c:
                resp = await c.get(url, headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/130.0.0.0",
                })
                assert resp.status_code == 200, f"{fang_code} → HTTP {resp.status_code}"
                html = resp.text

            # 从 <title> 提取区县名
            title_match = re.search(r'<title>【(.+?)二手房', html)
            assert title_match, f"{fang_code}: 未找到页面标题区县名"
            actual_title_district = title_match.group(1)
            print(f"  {fang_code} → title='{actual_title_district}', expected db='{expected_db_name}'")

            # 验证: 标题中的区县名与预期 db_name 至少有一个关键词匹配
            # (两江新区 → 渝北区 是特殊映射，fang.com 标题显示"两江新区")
            from crawler.constants import ACTIVE_DISTRICTS
            fang_name = next((d["name"] for d in ACTIVE_DISTRICTS if d["fang_code"] == fang_code), None)
            assert fang_name, f"fang_code {fang_code} not in ACTIVE_DISTRICTS"
            assert fang_name in actual_title_district or actual_title_district in fang_name, \
                f"标题 '{actual_title_district}' 与预期区县 '{fang_name}' 不匹配"

        asyncio.run(_check())

    def test_all_codes_unique(self):
        """所有 fang_code 唯一无重复。"""
        from crawler.constants import ACTIVE_DISTRICTS
        codes = [d["fang_code"] for d in ACTIVE_DISTRICTS]
        assert len(codes) == len(set(codes)), f"重复的 fang_code: {len(codes)} vs {len(set(codes))}"

    def test_all_db_names_in_districts_table(self):
        """所有 db_name 均在 DB districts 表中有对应记录。"""
        from crawler.constants import ACTIVE_DISTRICTS
        from seed_data import DISTRICTS as SEED_DISTRICTS
        seed_names = set(d[0] for d in SEED_DISTRICTS)
        for d in ACTIVE_DISTRICTS:
            db_name = d["db_name"]
            assert db_name in seed_names, f"db_name '{db_name}' (fang_code={d['fang_code']}) 不在 seed_data 中"

    def test_两江新区_maps_correctly(self):
        """两江新区是 fang.com 主城区入口。"""
        from crawler.constants import ACTIVE_DISTRICTS
        ljx = next((d for d in ACTIVE_DISTRICTS if d["fang_code"] == "a058"), None)
        assert ljx is not None
        assert ljx["db_name"] == "两江新区"

    def test_江北区_no_direct_fang_code(self):
        """江北区无独立 fang_code（并入两江新区），靠 resolver 文本解析。"""
        from crawler.constants import ACTIVE_DISTRICTS
        jb = [d for d in ACTIVE_DISTRICTS if d["db_name"] == "江北区"]
        assert len(jb) == 0, "江北区不应有独立 fang_code"


# ============================================================
# 解析器快照测试 — 用真实 HTML 验证
# ============================================================

# 测试用 HTML 片段（取自 2026-07-02 a058 两江新区第1页）
SAMPLE_LISTING_HTML = """<dl class="clearfix " dataflag="bg" data-bg="{&quot;houseid&quot;:&quot;204649634&quot;,&quot;housetype&quot;:&quot;JUHE&quot;}" id="kesfqbfylb_A01_01_03">
  <dt class="floatl">
    <a href="/chushou/3_204649634.htm" target="_blank">
      <img alt="新上 汽博一线高尔夫独栋 花园900平 面宽30米 客厅挑高" src="/loading.gif" data-src="/real.jpg"/>
    </a>
  </dt>
  <dd>
    <h4 class="clearfix">
      <a href="/chushou/3_204649634.htm" title="新上 汽博一线高尔夫独栋 花园900平 面宽30米 客厅挑高">
        <span class="tit_shop">新上 汽博一线高尔夫独栋 花园900平 面宽30米 客厅挑高</span>
      </a>
    </h4>
    <p class="tel_shop">
      <a class="link_rk" href="//baike.fang.com/item/独栋/12190559">独栋</a>
      <i>|</i> 卧室：5个 <i>|</i> 455.79㎡ <i>|</i> 南向 <i>|</i>
    </p>
    <p class="add_shop">
      <a href="/house-xm3110623668/" title="保利国际高尔夫花园别墅">保利国际高尔夫花园别</a>
      <span>汽博中心 北部新区保利高尔夫别墅</span>
    </p>
    <p class="clearfix label"><span>不满二</span></p>
  </dd>
  <dd class="price_right">
    <span class="red"><b>1200</b>万</span>
    <span>26327元/㎡</span>
  </dd>
</dl>"""


class TestListParserSnapshot:
    """解析器快照测试 — 确保 HTML 结构变更时能及时发现。"""

    def test_parse_single_listing(self):
        """单条房源解析 — 关键字段验证。"""
        from crawler.parsers.list_parser import ListParser
        soup = BeautifulSoup(SAMPLE_LISTING_HTML, "lxml")
        dl = soup.select_one("dl")
        data = ListParser._parse_one_dl(dl)

        assert data is not None, "解析返回 None"
        assert data["house_id"] == "3_204649634", f"house_id={data.get('house_id')}"
        assert data.get("listing_type") == "regular", f"listing_type={data.get('listing_type')}"
        assert data["title"] == "新上 汽博一线高尔夫独栋 花园900平 面宽30米 客厅挑高"
        assert data["total_price"] == 1200.0, f"total_price={data.get('total_price')}"
        assert data["unit_price"] == 26327.0, f"unit_price={data.get('unit_price')}"
        assert data["area"] == 455.79, f"area={data.get('area')}"
        assert data["room_count"] == 5, f"room_count={data.get('room_count')}"
        assert data["orientation"] == "南", f"orientation={data.get('orientation')}"
        assert data["building_type"] == "独栋", f"building_type={data.get('building_type')}"
        assert "保利国际高尔夫花园别墅" in data.get("community_name", ""), \
            f"community_name={data.get('community_name')}"
        assert data.get("community_address") is not None, "community_address 应为非空"

    def test_parse_listing_data_batch(self):
        """批量解析 — 从真实第1页 HTML 片段验证条数。"""
        from crawler.parsers.list_parser import ListParser

        # 构建含多条房源的 HTML
        repeated = "".join([
            SAMPLE_LISTING_HTML.replace('204649634', str(204649634 + i))
            for i in range(10)
        ])
        full_html = f"<html><body>{repeated}</body></html>"

        parsed = ListParser.parse_listing_data(full_html)
        assert len(parsed) == 10, f"应解析出 10 条，实际 {len(parsed)}"
        for p in parsed:
            assert p.get("house_id"), "每条都应有 house_id"
            assert p.get("title"), "每条都应有 title"

    def test_clean_list_page_preserves_fields(self):
        """clean_list_page_data 应保留解析器提取的所有字段。"""
        from crawler.cleaner import clean_list_page_data

        raw = {
            "total_price": 120.0,
            "unit_price": 15000.0,
            "area": 80.0,
            "room_count": 3,
            "hall_count": 2,
            "bathroom_count": 1,
            "floor_level": "中楼层",
            "total_floors": 32,
            "orientation": "南",
            "decoration": "精装",
            "building_type": "塔楼",
            "community_name": "测试小区",
            "community_address": "重庆市渝北区某某路",
            "title": "精装三房 南北通透",
        }

        cleaned = clean_list_page_data(raw)

        assert cleaned["total_price"] == 120.0
        assert cleaned["unit_price"] == 15000.0
        assert cleaned["area"] == 80.0
        assert cleaned["listing_type"] == "regular"
        assert cleaned["room_count"] == 3
        assert cleaned["hall_count"] == 2
        assert cleaned["bathroom_count"] == 1
        assert cleaned["floor_level"] == "中楼层"
        assert cleaned["total_floors"] == 32, "total_floors 应保留（修复前为 always None）"
        assert cleaned["orientation"] == "南"
        assert cleaned["building_type"] == "塔楼", "building_type 应保留（修复前为 always None）"
        assert cleaned["community_name"] == "测试小区"
        assert cleaned["community_address"] == "重庆市渝北区某某路", \
            "community_address 应保留（修复前为 always None）"

    def test_unit_price_fallback_computation(self):
        """当列表页没有 unit_price 时应从 total_price÷area 推算。"""
        from crawler.cleaner import clean_list_page_data

        raw = {
            "total_price": 150.0,  # 万
            "area": 100.0,         # ㎡
            "room_count": 3,
            "title": "测试",
        }
        cleaned = clean_list_page_data(raw)
        assert cleaned["unit_price"] == 15000.0, \
            f"推算单价=150*10000/100=15000, 实际={cleaned['unit_price']}"


# ============================================================
# District resolver 验证
# ============================================================

class TestDistrictResolver:
    """验证 resolver 能正确从文本中推断区县。"""

    def test_full_name_match(self):
        """直接包含区县全名应精确匹配。"""
        from crawler.district_resolver import DistrictResolver
        resolver = DistrictResolver().load()

        assert resolver.resolve("两江新区 某小区 精装三房") == "两江新区"
        assert resolver.resolve("江北区 观音桥 两房") == "两江新区"
        assert resolver.resolve("九龙坡区 杨家坪") == "九龙坡区"

    def test_short_name_match(self):
        """fang.com 简称应匹配到 DB 完整区县名。"""
        from crawler.district_resolver import DistrictResolver
        resolver = DistrictResolver().load()

        assert resolver.resolve("沙坪坝 大学城") == "沙坪坝区"
        assert resolver.resolve("九龙坡 杨家坪") == "九龙坡区"

    def test_两江新区_default(self):
        """两江新区默认匹配自身。"""
        from crawler.district_resolver import DistrictResolver
        resolver = DistrictResolver().load()

        assert resolver.resolve("两江新区 照母山") == "两江新区"

    def test_商圈_alias(self):
        """商圈别名应正确推断区县。"""
        from crawler.district_resolver import DistrictResolver
        resolver = DistrictResolver().load()

        assert resolver.resolve("观音桥 精装两房") == "两江新区"
        assert resolver.resolve("解放碑 一室一厅") == "渝中区"
        assert resolver.resolve("大学城 三房") == "沙坪坝区"
