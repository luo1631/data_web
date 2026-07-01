"""
爬虫全局常量 — cq.esf.fang.com 桌面站。

URL:
  首页:           https://cq.esf.fang.com/
  区县列表第1页:   https://cq.esf.fang.com/house-a{code}/
  区县列表第N页:   https://cq.esf.fang.com/house-a{code}/i3{N}/
  详情页:         https://cq.esf.fang.com/chushou/{house_id}.htm

注: 区县筛选页 (/house-a{code}/) 无滑块验证（与 /house/ 不同），
    每个区县可翻 100 页 × 60 条 = 6000 条，37 区县合计上限约 22 万条。
"""

# ============================================================
# 区县配置（38 个）— fang_code 为房天下区县路径代码
# ============================================================
DISTRICTS: list[dict] = [
    # --- 主城 9 区 ---
    {"name": "渝北区",     "pinyin": "yubei",      "is_urban": True,  "fang_code": "a058"},
    {"name": "江北区",     "pinyin": "jiangbei",    "is_urban": True,  "fang_code": "a056"},
    {"name": "渝中区",     "pinyin": "yuzhong",     "is_urban": True,  "fang_code": None},    # 渝中区几乎无二手房，fang.com 筛选栏不展示
    {"name": "南岸区",     "pinyin": "nanan",       "is_urban": True,  "fang_code": "a059"},
    {"name": "九龙坡区",   "pinyin": "jiulongpo",   "is_urban": True,  "fang_code": "a061"},
    {"name": "沙坪坝区",   "pinyin": "shapingba",   "is_urban": True,  "fang_code": "a060"},
    {"name": "巴南区",     "pinyin": "banan",       "is_urban": True,  "fang_code": "a063"},
    {"name": "大渡口区",   "pinyin": "dadukou",     "is_urban": True,  "fang_code": "a062"},
    {"name": "北碚区",     "pinyin": "beibei",      "is_urban": True,  "fang_code": "a064"},
    # --- 近郊 12 区 ---
    {"name": "璧山区",     "pinyin": "bishan",      "is_urban": True,  "fang_code": "a016748"},
    {"name": "江津区",     "pinyin": "jiangjin",    "is_urban": True,  "fang_code": None},    # fang.com 不展示此区
    {"name": "永川区",     "pinyin": "yongchuan",   "is_urban": True,  "fang_code": "a011839"},
    {"name": "合川区",     "pinyin": "hechuan",     "is_urban": True,  "fang_code": "a011828"},
    {"name": "长寿区",     "pinyin": "changshou",   "is_urban": True,  "fang_code": None},    # fang.com 不展示此区
    {"name": "涪陵区",     "pinyin": "fuling",      "is_urban": True,  "fang_code": "a011827"},
    {"name": "南川区",     "pinyin": "nanchuan",    "is_urban": True,  "fang_code": "a011829"},
    {"name": "綦江区",     "pinyin": "qijiang",     "is_urban": True,  "fang_code": "a011831"},
    {"name": "大足区",     "pinyin": "dazu",        "is_urban": True,  "fang_code": "a017400"},
    {"name": "铜梁区",     "pinyin": "tongliang",   "is_urban": True,  "fang_code": "a011833"},
    {"name": "潼南区",     "pinyin": "tongnan",     "is_urban": True,  "fang_code": "a017401"},
    {"name": "荣昌区",     "pinyin": "rongchang",   "is_urban": True,  "fang_code": "a011832"},
    # --- 远郊 17 区县 ---
    {"name": "万州区",     "pinyin": "wanzhou",     "is_urban": False, "fang_code": "a011834"},
    {"name": "开州区",     "pinyin": "kaizhou",     "is_urban": False, "fang_code": None},    # fang.com 不展示此区
    {"name": "梁平区",     "pinyin": "liangping",   "is_urban": False, "fang_code": "a016709"},
    {"name": "武隆区",     "pinyin": "wulong",      "is_urban": False, "fang_code": "a011837"},
    {"name": "城口县",     "pinyin": "chengkou",    "is_urban": False, "fang_code": "a016718"},
    {"name": "丰都县",     "pinyin": "fengdu",      "is_urban": False, "fang_code": "a016707"},
    {"name": "垫江县",     "pinyin": "dianjiang",   "is_urban": False, "fang_code": "a011825"},
    {"name": "忠县",       "pinyin": "zhongxian",   "is_urban": False, "fang_code": "a016708"},
    {"name": "云阳县",     "pinyin": "yunyang",     "is_urban": False, "fang_code": "a011840"},
    {"name": "奉节县",     "pinyin": "fengjie",     "is_urban": False, "fang_code": "a011826"},
    {"name": "巫山县",     "pinyin": "wushan",      "is_urban": False, "fang_code": "a011835"},
    {"name": "巫溪县",     "pinyin": "wuxi",        "is_urban": False, "fang_code": "a016714"},
    {"name": "黔江区",     "pinyin": "qianjiang",   "is_urban": False, "fang_code": "a016710"},
    {"name": "石柱土家族自治县",     "pinyin": "shizhu",    "is_urban": False, "fang_code": "a016711"},
    {"name": "秀山土家族苗族自治县", "pinyin": "xiushan",   "is_urban": False, "fang_code": "a011838"},
    {"name": "酉阳土家族苗族自治县", "pinyin": "youyang",   "is_urban": False, "fang_code": "a016713"},
    {"name": "彭水苗族土家族自治县", "pinyin": "pengshui",  "is_urban": False, "fang_code": "a011830"},
]

