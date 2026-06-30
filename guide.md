# 重庆市二手房源价格数据分析与可视化 — 技术方案

## 一、项目概述

**目标**：爬取重庆市各区县二手房源数据（5 万级），经过清洗、存储后，提供数据可视化与挖掘分析。

**技术栈**：Python 3.12（后端+爬虫+分析） + React 18（前端） + MySQL 8.0（数据库）

---

## 二、技术架构总览

```
┌─────────────────────────────────────────────────────────────────┐
│                        前端 (React 18)                           │
│  Vite + TypeScript + Tailwind CSS + ECharts + Zustand           │
│  端口: 5173                                                      │
└──────────────────────────┬──────────────────────────────────────┘
                           │ HTTP REST / SSE
┌──────────────────────────▼──────────────────────────────────────┐
│                     后端 API (FastAPI)                           │
│  Python 3.12 + Uvicorn + SQLAlchemy 2.0 async + Pydantic v2     │
│  端口: 8000                                                      │
├─────────────────────────────────────────────────────────────────┤
│  爬虫引擎 (asyncio 内置)                                         │
│  ├── asyncio + Semaphore 并发控制（I/O 密集型无需多进程）          │
│  ├── BackgroundTasks 管理爬取生命周期                              │
│  └── APScheduler 定时增量更新（轻量，无中间件依赖）                 │
├─────────────────────────────────────────────────────────────────┤
│                     数据库 (MySQL 8.0)                            │
│  端口: 3306                                                      │
└─────────────────────────────────────────────────────────────────┘
```

### 技术选型理由

| 层级 | 技术 | 选型理由 |
|------|------|----------|
| 前端框架 | React 18 + TypeScript | 生态丰富，ECharts/Table 组件成熟 |
| 构建工具 | Vite 5 | 秒级 HMR，TypeScript 原生支持 |
| CSS | Tailwind CSS 3 | 原子化 CSS，暗色模式内置支持 |
| 图表 | ECharts 5 | 中文生态最好，地图/热力图支持 |
| 状态管理 | Zustand | 轻量，无 boilerplate，TS 友好 |
| 后端框架 | FastAPI | 异步原生，自动 OpenAPI 文档，BackgroundTasks 内置，Pydantic 集成 |
| ORM | SQLAlchemy 2.0 async | 异步支持，迁移工具 Alembic 成熟 |
| 爬虫并发 | asyncio + Semaphore | I/O 密集型无需 Celery，FastAPI 原生异步即可高效调度 |
| 定时任务 | APScheduler | 轻量进程内调度，无需 Redis 中间件 |
| 爬虫引擎 | httpx + BeautifulSoup4 + fontTools | httpx 异步请求，fontTools 解密字体反爬 |
| 数据分析 | pandas + scikit-learn + scipy | 全流程覆盖（清洗→统计→建模） |
| 数据库 | MySQL 8.0 | 5 万级数据完全够用，窗口函数/CTE 已内置，部署简单 |
| 容器化 | Docker + Docker Compose | 一键部署 MySQL + FastAPI + 前端 |

---

## 三、数据爬取方案

### 3.1 数据源：房天下 (cq.esf.fang.com)

| 项目 | 说明 |
|------|------|
| 平台 | 房天下重庆二手房频道 |
| 反爬实况 | 无 WAF、无强制验证码，但存在 **字体反爬**（详情页价格数字用自定义字体加密）+ **IP 频率风控**（连续高速请求会临时封禁） |
| 解析方式 | httpx + BeautifulSoup4 + fontTools（字体解密），无需 Playwright |
| 目标数据量 | 5 万+ 条 |

> **关键提醒**：房天下的"低反爬"不等于"无反爬"。详情页的价格数字使用了 `@font-face` 自定义字体映射，直接 BeautifulSoup 解析文本会得到乱码（如 `□` 或 `驋`）。必须用 fontTools 解析字体文件、建立字符→数字的映射表。

**URL 结构**：

```
列表页: https://cq.esf.fang.com/housing/house/list/{district}__0_0_0_0_1_0_0_0/
                                                                          ↑ 页码
详情页: https://cq.esf.fang.com/chushou/{listing_id}.htm
```

**采集字段**（均为公开展示的挂牌信息，无个人信息）：

| 字段 | 来源页 | 说明 |
|------|--------|------|
| 总价 | 列表/详情 | 万元 |
| 单价 | 详情 | 元/㎡ |
| 面积 | 列表/详情 | ㎡ |
| 户型 | 列表/详情 | 室/厅/卫 |
| 楼层 | 详情 | 低/中/高楼层 |
| 总楼层 | 详情 | |
| 朝向 | 详情 | 南/南北/东南... |
| 装修 | 详情 | 毛坯/简装/精装/豪装 |
| 建筑年代 | 详情 | |
| 建筑类型 | 详情 | 板楼/塔楼/板塔结合 |
| 建筑结构 | 详情 | 钢混/砖混/框架 |
| 电梯 | 详情 | 有/无 |
| 小区名称 | 列表/详情 | |
| 小区地址 | 详情 | 仅到小区级别 |
| 挂牌日期 | 详情 | |
| 房源链接 | 列表 | 来源 URL |

**数据量估算**：

| 区域类型 | 区县数 | 每区县估计 | 小计 |
|----------|--------|------------|------|
| 主城 9 区 | 9 | 3,000-5,000 | ~36,000 |
| 近郊 12 区 | 12 | 1,000-2,000 | ~18,000 |
| 远郊 17 县 | 17 | 200-800 | ~8,500 |
| **合计** | **38** | | **~62,500** |

> 保守估计 5 万+，满足目标。若部分远郊区县数据量不足，按价格/面积分段搜索可进一步补充。

**合规说明**：仅采集房产平台公开展示的挂牌信息（房价/户型/小区等），数据类型为市场统计数据。业主姓名、电话、身份证号、具体门牌号等个人信息不在采集范围内，也不在页面公开显示。

### 3.2 爬虫架构：asyncio 并发（无 Celery）

