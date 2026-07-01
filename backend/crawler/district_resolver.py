"""
区县解析器 — 基于重庆行政区划数据的精确文本匹配。

从 data.json (国家统计局城乡划分数据) 构建:
  1. 街道/镇 → 区县 映射
  2. 社区/村 名称也包含在内（如果数据更细）
  3. 补充房天下常用区域简称
"""

import json
import re
from pathlib import Path
from collections import defaultdict

_DATA_PATH = Path(__file__).resolve().parent.parent.parent / "data.json"

# 额外补充 — 房天下房源中常见的区域简称和别名
_EXTRA_ALIASES: dict[str, str] = {
    # 两江新区覆盖区域 → 渝北区
    "两江新区": "渝北区", "北部新区": "渝北区",
    # 高新区覆盖 → 九龙坡区 (实际跨沙坪坝，但房源多标九龙坡)
    "高新区": "九龙坡区",
    # 经开区 → 南岸区
    "经开区": "南岸区",
    # 常见商圈/区域别名
    "汽博": "渝北区", "汽博中心": "渝北区",
    "照母山": "渝北区",
    "中央公园": "渝北区",
    "悦来": "渝北区",
    "礼嘉": "渝北区",
    "鸳鸯": "渝北区",
    "回兴": "渝北区",
    "空港": "渝北区",
    "龙头寺": "渝北区",
    "新牌坊": "渝北区",
    "冉家坝": "渝北区",
    "大竹林": "渝北区",
    "人和": "渝北区",
    "龙兴": "渝北区",
    "鱼嘴": "江北区",
    "观音桥": "江北区",
    "大石坝": "江北区",
    "五里店": "江北区",
    "江北城": "江北区",
    "寸滩": "江北区",
    "铁山坪": "江北区",
    "解放碑": "渝中区",
    "朝天门": "渝中区",
    "大坪": "渝中区",
    "化龙桥": "渝中区",
    "两路口": "渝中区",
    "上清寺": "渝中区",
    "七星岗": "渝中区",
    "南坪": "南岸区",
    "弹子石": "南岸区",
    "茶园": "南岸区",
    "长生桥": "南岸区",
    "海棠溪": "南岸区",
    "铜元局": "南岸区",
    "杨家坪": "九龙坡区",
    "谢家湾": "九龙坡区",
    "石桥铺": "九龙坡区",
    "二郎": "九龙坡区",
    "华岩": "九龙坡区",
    "巴国城": "九龙坡区",
    "陈家坪": "九龙坡区",
    "盘龙": "九龙坡区",
    "三峡广场": "沙坪坝区",
    "大学城": "沙坪坝区",
    "磁器口": "沙坪坝区",
    "西永": "沙坪坝区",
    "虎溪": "沙坪坝区",
    "双碑": "沙坪坝区",
    "井口": "沙坪坝区",
    "小龙坎": "沙坪坝区",
    "天星桥": "沙坪坝区",
    "凤天路": "沙坪坝区",
    "鱼洞": "巴南区",
    "李家沱": "巴南区",
    "龙洲湾": "巴南区",
    "花溪": "巴南区",
    "界石": "巴南区",
    "九宫庙": "大渡口区",
    "双山": "大渡口区",
    "蔡家": "北碚区",
    "城南": "北碚区",
    "歇马": "北碚区",
    "水土": "北碚区",
}


class DistrictResolver:
    """基于行政区划数据的区县推断器。

    加载 data.json，构建 name→district 的快速查找表。
    """

    def __init__(self):
        self._name_to_district: dict[str, str] = {}
        self._loaded = False

    def load(self, district_name_to_id: dict[str, int] | None = None) -> "DistrictResolver":
        """加载 data.json 并构建映射。

        Args:
            district_name_to_id: {区县全名: DB id} 用于验证
        """
        self._name_to_district = {}
        self._loaded = True

        if _DATA_PATH.exists():
            data = json.loads(_DATA_PATH.read_text(encoding="utf-8"))
            districts = data.get("data", {}).get("children", [])

            for district in districts:
                dname = district["name"]
                # 标准化 — 去掉"市辖区"等后缀
                dname_clean = dname.replace("市辖区", "").replace("县", "").strip()
                if not dname_clean:
                    continue
                # 记录区县全名
                self._add(dname, dname)

                # 遍历街道/镇
                for child in district.get("children", []):
                    cname = child["name"]
                    ctype = child.get("type", "")
                    # 去掉 "街道" / "镇" / "乡" 等后缀后的名称
                    for suffix in ["街道", "镇", "乡", "民族乡", "苏木"]:
                        cname_short = cname.removesuffix(suffix)
                        if cname_short != cname:
                            break
                    self._add(cname_short, dname)
                    self._add(cname, dname)

        # 额外别名（覆盖或补充）
        for alias, dname in _EXTRA_ALIASES.items():
            self._add(alias, dname)

        # 如果有 DB 映射，只保留在 DB 中存在的区县
        if district_name_to_id:
            valid = set(district_name_to_id.keys())
            self._name_to_district = {
                k: v for k, v in self._name_to_district.items()
                if v in valid
            }

        return self

    def _add(self, name: str, district: str):
        if name and len(name) >= 2:
            # 优先保留更长的匹配（避免"江北"匹配到"江北区"后又匹配到"江北街道"）
            existing = self._name_to_district.get(name)
            if existing and existing != district:
                # 如果已存在不同区县映射，选择更短的名字（更可能是区县而非街道）
                # 例如 "江北街道"在涪陵区，但"江北"应该匹配江北区
                pass  # 保留首次匹配
            else:
                self._name_to_district[name] = district

    def resolve(self, text: str, default: str = "渝北区") -> str:
        """从文本中推断区县名。

        匹配策略:
          1. 优先匹配完整区县名（如 "渝北区"）
          2. 再匹配街道/镇名
          3. 匹配商圈/别名
          4. 都没命中→默认

        Args:
            text: 房源标题+小区名+地址的拼接文本
            default: 未匹配时的默认区县

        Returns:
            区县全名 (如 "渝北区")
        """
        if not text:
            return default

        # 1. 先检查是否直接包含区县全名（最高优先级）
        for dname_full in [
            "渝北区", "江北区", "渝中区", "南岸区", "九龙坡区",
            "沙坪坝区", "巴南区", "大渡口区", "北碚区",
            "璧山区", "江津区", "永川区", "合川区", "长寿区",
            "涪陵区", "南川区", "綦江区", "大足区", "铜梁区",
            "潼南区", "荣昌区", "万州区", "开州区", "梁平区",
            "武隆区", "黔江区",
            "城口县", "丰都县", "垫江县", "忠县", "云阳县",
            "奉节县", "巫山县", "巫溪县",
            "石柱土家族自治县", "秀山土家族苗族自治县",
            "酉阳土家族苗族自治县", "彭水苗族土家族自治县",
        ]:
            if dname_full in text:
                return dname_full

        # 2. 按长度降序匹配（优先匹配长的，更精确）
        candidates = sorted(
            self._name_to_district.keys(),
            key=lambda x: len(x), reverse=True,
        )
        for name in candidates:
            if name in text:
                return self._name_to_district[name]

        return default
