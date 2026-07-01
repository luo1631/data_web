"""数据污染测试: 异常值检测、空 HTML 处理、价格校验"""

import pytest

from crawler.cleaner import (
    parse_price, parse_unit_price, parse_area,
    normalize_decoration, normalize_orientation,
    is_price_outlier, clean_listing,
)
from crawler.parsers import DetailParser
from crawler.dedup import compute_md5


class TestPriceOutlierDetection:
    def test_normal_price_passes(self):
        assert not is_price_outlier(132.5, 14865, 89.5)

    def test_zero_price_fails(self):
        assert is_price_outlier(0, 14865, 89.5)

    def test_negative_price_fails(self):
        assert is_price_outlier(-1, 14865, 89.5)

    def test_absurdly_high_price_fails(self):
        assert is_price_outlier(99999, 14865, 89.5)

    def test_absurdly_high_unit_price_fails(self):
        assert is_price_outlier(132.5, 999999, 89.5)

    def test_cross_validation_mismatch(self):
        """总价=500万, 单价=14865, 面积=89.5 → 预期总价=133万, 偏差>50%"""
        assert is_price_outlier(500, 14865, 89.5)

    def test_null_handling(self):
        """任意字段为 None 时仅做基本检查"""
        assert not is_price_outlier(None, 14865, 89.5)
        assert not is_price_outlier(132.5, None, 89.5)
        assert not is_price_outlier(132.5, 14865, None)


class TestEdgeCases:
    def test_empty_string_price(self):
        assert parse_price("") is None

    def test_malformed_price(self):
        assert parse_price("abc") is None

    def test_chinese_price_variations(self):
        """中文价格变体"""
        assert parse_price("一百三十二点五万") is None  # 无法解析中文数字

    def test_unit_price_wan(self):
        assert parse_unit_price("1.5万/㎡") == 15000.0

    def test_comma_in_number(self):
        assert parse_price("1,320.5万") == 1320.5


class TestHTMLParsingEdgeCases:
    def test_empty_html(self):
        """空 HTML 返回空列表"""
        from crawler.parsers import ListParser
        listings = ListParser.parse_listing_data("")
        assert listings == []

    def test_empty_count(self):
        """空 HTML 返回 0"""
        from crawler.parsers import ListParser
        assert ListParser.parse_total_count("<html></html>") == 0

    def test_detail_parser_no_crash(self):
        """详情页解析器不应因畸形 HTML 崩溃"""
        parser = DetailParser("test_id", "http://example.com")
        result = parser.parse("<html><body>Not a listing page</body></html>")
        assert result.external_id == "test_id"


class TestMD5Stability:
    def test_worst_case_different_types(self):
        """不同类型值不应影响 MD5 稳定性"""
        d1 = {"total_price": 100, "unit_price": 10000, "area": None}
        h1 = compute_md5(d1)
        h2 = compute_md5(d1)
        assert h1 == h2

    def test_boolean_in_hash(self):
        """布尔值正确序列化"""
        d1 = {"has_elevator": True}
        d2 = {"has_elevator": False}
        assert compute_md5(d1) != compute_md5(d2)
