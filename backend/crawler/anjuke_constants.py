"""
安居客移动站 (m.anjuke.com) 爬虫常量 — 重庆二手房。

URL 结构:
  全城首页:  https://m.anjuke.com/cq/sale/?page=N
  区县子区域: https://m.anjuke.com/cq/sale/{district}-{subarea}/?page=N

每页 60 条房源，MLIST_MAIN 卡片，Vue SSR 直出 HTML。
"""

# ============================================================
# 基础配置
# ============================================================
SEED_URL = "https://m.anjuke.com/cq/sale/"
LIST_PAGE_TEMPLATE = "https://m.anjuke.com/cq/sale/{area}/?page={page}"
LISTINGS_PER_PAGE = 60

# 翻页控制（和 fang.com 保持一致）
MAX_PAGES = 100
MAX_PAGES_PER_AREA = 100
DRY_PAGE_THRESHOLD = 3
ZERO_YIELD_THRESHOLD = 5
LOW_YIELD_JUMP_THRESHOLD = 2
JUMP_PAGES = 2
MAX_JUMPS_PER_AREA = 3
FETCH_FAILURE_THRESHOLD = 3
CONTEXT_ROTATE_PAGES = 50

# 速率控制
MIN_PAGE_DELAY = 3.0      # 比 fang.com 更保守，避免 IP 限速
MAX_PAGE_DELAY = 6.0
PROGRESSIVE_DELAY_PER_10 = 0.5

# ============================================================
# 区县子区域配置
#
# 安居客使用拼音子区域，需要映射到 DB 区县名。
# 每个子区域一个 URL path，格式: {pinyin_district}-{pinyin_subarea}
# ============================================================

# pinyin_district → DB 区县名
ANJUKE_DISTRICT_MAP: dict[str, str] = {
    "yuzhong": "渝中区",
    "jiangbei": "两江新区",      # 原江北区 → 两江新区
    "yubei": "两江新区",         # 原渝北区 → 两江新区
    "nanana": "南岸区",
    "jiulongpo": "九龙坡区",
    "shapingba": "沙坪坝区",
    "banan": "巴南区",
    "dadukou": "大渡口区",
    "beibei": "北碚区",
    "wanzhouqu": "万州区",
    "fulingqu": "涪陵区",
    "jiangjinqu": "江津区",
    "hechuanqu": "合川区",
    "yongchuanqu": "永川区",
    "changshouqu": "长寿区",
    "nanchuanqu": "南川区",
    "qijiangqu": "綦江区",
    "dazhuqu": "大足区",
    "tongliangqu": "铜梁区",
    "tongnanqu": "潼南区",
    "rongchangqu": "荣昌区",
    "bishanqu": "璧山区",
    "kaizhouqukaixian": "开州区",
    "liangpingxian": "梁平区",
    "wulongxian": "武隆区",
    "qianjiangqu": "黔江区",
    "fengjiexian": "奉节县",
    "fengduxian": "丰都县",
    "dainjiangxian": "垫江县",
    "zhongxian": "忠县",
    "yunyangxian": "云阳县",
    "wuxixian": "巫溪县",
    "cqwushanxian": "巫山县",
    "chengkouxian": "城口县",
    "shizhutujiazuzizhixian": "石柱土家族自治县",
    "xiushantujiazumiaozuzizhixian": "秀山土家族苗族自治县",
    "youyangtujiazumiaozuzizhixian": "酉阳土家族苗族自治县",
    "pengshuimiaozutujiazuzizhixian": "彭水苗族土家族自治县",
}

