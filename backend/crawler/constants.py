"""
爬虫全局常量：区县配置、URL 模板、速率限制、UA 池、字体映射缓存。

所有可调参数集中于此，避免硬编码分散到各模块。
"""

# ============================================================
# 区县配置（38 个）
# slug: 房天下 URL 中使用的拼音标识
# is_urban: True=主城/近郊, False=远郊
# ============================================================
DISTRICTS: list[dict] = [
    # --- 主城 9 区 ---
    {"name": "渝北区",     "pinyin": "yubei",      "slug": "yubei",      "is_urban": True},
    {"name": "江北区",     "pinyin": "jiangbei",    "slug": "jiangbei",    "is_urban": True},
    {"name": "渝中区",     "pinyin": "yuzhong",     "slug": "yuzhong",     "is_urban": True},
    {"name": "南岸区",     "pinyin": "nanan",       "slug": "nanan",       "is_urban": True},
    {"name": "九龙坡区",   "pinyin": "jiulongpo",   "slug": "jiulongpo",   "is_urban": True},
    {"name": "沙坪坝区",   "pinyin": "shapingba",   "slug": "shapingba",   "is_urban": True},
    {"name": "巴南区",     "pinyin": "banan",       "slug": "banan",       "is_urban": True},
    {"name": "大渡口区",   "pinyin": "dadukou",     "slug": "dadukou",     "is_urban": True},
    {"name": "北碚区",     "pinyin": "beibei",      "slug": "beibei",      "is_urban": True},
    # --- 近郊 12 区 ---
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
    # --- 远郊 17 区县 ---
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

# 按名称快速查找
DISTRICT_BY_NAME: dict[str, dict] = {d["name"]: d for d in DISTRICTS}
DISTRICT_BY_SLUG: dict[str, dict] = {d["slug"]: d for d in DISTRICTS}

# ============================================================
# URL 模板
# ============================================================
BASE_URL = "https://cq.esf.fang.com"
LIST_URL_TEMPLATE = (
    "https://cq.esf.fang.com/housing/house/list/"
    "{slug}__0_0_0_0_{page}_0_0_0/"
)
DETAIL_URL_TEMPLATE = "https://cq.esf.fang.com/chushou/{listing_id}.htm"

# ============================================================
# 速率限制（秒）
# ============================================================
LIST_PAGE_DELAY = (3.0, 5.0)       # 列表页请求间隔范围
DETAIL_PAGE_DELAY = (2.0, 4.0)     # 详情页请求间隔范围
JITTER_RANGE = (0.7, 1.3)          # 随机抖动系数范围

# ============================================================
# 并发控制
# ============================================================
LIST_CONCURRENCY = 3               # 列表页并发数 (asyncio.Semaphore)
DETAIL_CONCURRENCY = 5             # 详情页并发数 (asyncio.Semaphore)

# ============================================================
# 分页控制
# ============================================================
MAX_PAGES_PER_DISTRICT = 100       # 房天下单区县最大页数（约 3,000 条）

# 大区县价格区间分段 — 当总房源超 100 页时，按价格区间拆分搜索
PRICE_RANGES: list[tuple[int | None, int | None]] = [
    (None, 50),                     # 50 万以下
    (50, 100),                      # 50-100 万
    (100, 150),                     # 100-150 万
    (150, 200),                     # 150-200 万
    (200, None),                    # 200 万以上
]

# ============================================================
# 反爬策略
# ============================================================

# 15+ 真实浏览器 User-Agent（定期更新）
USER_AGENTS: list[str] = [
    # Chrome 130 / Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 Edg/130.0.0.0",
    # Chrome 129 / macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    # Firefox 132 / Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0",
    # Firefox 131 / macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:131.0) Gecko/20100101 Firefox/131.0",
    # Safari 18 / macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Safari/605.1.15",
    # Chrome 128 / Linux
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    # Edge 129 / Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36 Edg/129.0.0.0",
    # Chrome 127 / Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
    # Firefox 130 / Linux
    "Mozilla/5.0 (X11; Linux x86_64; rv:130.0) Gecko/20100101 Firefox/130.0",
    # Chrome 130 / macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    # Edge 128 / macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 Edg/128.0.0.0",
    # Chrome 126 / Linux
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    # Firefox 128 / Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0",
    # Chrome 125 / Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    # Firefox 115 ESR / Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:115.0) Gecko/20100101 Firefox/115.0",
]

# ============================================================
# 字体反爬
# ============================================================

# 字体文件 MD5 → 字符映射表（加密字符 → 真实数字）
# 首次遇到新字体时需人工标定后追加。key 为字体文件的 MD5 值，value 为 {乱码字符: 数字字符} 映射。
# 示例结构（实际映射需人工标定后填入）：
# FONT_MAPPING_CACHE: dict[str, dict[str, str]] = {
#     "a3f8c9d2e1b4567890abcdef12345678": {
#         "驋": "0", "閏": "1", "龒": "2", "驌": "3",
#         "驍": "4", "驎": "5", "驏": "6", "驐": "7",
#         "驑": "8", "驒": "9",
#     },
# }
FONT_MAPPING_CACHE: dict[str, dict[str, str]] = {}

# ============================================================
# 数据清洗
# ============================================================

# 价格异常值阈值
PRICE_OUTLIER = {
    "total_price_min": 1.0,          # 总价下限（万元）
    "total_price_max": 10000.0,       # 总价上限（万元）
    "unit_price_min": 100.0,          # 单价下限（元/㎡）
    "unit_price_max": 100000.0,       # 单价上限（元/㎡）
    "area_min": 10.0,                 # 面积下限（㎡）
    "area_max": 1000.0,               # 面积上限（㎡）
    "cross_check_tolerance": 0.5,     # 总价 vs 单价×面积 交叉验证容差（50%）
}

# 装修标准化映射
DECORATION_MAP: dict[str, str] = {
    "毛坯": "毛坯", "毛坯房": "毛坯",
    "简装": "简装", "简单装修": "简装", "简装修": "简装",
    "精装": "精装", "精装修": "精装",
    "豪装": "豪装", "豪华装修": "豪装", "豪华装": "豪装",
    "中装": "中装", "中等装修": "中装",
}

# 朝向标准化映射
ORIENTATION_MAP: dict[str, str] = {
    "南": "南", "朝南": "南",
    "北": "北", "朝北": "北",
    "南北": "南北", "南北通透": "南北", "朝南北": "南北",
    "东南": "东南", "朝东南": "东南",
    "西南": "西南", "朝西南": "西南",
    "东北": "东北", "朝东北": "东北",
    "西北": "西北", "朝西北": "西北",
    "东": "东", "朝东": "东",
    "西": "西", "朝西": "西",
    "东西": "东西", "朝东西": "东西",
}

# 楼层标准化映射
FLOOR_LEVEL_MAP: dict[str, str] = {
    "低": "低楼层", "低楼层": "低楼层", "底层": "低楼层",
    "中": "中楼层", "中楼层": "中楼层", "中层": "中楼层",
    "高": "高楼层", "高楼层": "高楼层", "高层": "高楼层", "顶层": "高楼层",
}

# ============================================================
# 小区去重
# ============================================================
JARO_WINKLER_THRESHOLD = 0.92       # Jaro-Winkler 相似度阈值

# 小区名规范化时需移除的干扰字符（分隔符等）
COMMUNITY_NAME_STRIP_CHARS = "·•-－—"