对于 5 万级 I/O 密集型任务，Celery + Redis 属于过度设计。直接用 asyncio + Semaphore 即可实现高效并发爬取，部署零中间件依赖。

```
FastAPI BackgroundTasks (启停控制)
       │
       ▼
┌──────────────────────────────────────────────────┐
│              asyncio 爬虫引擎                      │
│                                                    │
│  asyncio.Semaphore(5) — 控制并发连接数              │
│       │                                            │
│       ├──▶ 列表页协程池 (3 并发)                    │
│       │     └── 爬取各区县分页 → 提取房源 ID 列表    │
│       │                                            │
│       ├──▶ 详情页协程池 (5 并发)                    │
│       │     └── 逐条爬取详情 → fontTools 解密价格    │
│       │                                            │
│       └──▶ 清洗入库协程                             │
│             └── 字段标准化 → MD5 去重 → INSERT      │
│                                                    │
└──────────────────────────────────────────────────┘
       │
       ▼
  MySQL 8.0 (断点进度持久化)
```

**爬取流程**：

1. 前端点击"获取数据" → FastAPI BackgroundTasks 启动 `engine.crawl_all(district_ids)`
2. 列表页协程：每个区县一个协程，`asyncio.gather` 并发爬取分页列表，提取房源 ID
3. 详情页协程：Semaphore(5) 控制并发，逐条爬取详情（含字体解密）
4. 清洗入库：每完成一条立即 INSERT（而非批量），确保断点续爬时数据不丢失
5. 进度推送：每个区县完成后通过 SSE/WebSocket 实时推送进度到前端

**核心代码骨架** (`crawler/engine.py`)：

```python
import asyncio
from asyncio import Semaphore

class CrawlEngine:
    def __init__(self, db_session_factory):
        self.list_sem = Semaphore(3)    # 列表页 3 并发
        self.detail_sem = Semaphore(5)  # 详情页 5 并发
        self.db = db_session_factory
        self._running = False

    async def crawl_district(self, district_id: int):
        """爬取一个区县的全部房源"""
        async with self.list_sem:
            listing_ids = await self._fetch_all_list_pages(district_id)
        tasks = [self._crawl_one_detail(lid) for lid in listing_ids]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def crawl_all(self, district_ids: list[str]):
        """全量爬取：asyncio.gather 并发调度所有区县"""
        self._running = True
        tasks = [self.crawl_district(did) for did in district_ids]
        await asyncio.gather(*tasks, return_exceptions=True)

    def stop(self):
        self._running = False
```

**相比 Celery 方案的优势**：

| 维度 | Celery + Redis | asyncio 内置 |
|------|---------------|-------------|
| 部署依赖 | 额外部署 Redis + Celery Worker 进程 | 仅 FastAPI 进程 |
| 调试 | 序列化问题、Worker 日志分离 | 同一进程，pdb 直接断点 |
| 启停控制 | 需信号量 + Redis 标记 | `self._running` 布尔值 |
| 进度推送 | 需手动 WebSocket 广播 | 直接 SSE，无需中间件 |
| 内存开销 | Worker 进程 + Redis 内存 | 仅协程栈（~KB 级） |

### 3.3 反爬策略（两层防线）

房天下没有 WAF 和强制验证码，但有两道必须应对的机制：**字体反爬**和 **IP 频率风控**。

#### 第一层：字体反爬破解（fontTools）⚠️ 核心难点

房天下详情页的**总价、单价**数字使用 `@font-face` 自定义字体加密。浏览器渲染出的正常数字在 HTML 源码中是乱码（如 `驋`、`閏`），直接 BeautifulSoup 解析出来的文本无法直接使用。必须用 fontTools 破解。

**破解原理**：

```
HTML 源码:
  <span class="price">驋閏.龒万</span>

页面渲染后（字体映射生效）:
  132.5万

破解流程:
  1. 从 CSS 提取字体文件 URL（如 //img.fang.com/font/house2.woff）
  2. 下载 .woff 文件
  3. fontTools 解析 cmap 表，建立 Unicode→glyph名 映射
  4. 首次人工确认 0-9 各对应哪个 glyph，写入配置
  5. 后续自动解密
```

**核心代码**：

```python
# crawler/constants.py — 字体 MD5 → 映射缓存（预置已知字体）
FONT_MAPPING_CACHE: dict[str, dict[str, str]] = {
    # key: 字体文件的 MD5 值
    # value: {乱码字符: 真实数字}
    # 示例（需首次爬取后人工标定填入）:
    # "a3f8c9d2e1b4567890abcdef12345678": {
    #     "驋": "0", "閏": "1", "龒": "2", "驌": "3",
    #     "驍": "4", "驎": "5", "驏": "6", "驐": "7",
    #     "驑": "8", "驒": "9",
    # },
}
```

```python
# crawler/parsers/font_parser.py
from fontTools.ttLib import TTFont
from io import BytesIO
import hashlib
import httpx
from crawler.constants import FONT_MAPPING_CACHE

class FontDecryptor:
    def __init__(self):
        self._char_map: dict[str, str] = {}  # 乱码字符 → 真实数字

    async def load_font(self, font_url: str, client: httpx.AsyncClient):
        """下载字体文件 → 计算 MD5 → 命中缓存直接用；未命中需人工标定"""
        resp = await client.get(font_url)
        font_bytes = resp.content
        font_md5 = hashlib.md5(font_bytes).hexdigest()

        # 1. 命中缓存：直接使用
        if font_md5 in FONT_MAPPING_CACHE:
            self._char_map = FONT_MAPPING_CACHE[font_md5]
            return

        # 2. 未命中：自动解析 + 标定后追加到缓存
        font = TTFont(BytesIO(font_bytes))
        cmap = font.getBestCmap()

        # 收集所有加密字符（Unicode > 0x4E00 且 glyph 名含 'uni'）
        encrypted_chars = {}
        for unicode_val, glyph_name in cmap.items():
            if 'uni' in glyph_name and unicode_val > 0x2000:
                encrypted_chars[glyph_name] = chr(unicode_val)

        # 人工标定：需在一套房源页面上对照渲染结果确认 0-9 对应关系
        # 此处抛出异常，由开发者手动标定后追加到 FONT_MAPPING_CACHE
        raise FontNotCachedError(
            f"新字体 MD5={font_md5}，共 {len(encrypted_chars)} 个加密 glyph，"
            f"请在浏览器中打开房源详情页，对照价格数字标定映射表后，"
            f"将 MD5→映射 追加到 constants.py 的 FONT_MAPPING_CACHE 中。"
            f"\nglyph 列表: {encrypted_chars}"
        )

    def decrypt(self, raw_text: str) -> str:
        return ''.join(self._char_map.get(c, c) for c in raw_text)
```