# 子区域列表 — 从 m.anjuke.com/cq/sale/ 页面提取
# 格式: (area_path, DB区县名), area_path = "{district_pinyin}-{subarea_pinyin}"
ANJUKE_AREAS: list[tuple[str, str]] = [
    # ── 渝中区 (9) ──
    ("yuzhong-jiefangbeia", "渝中区"),
    ("yuzhong-daping", "渝中区"),
    ("yuzhong-hualongqiao", "渝中区"),
    ("yuzhong-caiyuanba", "渝中区"),
    ("yuzhong-chaotianmen", "渝中区"),
    ("yuzhong-lianglukou", "渝中区"),
    ("yuzhong-shangqingsi", "渝中区"),
    ("yuzhong-qixinggang", "渝中区"),
    ("yuzhong-daxigou", "渝中区"),
    # ── 江北区 → 两江新区 (11) ──
    ("jiangbei-jiangbeizui", "两江新区"),
    ("jiangbei-beibinlu", "两江新区"),
    ("jiangbei-dashiba", "两江新区"),
    ("jiangbei-guanyinqiao", "两江新区"),
    ("jiangbei-wulidian", "两江新区"),
    ("jiangbei-cqfusheng", "两江新区"),
    ("jiangbei-cqsenlingongyuan", "两江新区"),
    ("jiangbei-nanqiaosi", "两江新区"),
    ("jiangbei-shipuqiao", "两江新区"),
    ("jiangbei-cuntan", "两江新区"),
    ("jiangbei-tieshanping", "两江新区"),
    # ── 渝北区 → 两江新区 (26) ──
    ("yubei-zhaomushan", "两江新区"),
    ("yubei-aotelaisi", "两江新区"),
    ("yubei-bijingongyuan", "两江新区"),
    ("yubei-dazhulin", "两江新区"),
    ("yubei-huahuiyuan", "两江新区"),
    ("yubei-huixian", "两江新区"),
    ("yubei-huixianzhi", "两江新区"),
    ("yubei-konggangxincheng", "两江新区"),
    ("yubei-lijia", "两江新区"),
    ("yubei-longtousi", "两江新区"),
    ("yubei-longxing", "两江新区"),
    ("yubei-ranjiaba", "两江新区"),
    ("yubei-renhe", "两江新区"),
    ("yubei-xinpaifang", "两江新区"),
    ("yubei-yuanyang", "两江新区"),
    ("yubei-yuelai", "两江新区"),
    ("yubei-yuzui", "两江新区"),
    ("yubei-zhongyanggongyuan", "两江新区"),
    ("yubei-cqjiaoqu", "两江新区"),
    ("yubei-huixing", "两江新区"),
    ("yubei-liangluxinpianqu", "两江新区"),
    ("yubei-longta", "两江新区"),
    ("yubei-taoyuan", "两江新区"),
    ("yubei-xinglong", "两江新区"),
    ("yubei-yibei", "两江新区"),
    ("yubei-zhisheng", "两江新区"),
    # ── 南岸区 (15) ──
    ("nanana-nanping", "南岸区"),
    ("nanana-danzishi", "南岸区"),
    ("nanana-chayuancq", "南岸区"),
    ("nanana-changshengqiao", "南岸区"),
    ("nanana-donghaichengzhou", "南岸区"),
    ("nanana-huangjueya", "南岸区"),
    ("nanana-huangjueyawan", "南岸区"),
    ("nanana-luojiaping", "南岸区"),
    ("nanana-nanbinlu", "南岸区"),
    ("nanana-nanshan", "南岸区"),
    ("nanana-shenglong", "南岸区"),
    ("nanana-tongyuanju", "南岸区"),
    ("nanana-tuqiwan", "南岸区"),
    ("nanana-xuefudadao", "南岸区"),
    ("nanana-yazitang", "南岸区"),
    # ── 九龙坡区 (13) ──
    ("jiulongpo-yangjiaping", "九龙坡区"),
    ("jiulongpo-xiejiawan", "九龙坡区"),
    ("jiulongpo-shiqiaopu", "九龙坡区"),
    ("jiulongpo-erlang", "九龙坡区"),
    ("jiulongpo-baguocheng", "九龙坡区"),
    ("jiulongpo-baishiyi", "九龙坡区"),
    ("jiulongpo-chenjiaping", "九龙坡区"),
    ("jiulongpo-gaoxinqua", "九龙坡区"),
    ("jiulongpo-cqhangu", "九龙坡区"),
    ("jiulongpo-huangjueping", "九龙坡区"),
    ("jiulongpo-panlong", "九龙坡区"),
    ("jiulongpo-taozichang", "九龙坡区"),
    ("jiulongpo-zhongliangshan", "九龙坡区"),
    # ── 沙坪坝区 (18) ──
    ("shapingba-daxuechenga", "沙坪坝区"),
    ("shapingba-shanxiaguangchang", "沙坪坝区"),
    ("shapingba-ciqikou", "沙坪坝区"),
    ("shapingba-xiyong", "沙坪坝区"),
    ("shapingba-chenjiaqiao", "沙坪坝区"),
    ("shapingba-cqxinqiao", "沙坪坝区"),
    ("shapingba-fengtianlu", "沙坪坝区"),
    ("shapingba-geleshan", "沙坪坝区"),
    ("shapingba-huxi", "沙坪坝区"),
    ("shapingba-jingkou", "沙坪坝区"),
    ("shapingba-liechebeizhan", "沙坪坝区"),
    ("shapingba-lijiaqiao", "沙坪坝区"),
    ("shapingba-qingmuguan", "沙坪坝区"),
    ("shapingba-shapingbaqita", "沙坪坝区"),
    ("shapingba-shuangbei", "沙坪坝区"),
    ("shapingba-tianxingqiao", "沙坪坝区"),
    ("shapingba-xiaolongkan", "沙坪坝区"),
    ("shapingba-yangongqiao", "沙坪坝区"),
    # ── 巴南区 (10) ──
    ("banan-longzhouwan", "巴南区"),
    ("banan-yudong", "巴南区"),
    ("banan-lijiatuoa", "巴南区"),
    ("banan-huaxi", "巴南区"),
    ("banan-guqiao", "巴南区"),
    ("banan-jieshi", "巴南区"),
    ("banan-nanpeng", "巴南区"),
    ("banan-nanquan", "巴南区"),
    ("banan-ronghui", "巴南区"),
    ("banan-shengdengshan", "巴南区"),
    # ── 大渡口区 (7) ──
    ("dadukou-jiugongmiao", "大渡口区"),
    ("dadukou-shuangshan", "大渡口区"),
    ("dadukou-baojushi", "大渡口区"),
    ("dadukou-dayancun", "大渡口区"),
    ("dadukou-jinjiawan", "大渡口区"),
    ("dadukou-qufu", "大渡口区"),
    ("dadukou-tiaodeng", "大渡口区"),
    # ── 北碚区 (7) ──
    ("beibei-caijia", "北碚区"),
    ("beibei-chengbeixinqu", "北碚区"),
    ("beibei-chengnanxinqu", "北碚区"),
    ("beibei-laochengqu", "北碚区"),
    ("beibei-shuitu", "北碚区"),
    ("beibei-xiema", "北碚区"),
    ("beibei-jinyunshan", "北碚区"),
    # ── 近郊/远郊 (每个区县 1 个聚合子区域) ──
    ("jiangjinqu-binjiangxincheng", "江津区"),
    ("jiangjinqu-dongbuxinchenga", "江津区"),
    ("jiangjinqu-jiangjinqita", "江津区"),
    ("jiangjinqu-jijiangchengqu", "江津区"),
    ("jiangjinqu-shuangfu", "江津区"),
    ("hechuanqu-hechuanqucq", "合川区"),
    ("yongchuanqu-yongchuanqucq", "永川区"),
    ("changshouqu-changshouqucq", "长寿区"),
    ("nanchuanqu-nanchuanqucq", "南川区"),
    ("qijiangqu-qijiangqucq", "綦江区"),
    ("dazhuqu-dazhuqucq", "大足区"),
    ("tongliangqu-tongliangqucq", "铜梁区"),
    ("tongnanqu-tongnanqucq", "潼南区"),
    ("rongchangqu-rongchangqucq", "荣昌区"),
    ("bishanqu-bishanqucq", "璧山区"),
    ("kaizhouqukaixian-kaizhouqukaixiancq", "开州区"),
    ("liangpingxian-liangpingxiancq", "梁平区"),
    ("wulongxian-wulongxiancq", "武隆区"),
    ("qianjiangqu-cqqianjiangqu", "黔江区"),
    ("fengjiexian-fengjiexiancq", "奉节县"),
    ("fengduxian-fengduxiancq", "丰都县"),
    ("dainjiangxian-dianjiangxiancq", "垫江县"),
    ("zhongxian-cqzhongxian", "忠县"),
    ("yunyangxian-yunyangxiancq", "云阳县"),
    ("wuxixian-cqwuxixian", "巫溪县"),
    ("cqwushanxian-wushanxiancq", "巫山县"),
    ("chengkouxian-chengkouxiancq", "城口县"),
    ("shizhutujiazuzizhixian-shizhutujiazuzizhixiancq", "石柱土家族自治县"),
    ("xiushantujiazumiaozuzizhixian-xiushantujiazhumiaozhuzizhixian", "秀山土家族苗族自治县"),
    ("youyangtujiazumiaozuzizhixian-youtujiazhuzizhixian", "酉阳土家族苗族自治县"),
    ("pengshuimiaozutujiazuzizhixian-pengshuimiaozutujiazuzizhixiancq", "彭水苗族土家族自治县"),
    # ── 万州区 (9) ──
    ("wanzhouqu-beishanc", "万州区"),
    ("wanzhouqu-gaosuntanga", "万州区"),
    ("wanzhouqu-guanyinyan", "万州区"),
    ("wanzhouqu-jiangnanxinqu", "万州区"),
    ("wanzhouqu-shuanghekou", "万州区"),
    ("wanzhouqu-taibai", "万州区"),
    ("wanzhouqu-wuqiao", "万州区"),
    ("wanzhouqu-zhoujiaba", "万州区"),
    ("wanzhouqu-zhuanxintai", "万州区"),
]

# 仅爬取有子区域的区县
ACTIVE_ANJUKE_AREAS = ANJUKE_AREAS

# 区县名 → 子区域列表
from collections import defaultdict
AREAS_BY_DISTRICT: dict[str, list[str]] = defaultdict(list)
for area_path, db_name in ANJUKE_AREAS:
    AREAS_BY_DISTRICT[db_name].append(area_path)
AREAS_BY_DISTRICT = dict(AREAS_BY_DISTRICT)