# 仅含有效 fang_code 的区县（爬虫可爬的）
ACTIVE_DISTRICTS = [d for d in DISTRICTS if d["fang_code"] is not None]

DISTRICT_BY_NAME: dict[str, dict] = {d["name"]: d for d in DISTRICTS}
DISTRICT_BY_SLUG: dict[str, dict] = {d["pinyin"]: d for d in DISTRICTS}

# ============================================================
# URL 模板
# ============================================================
SEED_URL = "https://cq.esf.fang.com/"
DISTRICT_LIST_URL = "https://cq.esf.fang.com/house-{code}/"          # 第 1 页
DISTRICT_LIST_PAGE_URL = "https://cq.esf.fang.com/house-{code}/i3{page}/"  # 第 N 页
LIST_PAGE_TEMPLATE = DISTRICT_LIST_PAGE_URL  # 向后兼容别名
DETAIL_URL_TEMPLATE = "https://cq.esf.fang.com/chushou/{house_id}.htm"

# ============================================================
# 速率限制（秒）
# ============================================================
LIST_PAGE_DELAY = (2.0, 4.0)
DETAIL_PAGE_DELAY = (1.5, 3.0)
JITTER_RANGE = (0.7, 1.3)

# ============================================================
# 翻页控制
# ============================================================
MAX_PAGES = 100
MAX_PAGES_PER_DISTRICT = 100     # 每个区县最多翻页数
LISTINGS_PER_PAGE = 60
DRY_PAGE_THRESHOLD = 3            # 连续 N 页无变化即停止该区县
FETCH_FAILURE_THRESHOLD = 3       # 连续 N 页网络错误即停止该区县

# 历史兼容
OVERLAP_THRESHOLD = 0.9
LIST_CONCURRENCY = 1
DETAIL_CONCURRENCY = 3

# ============================================================
# User-Agent 池
# ============================================================
USER_AGENTS: list[str] = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 Edg/130.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:131.0) Gecko/20100101 Firefox/131.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Safari/605.1.15",
]

# ============================================================
# 数据清洗
# ============================================================
PRICE_OUTLIER = {
    "total_price_min": 1.0,    "total_price_max": 10000.0,
    "unit_price_min": 100.0,   "unit_price_max": 100000.0,
    "area_min": 10.0,          "area_max": 1000.0,
    "cross_check_tolerance": 0.5,
}

DECORATION_MAP: dict[str, str] = {
    "毛坯": "毛坯", "毛坯房": "毛坯",
    "简装": "简装", "简单装修": "简装",
    "精装": "精装", "精装修": "精装",
    "豪装": "豪装", "豪华装修": "豪装",
    "中装": "中装", "中等装修": "中装",
}

ORIENTATION_MAP: dict[str, str] = {
    "南": "南", "朝南": "南", "北": "北", "朝北": "北",
    "南北": "南北", "南北通透": "南北", "朝南北": "南北",
    "东南": "东南", "西南": "西南", "东北": "东北", "西北": "西北",
    "东": "东", "西": "西", "东西": "东西",
}

FLOOR_LEVEL_MAP: dict[str, str] = {
    "低": "低楼层", "低楼层": "低楼层", "低层": "低楼层", "底层": "低楼层",
    "中": "中楼层", "中楼层": "中楼层", "中层": "中楼层",
    "高": "高楼层", "高楼层": "高楼层", "高层": "高楼层", "顶层": "高楼层",
}

# 社区名括号内简称 → 区县全名（用于文本推断归属）
_AREA_SHORT_TO_FULL: dict[str, str] = {
    "两江新区": "渝北区",
    "高新区": "九龙坡区",
    "北部新区": "渝北区",
    "经开区": "南岸区",
}