**字体变更处理流程**：当房天下更新字体文件时（通常数月一次），`FontNotCachedError` 会中断爬虫并输出完整的异常信息。开发者只需：
1. 打开任意房源详情页查看正常渲染的价格
2. 将页面中数字与 HTML 源码中的乱码字符一一对应
3. 追加一行到 `FONT_MAPPING_CACHE` 字典

完成一次标定大约耗时 2 分钟，之后全自动。

#### 第二层：频率控制 + 断点续爬 + tenacity 重试

| 策略 | 实现方式 |
|------|----------|
| 请求频率 | 列表页 3-5s/次，详情页 2-4s/次，`random.uniform(0.7, 1.3)` 倍抖动—**不能用 1.5s**，全量爬取持续请求 28h+ 必触发 IP 封禁 |
| tenacity 重试 | `@retry(stop=3, wait=wait_exponential(min=5, max=60))`，遇到 429/403 指数退避 |
| 断点续爬 | 每页完成后立即写 `crawl_progress` 表记录 (district_id, page, status)，中断后从最大已完成页+1 恢复 |
| User-Agent 池 | 15+ 真实浏览器 UA，随机轮换 |
| Referer 链 | 首页 → 区县列表 → 分页列表 → 详情，缺环即被拒 |
| IP 代理 | 免费代理（站大爷）作为起步；若大面积触发 429 则升级为付费 HTTP 隧道 |
| Cookie | httpx.AsyncClient 自动管理，失效时重走首页获取 |

```python
# fetcher.py — tenacity 装饰器
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=5, min=5, max=60),
    reraise=True
)
async def fetch_page(url: str, client: httpx.AsyncClient) -> str:
    resp = await client.get(url)
    if resp.status_code == 429:
        raise RuntimeError("Rate limited")
    resp.raise_for_status()
    return resp.text
```

> **时间估算**：按 3s/条详情 × 50,000 条 × 5 并发 ≈ 8.3 小时。配合断点续爬，实际分 1-2 晚完成全量爬取。

### 3.4 增量更新策略

```
全量爬取（首次）: 爬取所有区县全部在售房源 → 预计 8-15 万条
       │
       ▼
每日增量: 爬取当日新挂牌房源（按挂牌日期筛选）→ 增量合并
       │
       ▼
每周全量对比: 重新爬取全部列表页房源ID → 与数据库对比
       ├── 新增: 数据库无此ID → 爬详情入库
       ├── 下架: 数据库中此ID不在最新列表 → 标记 status='removed'
       └── 变更: MD5 不一致 → 爬详情更新 + 记录价格历史
```

### 3.5 核心爬虫代码结构（Python）

```
crawler/
├── __init__.py
├── engine.py            # 爬虫引擎，asyncio 并发调度
├── fetcher.py           # HTTP 请求封装（UA轮换、代理、tenacity 重试）
├── parsers/
│   ├── list_parser.py   # 列表页 HTML 解析
│   ├── detail_parser.py # 详情页 HTML 解析 → 结构化 dict
│   └── font_parser.py   # fontTools 字体文件解析 + 解密映射
├── cleaner.py           # 数据清洗与去重逻辑
├── dedup.py             # MD5 去重 + 增量对比
├── pipelines.py         # 数据入库 pipeline
└── constants.py         # 区县列表、URL 模板、字段映射、字体映射配置
```

---

## 四、数据库设计

### 4.1 ER 图（核心表）

```
districts (区县)                    communities (小区)
┌──────────────────┐               ┌──────────────────┐
│ id (PK)          │◀──────────────│ district_id (FK) │
│ name             │               │ id (PK)          │
│ pinyin           │               │ name             │
│ level            │               │ address          │
└──────────────────┘               │ building_year    │
                                   │ lng, lat         │
                                   └──────┬───────────┘
                                          │
listings (房源)                           │
┌──────────────────────┐                  │
│ id (PK)              │                  │
│ external_id (UNIQUE) │  平台房源ID       │
│ district_id (FK)     │──────────────────┤
│ community_id (FK)    │──────────────────┘
│ title                │
│ total_price          │  总价(万元)
│ unit_price           │  单价(元/㎡)
│ area                 │  面积(㎡)
│ room/hall/bathroom   │  户型
│ floor_level          │  楼层(低/中/高)
│ total_floors         │  总楼层
│ orientation          │  朝向
│ decoration           │  装修情况
│ building_type        │  建筑类型
│ has_elevator         │  是否有电梯
│ listing_date         │  挂牌日期
│ status               │  active/sold/removed
│ md5_hash             │  增量对比用
│ source_url           │  原始URL
│ first_seen_at        │
│ last_updated_at      │
└──────────┬───────────┘
           │ 1:N
price_history (价格历史)
┌──────────────────────┐
│ id (PK)              │
│ listing_id (FK)      │
│ total_price          │
│ unit_price           │
│ record_date          │
└──────────────────────┘
```

### 4.2 完整建表 SQL (MySQL 8.0 / InnoDB)

