"""dedup.py 单元测试"""

from crawler.dedup import compute_md5, is_listing_changed


class TestComputeMd5:
    def test_deterministic(self):
        """相同输入多次调用返回相同 MD5"""
        data = {
            "total_price": 132.5,
            "unit_price": 14865.0,
            "area": 89.5,
            "room_count": 3,
            "hall_count": 2,
            "bathroom_count": 1,
            "floor_level": "中楼层",
            "total_floors": 32,
            "orientation": "南",
            "decoration": "精装",
            "building_type": "板楼",
            "building_structure": "钢混",
            "has_elevator": True,
            "community_name": "龙湖U城",
        }
        h1 = compute_md5(data)
        h2 = compute_md5(data)
        assert h1 == h2
        assert len(h1) == 32

    def test_different_data_different_hash(self):
        """不同数据产生不同 MD5"""
        d1 = {
            "total_price": 100,
            "unit_price": 10000,
            "area": 100,
            "room_count": 2,
            "hall_count": 1,
            "bathroom_count": 1,
            "floor_level": "低楼层",
            "total_floors": 6,
            "orientation": "南",
            "decoration": "毛坯",
            "building_type": "塔楼",
            "building_structure": "砖混",
            "has_elevator": False,
            "community_name": "测试小区A",
        }
        d2 = {**d1, "total_price": 200}
        assert compute_md5(d1) != compute_md5(d2)

    def test_none_fields_handled(self):
        """None 字段用空字符串替代，不影响计算"""
        data = {
            "total_price": None,
            "unit_price": None,
            "area": 80,
            "room_count": None,
            "hall_count": None,
            "bathroom_count": None,
            "floor_level": None,
            "total_floors": None,
            "orientation": None,
            "decoration": None,
            "building_type": None,
            "building_structure": None,
            "has_elevator": None,
            "community_name": None,
        }
        result = compute_md5(data)
        assert len(result) == 32


class TestIsListingChanged:
    class FakeListing:
        def __init__(self, md5):
            self.md5_hash = md5

    def test_changed(self):
        existing = self.FakeListing("abc123")
        assert is_listing_changed(existing, "def456")

    def test_unchanged(self):
        existing = self.FakeListing("abc123")
        assert not is_listing_changed(existing, "abc123")

    def test_none_vs_value(self):
        existing = self.FakeListing(None)
        assert is_listing_changed(existing, "abc123")
