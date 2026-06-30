"""cleaner.py 单元测试"""

from datetime import date

from crawler.cleaner import (
    parse_price,
    parse_unit_price,
    parse_area,
    parse_date,
    normalize_decoration,
    normalize_orientation,
    normalize_floor_level,
    is_price_outlier,
)


class TestParsePrice:
    def test_wan_format(self):
        assert parse_price("132.5万") == 132.5

    def test_plain_number(self):
        assert parse_price("132.5") == 132.5

    def test_with_comma(self):
        assert parse_price("1,320.5万") == 1320.5

    def test_none(self):
        assert parse_price(None) is None
        assert parse_price("") is None

    def test_large_yuan_converts_to_wan(self):
        """>10000 且无"万"字，按元→万元转换"""
        result = parse_price("5000000")
        assert result == 500.0  # 5,000,000元 = 500万元

    def test_small_yuan_stays(self):
        """<=10000 保持原值"""
        result = parse_price("5000")
        assert result == 5000.0


class TestParseUnitPrice:
    def test_normal(self):
        assert parse_unit_price("14865元/㎡") == 14865.0

    def test_plain_number(self):
        assert parse_unit_price("14865") == 14865.0

    def test_wan_format(self):
        assert parse_unit_price("1.5万/㎡") == 15000.0

    def test_none(self):
        assert parse_unit_price(None) is None


class TestParseArea:
    def test_with_sqm(self):
        assert parse_area("89.5㎡") == 89.5

    def test_plain(self):
        assert parse_area("89.5") == 89.5

    def test_with_chinese(self):
        assert parse_area("89.5平米") == 89.5

    def test_none(self):
        assert parse_area(None) is None


class TestParseDate:
    def test_iso_format(self):
        assert parse_date("2024-01-15") == date(2024, 1, 15)

    def test_slash_format(self):
        assert parse_date("2024/01/15") == date(2024, 1, 15)

    def test_chinese_format(self):
        assert parse_date("2024年1月15日") == date(2024, 1, 15)

    def test_none(self):
        assert parse_date(None) is None
        assert parse_date("") is None


class TestNormalizeDecoration:
    def test_exact_match(self):
        assert normalize_decoration("精装") == "精装"

    def test_fuzzy_match(self):
        assert normalize_decoration("精装修") == "精装"
        assert normalize_decoration("豪华装修") == "豪装"

    def test_no_match(self):
        assert normalize_decoration("未知装修") == "未知装修"

    def test_none(self):
        assert normalize_decoration(None) is None


class TestNormalizeOrientation:
    def test_exact(self):
        assert normalize_orientation("南") == "南"

    def test_prefix(self):
        assert normalize_orientation("朝南") == "南"

    def test_compound(self):
        assert normalize_orientation("南北通透") == "南北"

    def test_none(self):
        assert normalize_orientation(None) is None


class TestNormalizeFloorLevel:
    def test_low(self):
        assert normalize_floor_level("低层") == "低楼层"
        assert normalize_floor_level("底层") == "低楼层"

    def test_mid(self):
        assert normalize_floor_level("中层") == "中楼层"

    def test_high(self):
        assert normalize_floor_level("高层") == "高楼层"
        assert normalize_floor_level("顶层") == "高楼层"

    def test_none(self):
        assert normalize_floor_level(None) is None


class TestIsPriceOutlier:
    def test_normal(self):
        assert not is_price_outlier(132.5, 14865, 89.5)

    def test_negative_total(self):
        assert is_price_outlier(-1, 14865, 89.5)

    def test_too_high_total(self):
        assert is_price_outlier(99999, 14865, 89.5)

    def test_cross_check_mismatch(self):
        """总价 ≈ 单价×面积/10000，偏差>50% 判定异常"""
        # unit_price=14865 area=89.5 → expected total ≈ 133万
        # actual total=500万 → 偏差 > 50%
        assert is_price_outlier(500, 14865, 89.5)

    def test_all_none(self):
        assert not is_price_outlier(None, None, None)