```sql
-- 0. 创建数据库
CREATE DATABASE IF NOT EXISTS cq_house
    DEFAULT CHARACTER SET utf8mb4
    DEFAULT COLLATE utf8mb4_unicode_ci;
USE cq_house;

-- 1. 行政区划表
CREATE TABLE districts (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    name        VARCHAR(50)  NOT NULL,          -- 渝北区
    pinyin      VARCHAR(100),                   -- yubei
    level       TINYINT DEFAULT 1,              -- 1=区县
    is_urban    TINYINT(1) DEFAULT 1,           -- 是否主城区
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- 2. 小区表
CREATE TABLE communities (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    name            VARCHAR(200) NOT NULL,
    district_id     INT,
    address         VARCHAR(500),
    building_year   INT,                        -- 建成年份
    property_type   VARCHAR(50),                -- 住宅/商住/别墅
    property_fee    DECIMAL(10,2),              -- 物业费(元/㎡/月)
    developer       VARCHAR(200),               -- 开发商
    building_count  INT,                        -- 楼栋数
    household_count INT,                        -- 总户数
    green_rate      DECIMAL(5,2),               -- 绿化率(%)
    plot_ratio      DECIMAL(5,2),               -- 容积率
    lng             DECIMAL(10,7),              -- 经度
    lat             DECIMAL(10,7),              -- 纬度
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (district_id) REFERENCES districts(id)
) ENGINE=InnoDB;
CREATE INDEX idx_communities_district ON communities(district_id);

-- 3. 房源表（核心表）
CREATE TABLE listings (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    external_id         VARCHAR(100) NOT NULL,      -- 平台房源ID
    district_id         INT,
    community_id        INT,
    title               VARCHAR(500),
    source_platform     VARCHAR(100) DEFAULT 'fang.com',  -- 来源平台，多源逗号分隔
    source_url          VARCHAR(1000),

    -- 价格
    total_price         DECIMAL(12,2),              -- 总价(万元)
    unit_price          DECIMAL(10,2),              -- 单价(元/㎡)

    -- 房屋属性
    area                DECIMAL(10,2),              -- 面积(㎡)
    room_count          TINYINT,                    -- 室
    hall_count          TINYINT,                    -- 厅
    bathroom_count      TINYINT,                    -- 卫
    floor_level         VARCHAR(20),                -- 低楼层/中楼层/高楼层
    total_floors        SMALLINT,                   -- 总楼层
    orientation         VARCHAR(50),                -- 南/南北/东南...
    decoration          VARCHAR(50),                -- 毛坯/简装/精装/豪装
    building_type       VARCHAR(50),                -- 板楼/塔楼/板塔结合
    building_structure  VARCHAR(50),                -- 钢混/砖混/框架
    has_elevator        TINYINT(1),
    listing_date        DATE,                       -- 挂牌日期
    listing_age_days    INT,                        -- 挂牌天数(计算字段)

    -- 状态
    status              VARCHAR(20) DEFAULT 'active', -- active/sold/removed
    status_change_date  DATE,

    -- 元数据
    md5_hash            VARCHAR(32),                -- 关键字段MD5，增量对比
    crawl_batch_id      INT,
    first_seen_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_updated_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    UNIQUE KEY uq_external_id (external_id),
    FOREIGN KEY (district_id)  REFERENCES districts(id),
    FOREIGN KEY (community_id) REFERENCES communities(id)
) ENGINE=InnoDB;

-- 索引设计
-- 原则：只保留高区分度 + 高频查询字段，避免爬虫写入时维护大量低区分度索引
-- 单列索引（高区分度 + 高频排序/范围查询）
CREATE INDEX idx_listings_district    ON listings(district_id);
CREATE INDEX idx_listings_community   ON listings(community_id);
CREATE INDEX idx_listings_unit_price  ON listings(unit_price);
CREATE INDEX idx_listings_total_price ON listings(total_price);
CREATE INDEX idx_listings_area        ON listings(area);
CREATE INDEX idx_listings_list_date   ON listings(listing_date);
CREATE INDEX idx_listings_md5         ON listings(md5_hash);
-- 复合索引（覆盖 99% 筛选场景）
CREATE INDEX idx_listings_dist_status_price ON listings(district_id, status, unit_price);
CREATE INDEX idx_listings_comm_status       ON listings(community_id, status);
-- 注意：decoration、room_count、status 等低区分度字段（5-10 个取值）
--       不建单列索引，MySQL 优化器会直接全表扫描，建了也用不上且拖慢写入

-- 4. 价格历史表
CREATE TABLE price_history (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    listing_id  INT NOT NULL,
    total_price DECIMAL(12,2),
    unit_price  DECIMAL(10,2),
    record_date DATE NOT NULL,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (listing_id) REFERENCES listings(id) ON DELETE CASCADE
) ENGINE=InnoDB;
CREATE INDEX idx_price_hist_listing ON price_history(listing_id);
CREATE INDEX idx_price_hist_date    ON price_history(record_date);

-- 5. 爬取批次表
CREATE TABLE crawl_batches (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    type                VARCHAR(20) NOT NULL,        -- full / incremental
    status              VARCHAR(20) DEFAULT 'pending', -- pending/running/completed/failed
    started_at          TIMESTAMP NULL,
    finished_at         TIMESTAMP NULL,
    total_tasks         INT DEFAULT 0,
    completed_tasks     INT DEFAULT 0,
    new_listings        INT DEFAULT 0,
    updated_listings    INT DEFAULT 0,
    removed_listings    INT DEFAULT 0,
    error_summary       JSON DEFAULT NULL            -- 错误汇总
) ENGINE=InnoDB;

-- 6. 爬取任务明细表
CREATE TABLE crawl_tasks (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    batch_id        INT,
    district_id     INT,
    status          VARCHAR(20) DEFAULT 'pending',
    page_start      INT DEFAULT 1,
    page_end        INT,
    listings_found  INT DEFAULT 0,
    error_message   TEXT,
    started_at      TIMESTAMP NULL,
    finished_at     TIMESTAMP NULL,
    FOREIGN KEY (batch_id)    REFERENCES crawl_batches(id),
    FOREIGN KEY (district_id) REFERENCES districts(id)
) ENGINE=InnoDB;
CREATE INDEX idx_crawl_tasks_batch ON crawl_tasks(batch_id);
```

### 4.3 设计备注

