"""
爬虫全局常量 — m.fang.com 移动站配置。

URL 规律:
  列表页: https://m.fang.com/esf/{slug}/?page={n}     (slug=city 如 cq)
  区县筛选: https://m.fang.com/esf/{district_pinyin}/
  详情页: https://m.fang.com/esf/cq/{house_id}.html
"""

# ============================================================
# 区县配置（38 个）— slug 为移动站 URL 中使用的拼音标识
# ============================================================
DISTRICTS: list[dict] = [
    {"name": "渝北区",     "pinyin": "yubei",      "slug": "yubei",      "is_urban": True},
    {"name": "江北区",     "pinyin": "jiangbei",    "slug": "jiangbei",    "is_urban": True},
    {"name": "渝中区",     "pinyin": "yuzhong",     "slug": "yuzhong",     "is_urban": True},
    {"name": "南岸区",     "pinyin": "nanan",       "slug": "nanan",       "is_urban": True},
    {"name": "九龙坡区",   "pinyin": "jiulongpo",   "slug": "jiulongpo",   "is_urban": True},
    {"name": "沙坪坝区",   "pinyin": "shapingba",   "slug": "shapingba",   "is_urban": True},
    {"name": "巴南区",     "pinyin": "banan",       "slug": "banan",       "is_urban": True},
    {"name": "大渡口区",   "pinyin": "dadukou",     "slug": "dadukou",     "is_urban": True},
    {"name": "北碚区",     "pinyin": "beibei",      "slug": "beibei",      "is_urban": True},
    {"name": "璧山区",     "pinyin": "bishan",      "slug": "bishan",      "is_urban": True},
    {"name": "江津区",     "pinyin": "jiangjin",    "slug": "jiangjin",    "is_urban": True},
    {"name": "永川区",     "pinyin": "yongchuan",   "slug": "yongchuan",   "is_urban": True},
    {"name": "合川区",     "pinyin": "hechuan",     "slug": "hechuan",     "is_urban": True},
    {"name": "长寿区",     "pinyin": "changshou",   "slug": "changshou",   "is_urban": True},
    {"name": "涪陵区",     "pinyin": "fuling",      "slug": "fuling",      "is_urban": True},
    {"name": "南川区",     "pinyin": "nanchuan",    "slug": "nanchuan",    "is_urban": True},
    {"name": "綦江区",     "pinyin": "qijiang",     "slug": "qijiang",     "is_urban": True},
    {"name": "大足区",     "pinyin": "dazu",        "slug": "dazu",        "is_urban": True},
    {"name": "铜梁区",     "pinyin": "tongliang",   "slug": "tongliang",   "is_urban": True},
    {"name": "潼南区",     "pinyin": "tongnan",     "slug": "tongnan",     "is_urban": True},
    {"name": "荣昌区",     "pinyin": "rongchang",   "slug": "rongchang",   "is_urban": True},
    {"name": "万州区",     "pinyin": "wanzhou",     "slug": "wanzhou",     "is_urban": False},
    {"name": "开州区",     "pinyin": "kaizhou",     "slug": "kaizhou",     "is_urban": False},
    {"name": "梁平区",     "pinyin": "liangping",   "slug": "liangping",   "is_urban": False},
    {"name": "武隆区",     "pinyin": "wulong",      "slug": "wulong",      "is_urban": False},
    {"name": "城口县",     "pinyin": "chengkou",    "slug": "chengkou",    "is_urban": False},
    {"name": "丰都县",     "pinyin": "fengdu",      "slug": "fengdu",      "is_urban": False},
    {"name": "垫江县",     "pinyin": "dianjiang",   "slug": "dianjiang",   "is_urban": False},
    {"name": "忠县",       "pinyin": "zhongxian",   "slug": "zhongxian",   "is_urban": False},
    {"name": "云阳县",     "pinyin": "yunyang",     "slug": "yunyang",     "is_urban": False},
    {"name": "奉节县",     "pinyin": "fengjie",     "slug": "fengjie",     "is_urban": False},
    {"name": "巫山县",     "pinyin": "wushan",      "slug": "wushan",      "is_urban": False},
    {"name": "巫溪县",     "pinyin": "wuxi",        "slug": "wuxi",        "is_urban": False},
    {"name": "黔江区",     "pinyin": "qianjiang",   "slug": "qianjiang",   "is_urban": False},
    {"name": "石柱土家族自治县",     "pinyin": "shizhu",    "slug": "shizhu",    "is_urban": False},
    {"name": "秀山土家族苗族自治县", "pinyin": "xiushan",   "slug": "xiushan",   "is_urban": False},
    {"name": "酉阳土家族苗族自治县", "pinyin": "youyang",   "slug": "youyang",   "is_urban": False},
    {"name": "彭水苗族土家族自治县", "pinyin": "pengshui",  "slug": "pengshui",  "is_urban": False},
]

DISTRICT_BY_NAME: dict[str, dict] = {d["name"]: d for d in DISTRICTS}
DISTRICT_BY_SLUG: dict[str, dict] = {d["slug"]: d for d in DISTRICTS}

# ============================================================
# URL 模板（移动站 m.fang.com）
# ============================================================
BASE_URL = "https://m.fang.com"
SEED_URL = "https://m.fang.com/esf/cq/"
# 列表页: ?page=N (每页 30 条)
LIST_URL_TEMPLATE = "https://m.fang.com/esf/{slug}/?page={page}"
# 详情页
DETAIL_URL_TEMPLATE = "https://m.fang.com/esf/cq/{house_id}.html"

# ============================================================
# 速率限制（秒）— 移动站反爬轻，适当放宽
# ============================================================
LIST_PAGE_DELAY = (1.5, 3.0)
DETAIL_PAGE_DELAY = (1.0, 2.0)
JITTER_RANGE = (0.7, 1.3)

# ============================================================
# 并发控制
# ============================================================
LIST_CONCURRENCY = 3
DETAIL_CONCURRENCY = 3    # SQLite 单写瓶颈，不宜过高

# ============================================================
# 分页控制
# ============================================================
MAX_PAGES_PER_DISTRICT = 100
LISTINGS_PER_PAGE = 30

# ============================================================
# User-Agent 池（移动端为主）
# ============================================================
USER_AGENTS: list[str] = [
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 14; SM-S9080) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 13; VOG-AL00) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 14; CPH2581) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 12; SM-G9910) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/130.0.0.0 Mobile/15E148 Safari/604.1",
]

# ============================================================
# 数据清洗 — 与桌面版共用，无变化
# ============================================================
PRICE_OUTLIER = {
    "total_price_min": 1.0,
    "total_price_max": 10000.0,
    "unit_price_min": 100.0,
    "unit_price_max": 100000.0,
    "area_min": 10.0,
    "area_max": 1000.0,
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
    "低": "低楼层", "低楼层": "低楼层", "底层": "低楼层",
    "中": "中楼层", "中楼层": "中楼层",
    "高": "高楼层", "高楼层": "高楼层", "顶层": "高楼层",
}

JARO_WINKLER_THRESHOLD = 0.92
COMMUNITY_NAME_STRIP_CHARS = "·•-－—"