**小区去重问题** — 爬虫入库阶段的小区名称常存在错别字或简写差异（如"龙湖·U城" vs "龙湖U城" vs "龙湖U城一期"）。若不加控制，同一个物理小区可能产生 3-5 条 `communities` 记录，后续按 `community_id` 聚合均价时会产生偏差。

**三阶段解决方案**：

```
爬虫入库时（自动）:
  使用 Jaro-Winkler 相似度 > 0.92 匹配已有 communities 表
    • "龙湖U城" vs "龙湖·U城"     → 相似度 0.95 → 匹配成功
    • "龙湖U城" vs "龙湖U城一期"   → 相似度 0.88 → 匹配失败，INSERT 新行
    • "龙湖U城" vs "万科金色家园"   → 相似度 0.45 → 匹配失败
  匹配命中 → 复用已有 community_id
  匹配失败 → INSERT 新行（允许重复存在）

管理后台（人工/规则合并）:
  提供"小区合并"功能：
    • 列表展示疑似重复小区（name 相似度 0.85-0.95 的对）
    • 人工勾选确认 → 合并后保留最早的 community_id
    • 自动更新所有关联房源的外键

分析阶段（规避）:
  关键统计指标不按 community_id 聚合，改为按 district_id 聚合
  小区级别分析仅在小区已去重合并后进行
```

> 该问题不影响分析结论——只要分析查询按 `district_id` 而非 `community_id` 聚合，区县均价的偏差在 < 0.1% 量级。

---

## 五、后端架构

### 5.1 项目结构

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                # FastAPI 应用入口
│   ├── config.py              # 配置管理（环境变量/pydantic-settings）
│   ├── database.py            # SQLAlchemy async engine + session
│   │
│   ├── models/                # SQLAlchemy ORM 模型
│   │   ├── __init__.py
│   │   ├── district.py
│   │   ├── community.py
│   │   ├── listing.py
│   │   ├── price_history.py
│   │   └── crawl.py           # crawl_batches / crawl_tasks
│   │
│   ├── schemas/               # Pydantic 请求/响应模型
│   │   ├── __init__.py
│   │   ├── listing.py
│   │   ├── district.py
│   │   ├── crawl.py
│   │   └── analytics.py
│   │
│   ├── api/                   # 路由与控制器
│   │   ├── __init__.py
│   │   ├── v1/
│   │   │   ├── __init__.py
│   │   │   ├── listings.py    # 房源 CRUD + 筛选查询
│   │   │   ├── districts.py   # 区县数据
│   │   │   ├── crawl.py       # 爬取控制 API
│   │   │   └── analytics.py   # 分析数据 API
│   │   └── deps.py            # 依赖注入（DB session 等）
│   │
│   ├── services/              # 业务逻辑层
│   │   ├── __init__.py
│   │   ├── listing_service.py
│   │   ├── crawl_service.py   # 爬取调度逻辑
│   │   └── analytics_service.py
│   │
│   └── utils/
│       ├── __init__.py
│       ├── pagination.py      # 统一分页
│       └── response.py        # 统一响应格式
│
├── crawler/                   # 爬虫模块（参见 3.5 节）
│
├── analytics/                 # 数据分析模块
│   ├── __init__.py
│   ├── stats.py               # 描述性统计
│   ├── clustering.py          # 聚类分析
│   ├── regression.py          # 回归分析
│   └── trends.py              # 趋势分析
│
├── scheduler/                 # 定时任务（APScheduler，轻量级）
│   ├── __init__.py
│   └── jobs.py                # 定时增量爬取任务
│
├── alembic/                   # 数据库迁移
│   └── versions/
│
├── requirements.txt
├── Dockerfile
└── docker-compose.yml         # 根目录，统一编排
```

### 5.2 APScheduler 生命周期管理

> APScheduler 是进程内调度器，若只在 `jobs.py` 中创建全局实例而不与 FastAPI 事件绑定，应用重启后定时任务会丢失，爬取状态也会因存于内存而无法恢复。

**正确方式：FastAPI startup/shutdown 挂钩 + crawl_batches 表持久化**

```python
# app/main.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from contextlib import asynccontextmanager

scheduler = AsyncIOScheduler()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # === 启动时 ===
    # 1. 恢复未完成的爬取任务（进程重启后从中断点继续）
    await resume_incomplete_batches()

    # 2. 注册定时任务（replace_existing=True 确保重启后覆盖，不重复）
    scheduler.add_job(
        func=run_weekly_incremental_crawl,
        trigger=CronTrigger(day_of_week='mon', hour=2, minute=0),
        id="weekly_incremental",
        replace_existing=True,
    )
    scheduler.start()
    app.state.scheduler = scheduler

    yield  # FastAPI 运行中...

    # === 关闭时 ===
    scheduler.shutdown(wait=False)


app = FastAPI(lifespan=lifespan)
```

```python
# scheduler/jobs.py
from sqlalchemy import select
from app.database import async_session

async def run_weekly_incremental_crawl():
    """每周一凌晨 2 点执行增量爬取"""
    async with async_session() as db:
        # 从 crawl_batches 表恢复上次进度
        last_batch = await db.execute(
            select(CrawlBatch).where(
                CrawlBatch.type == 'incremental',
                CrawlBatch.status == 'completed'
            ).order_by(CrawlBatch.finished_at.desc()).limit(1)
        )
        last_batch = last_batch.scalar_one_or_none()

        # 创建新批次（持久化到数据库，非内存）
        batch = CrawlBatch(type='incremental', status='running')
        db.add(batch)
        await db.commit()

        # 执行增量逻辑...
        engine = CrawlEngine(async_session)
        await engine.crawl_incremental(last_batch)

        batch.status = 'completed'
        await db.commit()
```

**关键原则**：

| 问题 | 对策 |
|------|------|
| 定时任务丢失 | `replace_existing=True` + `lifespan` 事件确保每次重启后重新注册 |
| 爬取中断后丢失进度 | 每完成一个区县/页面即写 `crawl_batches` 表，不依赖内存状态 |
| 重复执行 | `CrawlBatch` 的 running 状态作为互斥锁，启动前检查是否有 running 中的同类型批次 |

### 5.3 API 设计

#### 基础路径: `/api/v1`

#### 房源接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/listings` | 房源列表（分页+筛选+排序） |
| GET | `/listings/{id}` | 房源详情 |
| GET | `/listings/{id}/history` | 某房源价格变动历史 |
| GET | `/listings/stats/summary` | 汇总统计（均价/中位数/在售数） |

**查询参数** (`GET /listings`):
```
?district_id=1,2,3     # 区县筛选（多选）
&min_price=50           # 最低总价(万)
&max_price=200          # 最高总价(万)
&min_area=60            # 最小面积
&max_area=140           # 最大面积
&room_count=3           # 户型筛选
&decoration=精装        # 装修筛选
&status=active          # 状态
&sort_by=unit_price     # 排序字段
&order=asc              # 升序/降序
&page=1                 # 页码
&page_size=30           # 每页条数
```

**响应格式**（统一）:
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "items": [...],
    "total": 52300,
    "page": 1,
    "page_size": 30,
    "total_pages": 1744
  }
}
```

#### 区县/小区接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/districts` | 区县列表（含房源计数） |
| GET | `/districts/{id}/stats` | 区县维度统计 |
| GET | `/communities` | 小区列表（分页+搜索） |
| GET | `/communities/{id}` | 小区详情+在售房源数+均价 |

#### 爬取控制接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/crawl/start` | 启动爬取任务 |
| GET | `/crawl/status/{batch_id}` | 爬取进度（含各区县进度） |
| GET | `/crawl/batches` | 历史批次列表 |
| POST | `/crawl/stop/{batch_id}` | 停止爬取 |

**启动爬取请求体**:
```json
{
  "type": "full",                    // full / incremental
  "districts": [1, 2, 3],           // 指定区县ID，空=全部
  "max_pages_per_district": 100     // 每区县最大页数限制
}
```

**爬取进度响应** (WebSocket 实时推送):
```json
{
  "batch_id": 12,
  "status": "running",
  "progress": {
    "total": 38,
    "completed": 15,
    "districts": [
      {"name": "渝北区", "status": "completed", "found": 4520, "pages": 120},
      {"name": "江北区", "status": "running",   "found": 1203, "pages": 45},
      {"name": "渝中区", "status": "pending",   "found": 0,    "pages": 0}
    ]
  }
}
```

#### 数据分析接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/analytics/overview` | 总览仪表板数据 |
| GET | `/analytics/district-compare` | 区县对比分析 |
| GET | `/analytics/price-distribution` | 价格分布（直方图数据） |
| GET | `/analytics/trends` | 价格趋势（时间序列） |
| GET | `/analytics/correlation` | 价格因素相关性矩阵 |
| GET | `/analytics/clusters` | 聚类分析结果 |
| GET | `/analytics/feature-importance` | 特征重要性排序（非精准估值） |

### 5.4 核心依赖 (`requirements.txt`)

```
# Web 框架
fastapi==0.111.0
uvicorn[standard]==0.30.1

# 数据库
sqlalchemy[asyncio]==2.0.30
asyncmy==0.2.9
aiomysql==0.2.0
alembic==1.13.1

# 数据验证
pydantic==2.7.3
pydantic-settings==2.3.3

# 定时任务（轻量，进程内运行）
apscheduler==3.10.4

# 爬虫
httpx==0.27.0
beautifulsoup4==4.12.3
lxml==5.2.2
fonttools==4.53.0          # 字体反爬解密
tenacity==8.5.0            # 智能重试

# 数据分析
pandas==2.2.2
numpy==1.26.4
scikit-learn==1.5.0
scipy==1.13.1

# 工具
python-dotenv==1.0.1
loguru==0.7.2

# 测试
pytest==8.2.2
pytest-asyncio==0.23.7
httpx  # (测试用)
```

---

## 六、前端架构

### 6.1 项目结构

```
frontend/
├── public/
│   └── favicon.svg
├── src/
│   ├── main.tsx                    # 入口
│   ├── App.tsx                     # 根组件 + 路由
│   ├── vite-env.d.ts
│   │
│   ├── assets/
│   │   └── icons/                  # SVG 图标组件
│   │
│   ├── styles/
│   │   ├── index.css               # Tailwind 入口 + CSS 变量
│   │   └── theme.ts                # 主题配置对象
│   │
│   ├── components/                 # 通用组件
│   │   ├── layout/
│   │   │   ├── AppLayout.tsx       # 整体布局
│   │   │   ├── Navbar.tsx          # 顶部导航栏
│   │   │   └── SettingsDrawer.tsx  # 左侧设置抽屉
│   │   ├── ui/                     # 基础 UI 组件
│   │   │   ├── Button.tsx
│   │   │   ├── Select.tsx
│   │   │   ├── Chip.tsx
│   │   │   ├── Table.tsx
│   │   │   ├── Spinner.tsx
│   │   │   └── ThemeToggle.tsx
│   │   └── charts/                 # 图表封装组件
│   │       ├── BarChart.tsx
│   │       ├── PieChart.tsx
│   │       ├── LineChart.tsx
│   │       ├── ScatterChart.tsx
│   │       └── HeatMapChart.tsx
│   │
│   ├── pages/                      # 页面组件
│   │   ├── CrawlPage.tsx           # 数据爬取界面
│   │   │   ├── DistrictSelector.tsx
│   │   │   └── ProgressPanel.tsx
│   │   ├── DataStoragePage.tsx     # 数据存储界面
│   │   │   ├── FilterBar.tsx
│   │   │   └── ListingTable.tsx
│   │   └── AnalysisPage.tsx        # 数据分析界面
│   │       ├── OverviewCards.tsx
│   │       ├── PriceDistChart.tsx
│   │       ├── DistrictCompareChart.tsx
│   │       ├── TrendChart.tsx
│   │       └── ConclusionPanel.tsx
│   │
│   ├── stores/                     # Zustand 状态管理
│   │   ├── useThemeStore.ts        # 主题/语言
│   │   ├── useCrawlStore.ts        # 爬取状态
│   │   └── useFilterStore.ts       # 筛选条件
│   │
│   ├── hooks/                      # 自定义 Hooks
│   │   ├── useListings.ts          # 房源数据请求
│   │   ├── useCrawlProgress.ts     # WebSocket 爬取进度
│   │   └── useAnalytics.ts         # 分析数据请求
│   │
│   ├── api/                        # API 请求层
│   │   ├── client.ts               # axios 实例 + 拦截器
│   │   ├── listings.ts
│   │   ├── districts.ts
│   │   ├── crawl.ts
│   │   └── analytics.ts
│   │
│   ├── i18n/                       # 国际化
│   │   ├── index.ts
│   │   ├── zh.json
│   │   └── en.json
│   │
│   └── types/                      # TypeScript 类型定义
│       ├── listing.ts
│       ├── district.ts
│       └── analytics.ts
│
├── index.html
├── package.json
├── tsconfig.json
├── vite.config.ts
├── tailwind.config.ts
└── postcss.config.js
```

### 6.2 组件树

```
App
├── AppLayout
│   ├── Navbar
│   │   ├── SettingsButton (齿轮图标)
│   │   ├── NavLink × 3 (数据爬取 | 数据存储 | 数据分析)
│   │   ├── LanguageSwitch (中/En)
│   │   └── ThemeToggle (☀/🌙)
│   │
│   ├── SettingsDrawer (左侧滑出，宽度 50vw)
│   │   ├── SettingsTabs (爬取设置 | 通知设置 | ...)
│   │   └── SettingsPanel
│   │
│   └── <Outlet /> ─────────────────────
│       │
│       ├── CrawlPage
│       │   ├── DistrictSelector (上板块)
│       │   │   ├── DistrictChip[] (38个区县标签，可多选)
│       │   │   └── StartCrawlButton
│       │   └── ProgressPanel (下板块，overflow-y:auto)
│       │       └── DistrictProgressItem[] (每个区县一行)
│       │
│       ├── DataStoragePage
│       │   ├── FilterBar
│       │   │   ├── DistrictDropdown (区县筛选)
│       │   │   ├── StatusDropdown (在售/已售/下架)
│       │   │   ├── PriceRangeInput
│       │   │   └── ActionButtons (刷新 | 导出)
│       │   └── ListingTable (TanStack Table)
│       │       ├── 排序表头
│       │       ├── 分页器
│       │       └── 行点击展开详情
│       │
│       └── AnalysisPage
│           ├── OverviewCards (4 个统计卡片)
│           │   ├── 在售房源总数
│           │   ├── 全市均价
│           │   ├── 最高/最低区县
│           │   └── 近30天涨跌
│           ├── ChartGrid (2×3 网格)
│           │   ├── PriceBarChart (各区县均价柱状图)
│           │   ├── PriceDistHistogram (价格分布直方图)
│           │   ├── UnitPriceHeatmap (单价热力图)
│           │   ├── AreaPriceScatter (面积-价格散点图)
│           │   ├── DecorationPie (装修情况饼图)
│           │   └── PriceTrendLine (近12个月价格趋势)
│           └── ConclusionPanel (AI/挖掘结论)
```

### 6.3 主题系统

```css
/* styles/index.css */
:root {
  /* 亮色主题 */
  --color-primary:    #122e8a;
  --color-bg:         #f5efea;
  --color-accent:     #d9d3e8;  /* 10% primary + 90% bg */
  --color-text:       #1a1a1a;
  --color-text-white: #ffffff;
}

.dark {
  /* 暗色主题 */
  --color-primary:    #e6397c;
  --color-bg:         #1a1a1d;
  --color-accent:     #301f28;  /* 10% primary + 90% bg */
  --color-text:       #e0e0e0;
  --color-text-white: #ffffff;
}
```

### 6.4 核心前端依赖 (`package.json`)

```json
{
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-router-dom": "^6.23.1",
    "zustand": "^4.5.2",
    "axios": "^1.7.2",
    "@tanstack/react-table": "^8.17.3",
    "echarts": "^5.5.1",
    "echarts-for-react": "^3.0.2",
    "lucide-react": "^0.379.0",
    "react-i18next": "^14.1.2",
    "i18next": "^23.11.5",
    "clsx": "^2.1.1"
  },
  "devDependencies": {
    "typescript": "^5.4.5",
    "vite": "^5.2.12",
    "@vitejs/plugin-react": "^4.3.0",
    "tailwindcss": "^3.4.4",
    "postcss": "^8.4.38",
    "autoprefixer": "^10.4.19",
    "@types/react": "^18.3.3",
    "@types/react-dom": "^18.3.0"
  }
}
```

---

## 七、数据分析与挖掘方案

### 7.1 分析维度

```
                ┌─────────────────────────┐
                │     数据分析体系           │
                └───────────┬─────────────┘
           ┌────────────────┼────────────────┐
    ┌──────▼──────┐  ┌──────▼──────┐  ┌──────▼──────┐
    │  描述性统计   │  │  因素分析    │  │  聚类洞察    │
    └──────┬──────┘  └──────┬──────┘  └──────┬──────┘
           │                │                │
    • 均价/中位数      • 面积↔价格       • 房源聚类画像
    • 区县排名         • 楼层↔价格       • 区域分化特征
    • 装修分布         • 朝向↔价格       • 价格梯度地图
    • 户型分布         • 年代↔价格
    • 面积分布         • 区位↔价格
    • 价格分布         • 特征重要性排序
```

### 7.2 具体分析内容

#### (A) 描述性统计
- 全市及各区域均价、中位数、标准差、四分位数
- 房源数量区县排名（柱状图）
- 户型分布（饼图/玫瑰图）
- 装修情况分布（堆叠柱状图）
- 面积区间分布（直方图）
- 房龄分布（直方图）

#### (B) 价格影响因素分析（相关性 + 回归）⚠️ 定位为"因素重要性排序"

> **重要说明**：由于数据中缺少**楼层系数**（同一栋楼高区/低区价差）、**学区归属**、**地铁距离**等高影响变量，仅凭面积、房龄、朝向、装修等公开字段，RandomForest 回归模型的 R² 很难超过 0.6。此模块的定位是**"影响房价的关键因素排序"**，而非精准估值工具。

```python
# analytics/regression.py 核心思路
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import OneHotEncoder
from sklearn.pipeline import Pipeline

# 可用特征:
# - 数值型: area, total_floors, building_year, listing_age_days
# - 类别型: district, floor_level, orientation, decoration, building_type
# 目标: unit_price

# 输出定位:
# - 特征重要性排序（如 "面积贡献 35%，区县贡献 28%，房龄贡献 12%..."）
#    → 前端水平柱状图
# - R² 作为模型解释力参考，不做为估值精度承诺
# - 明确标注未纳入变量（学区/地铁/楼层系数）及其对模型的影响
```

#### (C) 聚类分析
```python
# analytics/clustering.py 核心思路
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA

# 用面积、单价、房龄、楼层等做 K-Means 聚类 (k=4~6)
# PCA 降维到2D → 散点图展示
# 每类特征画像 → "老破小/次新改善/核心豪宅/远郊大盘"
```

#### (D) 价格趋势分析（时间序列）
- 按月聚合均价 → 折线图
- 各区县价格环比/同比 → 表格+热力图
- 简单移动平均 (SMA) 平滑

#### (E) 最终结论输出

1. **重庆二手房市场整体画像**：均价水平、主要价格区间
2. **区域分化特征**：核心区 vs 近郊 vs 远郊的价差与走势
3. **价格核心驱动因素**：影响最大的变量及量化权重（非精确估值）
4. **购房建议**：基于数据的不同预算段推荐区域
5. **市场趋势判断**：过去 12 个月走势及短期预判
6. **分析局限性说明**：明确列出未纳入的高影响变量（学区、地铁距离、楼层系数等），说明这些变量缺失对结论精度的影响

---

## 八、部署方案

### 8.1 Docker Compose 编排

```yaml
# docker-compose.yml (根目录)
version: '3.8'
services:
  db:
    image: mysql:8.0
    environment:
      MYSQL_ROOT_PASSWORD: ${DB_ROOT_PASSWORD}
      MYSQL_DATABASE: cq_house
      MYSQL_USER: admin
      MYSQL_PASSWORD: ${DB_PASSWORD}
    volumes:
      - mysqldata:/var/lib/mysql
      - ./db/init.sql:/docker-entrypoint-initdb.d/init.sql  # 自动建表
    ports:
      - "3306:3306"
    command: --default-authentication-plugin=mysql_native_password
              --character-set-server=utf8mb4
              --collation-server=utf8mb4_unicode_ci

  backend:
    build: ./backend
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
    volumes:
      - ./backend:/app
    ports:
      - "8000:8000"
    depends_on: [db]
    environment:
      DATABASE_URL: mysql+asyncmy://admin:${DB_PASSWORD}@db:3306/cq_house

  frontend:
    build: ./frontend
    ports:
      - "5173:5173"
    depends_on: [backend]

volumes:
  mysqldata:
```

### 8.2 开发环境启动

```bash
# 1. 启动所有服务
docker-compose up -d

# 2. 数据库迁移
docker-compose exec backend alembic upgrade head

# 3. 导入区县基础数据
docker-compose exec backend python -c "from app.init_data import seed_districts; seed_districts()"

# 4. 首次全量爬取
curl -X POST http://localhost:8000/api/v1/crawl/start \
  -H "Content-Type: application/json" \
  -d '{"type": "full", "districts": []}'

# 5. 前端开发
cd frontend && npm run dev
```

---

## 九、开发计划

| 阶段 | 内容 | 工期 |
|------|------|------|
| **Phase 1** | 项目搭建：Docker 环境 + FastAPI 骨架 + React 骨架 + 数据库建表 | 3天 |
| **Phase 2** | 爬虫开发：房天下解析器 + fontTools 字体解密 + tenacity 重试 + 全量爬取 | 4天 |
| **Phase 3** | 后端 API：房源 CRUD + 筛选排序分页 + 爬取控制 + SSE 进度推送 | 4天 |
| **Phase 4** | 前端页面：三个主界面 + 导航栏 + 设置抽屉 + 主题切换 + i18n | 5天 |
| **Phase 5** | 数据分析：统计 + 因素重要性排序 + 聚类 + 趋势 + 图表 API + 前端柱状图/表格 | 4天 |
| **Phase 6** | 增量更新：APScheduler 定时任务 + 增量对比逻辑 + 价格历史记录 | 2天 |
| **Phase 7** | 联调优化 + 地图可视化（ECharts Map + GeoJSON，作为优化项） | 3天 |

---

## 十、关键风险与应对

| 风险 | 影响 | 应对措施 |
|------|------|----------|
| 字体文件更新 | 价格解密失败，数据变乱码 | fontTools 映射配置模块化；监控异常字符率，超阈值告警并人工更新映射表 |
| IP 频率封禁 | 全量爬取中断 | tenacity 指数退避重试 + 代理 IP 切换；断点续爬确保不丢数据 |
| 页面结构变更 | 解析器失效 | 关键 CSS/XPath 选择器写入 config，不硬编码；解析失败率监控告警 |
| 列表页 100 页上限 | 大区县数据截断，总量不足 | 按价格区间（50 万以下/50-100 万/100-200 万/200 万+）分段搜索，每个区间各 100 页 |
| 部分远郊区县房源稀少 | 总量不达 5 万 | 38 区县中核心 20 个即可覆盖 90% 数据；远郊不足不影响统计结论 |
| 数据质量问题 | 分析结论偏差 | 多层清洗：异常值检测(IQR) + 缺失值处理 + 人工抽检 5% |
| ECharts 地图耗时 | 前端交付延期 | 地图作为 Phase 7 优化项，先用柱状图/表格完成核心可视化 |
| 模型 R² 偏低 | 预测不准 | 明确定位为"因素重要性排序"，非精准估值；报告中列出未纳入变量的局限性 |

---

> **文档版本**: v2.0  
> **最后更新**: 2026-06-30
