# 重庆房产数据分析系统 — 架构文档

> **版本**: v0.2.1 | **日期**: 2026-07-02 | **分析深度**: 全栈架构 + 三大界面逐层剖析

---

## 目录

1. [系统总览](#1-系统总览)
2. [技术栈](#2-技术栈)
3. [项目结构](#3-项目结构)
4. [数据库架构](#4-数据库架构)
5. [后端架构](#5-后端架构)
6. [前端架构](#6-前端架构)
7. [界面一：数据爬取 (CrawlPage)](#7-界面一数据爬取-crawlpage)
8. [界面二：数据浏览 (DataStoragePage)](#8-界面二数据浏览-datastoragepage)
9. [界面三：数据分析 (AnalysisPage)](#9-界面三数据分析-analysispage)
10. [数据流与系统交互](#10-数据流与系统交互)
11. [定时任务与运维](#11-定时任务与运维)
12. [测试体系](#12-测试体系)

---

## 1. 系统总览

### 1.1 项目定位

重庆房产数据分析系统是一个**全栈单体应用**，聚焦于重庆市房产市场数据的自动采集、存储、浏览和多维度统计分析。系统通过爬虫自动抓取房天下 (m.fang.com) 的房源信息，提供数据浏览与筛选功能，并内置机器学习驱动的分析模块（聚类画像、特征重要性、价格预测、趋势分析）及地图可视化。

### 1.2 核心业务流程

```
┌──────────────────────────────────────────────────────────────────┐
│                        系统核心流程                               │
│                                                                  │
│  [定时/手动触发] → [爬虫引擎] → [数据清洗] → [去重/入库]         │
│                                                   │              │
│                                                   ▼              │
│  用户 ← [三大界面] ← [REST API] ← [SQLite WAL 数据库]           │
│    │                                                             │
│    ├── CrawlPage:     配置并触发爬取，实时监控进度               │
│    ├── DataStoragePage: 多维度筛选/排序/分页浏览房源             │
│    └── AnalysisPage:   7个分析Tab (概览/地图/区县/因素/聚类/     │
│                        趋势/预测)                                 │
└──────────────────────────────────────────────────────────────────┘
```

### 1.3 架构模式

- **后端**: 分层架构 (API Route → Service → Model/ORM → Database)
- **前端**: SPA 组件化架构 (Pages → Components/Hooks → API client → Stores)
- **通信**: REST API + SSE (Server-Sent Events) 实时推送爬取进度
- **调度**: APScheduler 进程内定时任务 (增量爬取 + 趋势缓存刷新)

---

## 2. 技术栈

### 2.1 前端

| 类别 | 技术 | 版本 | 用途 |
|------|------|------|------|
| 框架 | React | 19 | UI 组件框架 |
| 语言 | TypeScript | 6 | 类型安全 |
| 构建 | Vite | 8 | 开发服务器 + 生产构建 |
| CSS | Tailwind CSS | v4 | 原子化样式 |
| 图表 | ECharts + echarts-for-react | 6 | 柱状图/折线图/饼图/散点图/地图 |
| 状态管理 | Zustand | 5 | 轻量级全局状态 |
| 路由 | react-router-dom | 7 | 客户端路由 |
| HTTP | axios | — | API 请求 |
| 国际化 | react-i18next + i18next | 17/26 | 中/英双语 |
| 图标 | Lucide React | — | SVG 图标库 |
| 代码检查 | Oxlint | — | Lint 规则 |

### 2.2 后端

| 类别 | 技术 | 版本 | 用途 |
|------|------|------|------|
| 框架 | FastAPI + uvicorn | 0.111/0.30 | 异步 Web 框架 |
| 语言 | Python | 3.12 | — |
| ORM | SQLAlchemy (async) | 2.0.30 | 异步数据库操作 |
| 数据验证 | Pydantic | — | 请求/响应 Schema |
| 爬虫渲染 | Playwright | ≥1.45 | 无头浏览器渲染 JS 页面 |
| HTML 解析 | BeautifulSoup4 + lxml | 4.12/5.2 | HTML 提取 |
| 分析计算 | pandas + numpy + scikit-learn | 2.2/1.26/1.5 | 统计/聚类/回归/ML |
| 定时任务 | APScheduler | 3.10.4 | 进程内调度 |
| 重试机制 | tenacity | 8.5.0 | 指数退避重试 |
| 迁移 | Alembic | 1.13.1 | 数据库 Schema 迁移 |

### 2.3 数据库与基础设施

| 类别 | 技术 | 说明 |
|------|------|------|
| 数据库 | SQLite (WAL 模式) + aiosqlite | 零配置、并发读友好 |
| 部署 | 本地进程 (无 Docker) | start.py / start.bat 启动前后端 |
| 测试 | pytest 8.2 + pytest-asyncio 0.23 | 99 个测试用例全部通过 |
| 日志 | Python logging | 模块级日志 |

---

## 3. 项目结构

```
data_web/
├── README.md                       # 项目完整文档 (中文)
├── start.py / start.bat            # 跨平台启动脚本
├── _run_backend.bat                # 后端独立启动
├── _run_frontend.bat               # 前端独立启动
├── tasks/                          # Windows 批处理任务
│   ├── daily-update-ages.bat       # 每日房龄刷新
│   └── weekly-incremental.bat      # 每周增量爬取
│
├── backend/                        # Python 后端
│   ├── requirements.txt            # 36 个依赖包
│   ├── alembic.ini                 # 数据库迁移配置
│   ├── seed_data.py                # 37 个区县种子数据
│   ├── cq_house.db                 # SQLite 数据库 (运行时生成)
│   │
│   ├── app/                        # FastAPI 应用层
│   │   ├── main.py                 # 入口: 生命周期/调度器/CORS
│   │   ├── config.py               # 配置 (数据库路径自动计算)
│   │   ├── database.py             # 异步引擎 + 会话工厂
│   │   ├── api/
│   │   │   ├── deps.py             # 依赖注入 (get_db)
│   │   │   └── v1/
│   │   │       ├── analytics.py    # 7 个分析端点
│   │   │       ├── listings.py     # 房源 CRUD + 筛选
│   │   │       ├── crawl.py        # 爬取控制 + SSE
│   │   │       ├── districts.py    # 区县列表
│   │   │       ├── communities.py  # 小区信息
│   │   │       ├── map_data.py     # 地图热力图数据
│   │   │       └── health.py       # 健康检查
│   │   ├── models/                 # 6 个 ORM 模型
│   │   ├── schemas/                # Pydantic 请求/响应模型
│   │   ├── services/               # 业务逻辑层
│   │   │   ├── listing_service.py  # 房源查询构建器
│   │   │   └── crawl_service.py    # 爬取流程编排
│   │   └── utils/
│   │       └── response.py         # ok()/error() 响应工具
│   │
│   ├── crawler/                    # 爬虫引擎
│   │   ├── engine.py               # 异步爬取引擎 (状态机)
│   │   ├── playwright_fetcher.py   # Playwright 无头获取
│   │   ├── cleaner.py              # 数据清洗 + 归一化
│   │   ├── dedup.py                # MD5 去重
│   │   ├── pipelines.py            # 数据库写入管线
│   │   ├── constants.py            # 37 区县配置 + 常量和URL
│   │   ├── district_resolver.py    # 区县归属推断
│   │   └── parsers/
│   │       ├── list_parser.py      # 列表页 HTML 解析
│   │       └── detail_parser.py    # 详情页 HTML 解析
│   │
│   ├── analytics/                  # 数据分析模块
│   │   ├── stats.py                # 描述统计 + LRU 缓存
│   │   ├── trends.py               # SMA-7 趋势 + 线性预测 + 内存缓存
│   │   ├── regression.py           # RandomForest 特征重要性
│   │   ├── clustering.py           # KMeans + PCA + 肘部法则
│   │   └── predict.py              # KNN 加权估值
│   │
│   ├── scheduler/
│   │   └── jobs.py                 # 定时任务: 房龄刷新/增量爬取/趋势缓存
│   │
│   └── tests/                      # 8 个测试文件, 99 个用例
│       ├── conftest.py             # 异步 DB + TestClient fixtures
│       ├── test_crawl_safety.py
│       ├── test_data_integrity.py
│       ├── test_data_pollution.py
│       ├── test_dedup.py
│       ├── test_cleaner.py
│       ├── test_api_integration.py
│       └── test_district_mapping.py
│
└── frontend/                       # React 前端
    ├── index.html                  # HTML 入口 (zh-CN)
    ├── package.json                # Node 依赖 + 脚本
    ├── vite.config.ts              # Vite 配置: 代理 API → :8000
    ├── public/
    │   └── chongqing.json          # 重庆 GeoJSON 地图
    └── src/
        ├── main.tsx                # React 入口
        ├── pages/
        │   ├── CrawlPage.tsx       # 爬取控制面板
        │   ├── DataStoragePage.tsx # 房源浏览
        │   └── AnalysisPage.tsx    # 分析仪表盘
        ├── components/
        │   ├── charts/             # 5 个 ECharts 封装组件
        │   ├── layout/             # AppLayout + Navbar
        │   └── ui/                 # 通用 UI 原语
        ├── stores/                 # 3 个 Zustand Store
        ├── hooks/                  # 2 个自定义 Hook
        ├── api/                    # 4 个 API 模块
        ├── i18n/                   # 中/英翻译文件
        ├── types/                  # TypeScript 类型定义
        └── constants/              # 区县常量配置
```

---

## 4. 数据库架构

### 4.1 数据库配置

- **引擎**: SQLite via `sqlite+aiosqlite:///`，`check_same_thread=False`
- **PRAGMA**: `foreign_keys=ON`，`journal_mode=WAL`，`busy_timeout=30000`
- **会话**: `async_sessionmaker(expire_on_commit=False)`

### 4.2 ER 图 (6 张表)

```
┌──────────────┐       ┌──────────────────┐       ┌──────────────┐
│   districts  │       │   communities    │       │   listings   │
│──────────────│       │──────────────────│       │──────────────│
│ id (PK)      │◄──┐   │ id (PK)          │◄──┐   │ id (PK)      │
│ name         │   │   │ name             │   │   │ external_id  │
│ pinyin       │   │   │ district_id (FK) │   │   │ district_id  │
│ is_urban     │   │   │ address          │   ├───│ community_id │
│ created_at   │   │   │ lng, lat         │   │   │ title        │
└──────────────┘   │   │ ...字段          │   │   │ total_price  │
                   │   └──────────────────┘   │   │ unit_price   │
                   │                          │   │ area         │
                   │   ┌──────────────────┐   │   │ room_count   │
                   │   │  price_history   │   │   │ ...          │
                   │   │──────────────────│   │   │ md5_hash     │
                   │   │ id (PK)          │   │   │ status       │
                   │   │ listing_id (FK)  │◄──┘   │ listing_type │
                   │   │ total_price      │       │ crawl_batch  │
                   │   │ unit_price       │       │ ...时间戳     │
                   │   │ record_date      │       └──────────────┘
                   │   │ created_at       │              │
                   │   └──────────────────┘              │
                   │                                     │
                   │   ┌──────────────────┐              │
                   │   │  crawl_batches   │◄─────────────┘
                   │   │──────────────────│
                   │   │ id (PK)          │
                   │   │ type             │
                   │   │ status           │       ┌──────────────┐
                   │   │ new_listings     │       │ crawl_tasks  │
                   │   │ updated_listings │       │──────────────│
                   │   │ ...汇总字段      │       │ id (PK)      │
                   │   └──────────────────┘       │ batch_id(FK) │
                   │              │               │ district_id  │
                   └──────────────┼───────────────│ status       │
                                  └───────────────│ page_start   │
                                                  │ page_end     │
                                                  └──────────────┘
```

### 4.3 表字段详解

#### districts (区县字典)
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INT PK | 自增主键 |
| name | VARCHAR(50) NOT NULL | 区县名称 |
| pinyin | VARCHAR(100) | 拼音 |
| is_urban | BOOLEAN DEFAULT TRUE | 主城区标识 |
| created_at | DATETIME | 创建时间 |
| **索引** | `idx_districts_name` ON (name) | |

#### communities (小区)
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INT PK | 自增主键 |
| name | VARCHAR(200) NOT NULL | 小区名称 |
| district_id | FK → districts | 所属区县 |
| address | VARCHAR(500) | 地址 |
| lng/lat | NUMERIC(10,7) | 经纬度 |
| 约束 | UNIQUE(name, district_id) | 同区县内小区名唯一 |

#### listings (房源 — 核心表)
| 分类 | 字段 | 类型 | 说明 |
|------|------|------|------|
| 标识 | external_id | VARCHAR(100) UNIQUE | 房源外部 ID (去重键) |
| 价格 | total_price | NUMERIC(12,2) | 总价 (万元) |
| | unit_price | NUMERIC(10,2) | 单价 (元/㎡) |
| 物理 | area | NUMERIC(10,2) | 面积 (㎡) |
| | room/hall/bathroom_count | SMALLINT | 室/厅/卫数量 |
| | floor_level | VARCHAR(20) | 楼层 (低/中/高) |
| | total_floors | SMALLINT | 总楼层 |
| | orientation | VARCHAR(50) | 朝向 |
| | decoration | VARCHAR(50) | 装修 |
| 分类 | listing_type | VARCHAR(20) | regular / court_auction |
| 状态 | status | VARCHAR(20) | active / removed |
| 追踪 | md5_hash | VARCHAR(32) | 内容指纹 (变更检测) |
| | first_seen_at | DATETIME | 首次发现时间 |
| | last_seen_at | DATETIME | 最后发现时间 |
| | last_updated_at | DATETIME | 最后更新时间 |
| **索引** | `idx_listings_district_status` | (district_id, status) | |
| | `idx_listings_community_status` | (community_id, status) | |
| | `idx_listings_unit_price` | (unit_price) | |
| | `idx_listings_last_updated` | (last_updated_at) | |
| | `idx_listings_listing_date` | (listing_date) | |

#### price_history (价格历史)
| 字段 | 类型 | 说明 |
|------|------|------|
| listing_id | FK → listings CASCADE | 关联房源 |
| total_price | NUMERIC(12,2) | 历史总价 |
| unit_price | NUMERIC(10,2) | 历史单价 |
| record_date | DATE NOT NULL | 记录日期 |

#### crawl_batches (爬取批次)
| 字段 | 类型 | 说明 |
|------|------|------|
| type | VARCHAR(20) | "manual" / "incremental" |
| status | VARCHAR(20) | running/completed/failed/stopped |
| total_tasks | INT | 总任务数 |
| completed_tasks | INT | 已完成任务数 |
| new/updated/removed_listings | INT | 统计计数 |

#### crawl_tasks (爬取任务 — 每区县一个)
| 字段 | 类型 | 说明 |
|------|------|------|
| batch_id | FK → crawl_batches CASCADE | 所属批次 |
| district_id | FK → districts SET NULL | 目标区县 |
| page_start/page_end | INT | 页码范围 |
| listings_found | INT | 发现房源数 |

---

## 5. 后端架构

### 5.1 应用入口 ([app/main.py](backend/app/main.py))

```python
# FastAPI 应用 "chongqing-house-data-analysis" v0.2.1
# CORS: localhost:5173/5174/5175
# Lifespan:
#   startup  → resume_incomplete_batches()  # 恢复崩溃批次
#            → 创建 AsyncIOScheduler
#            → run_periodic_update() (6h interval)
#            → setup_trends_scheduler()
#            → 确保索引存在
#   shutdown → scheduler.shutdown()
```

### 5.2 路由树

```
/api/v1/
├── GET  /health                    → 健康检查
├── GET  /districts                 → 区县列表 (含房源计数)
├── GET  /districts/{id}/stats      → 区县统计
├── GET  /listings                  → 房源列表 (多条件筛选+分页)
├── GET  /listings/stats/summary    → 房源汇总统计
├── GET  /listings/{id}             → 房源详情 (含价格历史)
├── GET  /listings/{id}/history     → 价格历史
├── GET  /communities               → 小区列表
├── GET  /communities/{id}          → 小区详情
├── POST /crawl/start               → 启动爬取
├── GET  /crawl/status/{batch_id}   → 查询进度
├── GET  /crawl/status/{batch_id}/stream → SSE 进度推送
├── POST /crawl/stop/{batch_id}     → 停止爬取
├── GET  /crawl/batches             → 历史批次 (最近18个)
├── GET  /analytics/overview        → 概览统计
├── GET  /analytics/district-compare → 区县对比
├── GET  /analytics/price-distribution → 价格分布
├── GET  /analytics/feature-importance → 特征重要性
├── GET  /analytics/clusters        → 聚类画像
├── GET  /analytics/trends          → 价格趋势 (内存缓存)
├── GET  /analytics/trends/status   → 趋势缓存状态
├── POST /analytics/predict         → KNN 价格预测
├── GET  /map/district-prices       → 地图区县均价
├── GET  /map/district-heatmap      → 地图热力图
```

### 5.3 统一响应格式

```json
// 成功
{ "code": 200, "message": "success", "data": {...} }

// 分页
{ "code": 200, "message": "success", "data": {
    "items": [...], "total": 1000, "page": 1, "page_size": 30, "total_pages": 34
}}

// 错误
{ "code": 500, "message": "error description", "data": null }
```

### 5.4 爬虫架构

```
┌─────────────────────────────────────────────────────────────┐
│  爬虫架构                                                    │
│                                                              │
│  用户/定时任务                                                │
│     │                                                        │
│     ▼                                                        │
│  crawl_service.start_crawl()                                │
│     │  - asyncio.Lock 互斥锁                                 │
│     │  - 创建 CrawlBatch DB 记录                             │
│     │  - 创建 CrawlEngine 实例                               │
│     │  - spawn asyncio.Task                                  │
│     ▼                                                        │
│  CrawlEngine.crawl_all()                                    │
│     │  - 加载区县映射表                                      │
│     │  - 构建区县队列 (状态字典)                              │
│     │  - Round-Robin 主循环:                                 │
│     │    ├── 跳过冷却中区县 (paused_until)                   │
│     │    ├── PlaywrightFetcher.fetch_page()                  │
│     │    │   ├── 伪装: 覆盖 navigator.webdriver              │
│     │    │   ├── 地理位置: 重庆 (106.55, 29.57)             │
│     │    │   ├── Viewport: 1920×1080, zh-CN                  │
│     │    │   ├── 重试: 3次指数退避 (2s, 6s, 10s)             │
│     │    │   └── 验证码检测: pattern matching                 │
│     │    ├── ListParser.parse_listing_data()                 │
│     │    │   ├── BeautifulSoup 解析 <dl> 元素                │
│     │    │   ├── 提取14个字段 (价格/面积/户型/朝向等)         │
│     │    │   └── 翻页计算 (正则匹配 max_page)                │
│     │    ├── clean_list_page_data()                          │
│     │    │   ├── 类型转换 (万/元/㎡ → float)                 │
│     │    │   ├── 归一化 (朝向/装修/楼层 映射表)               │
│     │    │   └── 异常值过滤                                   │
│     │    ├── compute_md5() → 变更检测                        │
│     │    ├── DistrictResolver.resolve()                      │
│     │    │   ├── 精确全名匹配                                │
│     │    │   ├── 120+ 别名子串匹配                           │
│     │    │   └── 默认回退: 两江新区                           │
│     │    └── DatabasePipeline.upsert_listing()                │
│     │        ├── 新: INSERT                                  │
│     │        ├── 同MD5: 只更新 last_seen_at                   │
│     │        └── 不同MD5: UPDATE全部+INSERT价格历史           │
│     │                                                        │
│     ▼                                                        │
│  容灾机制:                                                    │
│  - 验证码: 5次打击 → 跳区县 (指数退避 30s→150s)              │
│  - 网络: 3次失败 → 跳区县 (指数退避 30s→120s)               │
│  - 空HTML(<500B): 视为网络错误                                │
│  - DRY检测: 连续3页0条 → 区县完成                             │
│  - 致命异常: 标记 failed 但 finally 继续执行                  │
└─────────────────────────────────────────────────────────────┘
```

### 5.5 爬取服务全局状态管理

```python
# 模块级单例 (app/services/crawl_service.py)
_active_engine: CrawlEngine | None   # 当前活动的爬取引擎
_active_batch_id: int | None         # 当前批次 ID
_active_task: asyncio.Task | None    # 后台异步任务
_crawl_lock = asyncio.Lock()         # 防止并发启动

# SSE: 每2秒轮询 get_crawl_progress()
# 进度查询: 优先内存(引擎), 降级数据库(批次+任务)
# 历史批次: 单次 JOIN 查询 (aggregate district_names + total_pages)
```

### 5.6 数据分析模块

```
┌──────────────────────────────────────────────────────────────┐
│  analytics/stats.py       描述统计 + LRU 缓存                 │
│  ─────────────────────                                         │
│  get_overview_stats():    总览: 均值/中位数/标准差/分布        │
│  get_district_compare():  区县对比: 各区县统计指标             │
│  缓存: OrderedDict LRU (max 50, TTL 60s)                     │
│  分布计算: 单条 CASE WHEN SQL (6档价格/6档面积/6档房龄)       │
├──────────────────────────────────────────────────────────────┤
│  analytics/regression.py  特征重要性分析                       │
│  ─────────────────────                                         │
│  analyze_feature_importance():                               │
│    特征: area/room_count/floor/decoration/orientation...      │
│    管线: ColumnTransformer(StandardScaler+OneHotEncoder)     │
│          + RandomForestRegressor(n=100, depth=15)             │
│    交叉验证: 3-fold R²                                       │
│    重要性聚合: One-Hot → 原始特征求和                          │
│    返回: feature_importance[], r², limitations               │
├──────────────────────────────────────────────────────────────┤
│  analytics/clustering.py  KMeans + PCA 聚类画像               │
│  ─────────────────────                                         │
│  get_clusters():                                              │
│    特征 (纯物理, 不含价格): area/room_count/decoration/...    │
│    K选择: 肘部法则(惯性加速度拐点) + Silhouette(5-8范围)      │
│    降维: PCA → 2D 散点                                        │
│    标签: _auto_label() → "改善型·大户型·高层" 等              │
│    价格是输出变量, 不作为聚类特征                              │
├──────────────────────────────────────────────────────────────┤
│  analytics/trends.py      价格趋势 (内存缓存)                  │
│  ─────────────────────                                         │
│  compute_and_cache():                                         │
│    数据源优先级: price_history > listing_date > first_seen_at │
│    时间范围: 最近 60 天                                        │
│    平滑: SMA-7 (7日简单移动平均)                               │
│    预测: 最后30点线性回归, 限制 ±30%                           │
│    调度: 每日 6:00 AM + 启动后 2s bootstrap                   │
│    缓存: _TREND_CACHE dict + threading.Lock                   │
├──────────────────────────────────────────────────────────────┤
│  analytics/predict.py     KNN 价格预测                         │
│  ─────────────────────                                         │
│  predict_price():                                             │
│    特征: area/rooms/halls + 分类特征 OneHot                   │
│    算法: KNN (K=30, Euclidean)                                │
│    权重: 1/(distance+0.01) 归一化                              │
│    输出: 预测单价+总价 + 置信度(high/medium/low)              │
│    附加: Top-5 相似活跃房源                                    │
│    区县过滤: 仅在 >=100 条时启用                              │
└──────────────────────────────────────────────────────────────┘
```

---

## 6. 前端架构

### 6.1 组件层级

```
<App>
  └── <BrowserRouter>
       └── <AppLayout>
            ├── <Navbar> (导航: 数据获取 / 数据浏览 / 数据分析)
            └── <Routes>
                 ├── "/" → <Navigate to="/crawl">
                 ├── "/crawl" → <CrawlPage>
                 ├── "/storage" → <DataStoragePage>
                 └── "/analysis" → <AnalysisPage>
```

### 6.2 状态管理 (Zustand)

| Store | 状态 | 用途 |
|-------|------|------|
| `useCrawlStore` | activeBatchId, eventSource, progress | 爬取实时状态 + SSE 连接 |
| `useThemeStore` | theme, lang, resolved | 主题 (light/dark) + 语言 (zh/en) |
| `useSettingsStore` | defaultMaxPages, defaultPageSize | 用户偏好设置 |

### 6.3 自定义 Hooks

| Hook | 封装 | 核心功能 |
|------|------|----------|
| `useCrawlProgress` | useCrawlStore | start/stop/reconnect/loadBatches + SSE 生命周期 |
| `useListings` | fetchListings API | 筛选器状态管理 + 分页 + useRef 防闭包过期 |

### 6.4 图表组件 (ECharts)

| 组件 | 底层 | 特性 |
|------|------|------|
| `BarChart` | ECharts bar | 竖向/横向, 响应式, 暗色模式 |
| `LineChart` | ECharts line | 多系列, 虚线预测, SMA 叠加 |
| `PieChart` | ECharts pie | roseType, 暗色模式 |
| `ScatterChart` | ECharts scatter | 聚类着色, 散点大小 |
| `MapChart` | ECharts map + GeoJSON | 重庆区县热力图, roam, visualMap |

### 6.5 API 客户端 ([frontend/src/api/client.ts](frontend/src/api/client.ts))

```typescript
// Axios 实例, baseURL: "/api/v1", timeout: 30s
```

API 模块:
- [analytics.ts](frontend/src/api/analytics.ts): 7 个分析 API 函数
- [crawl.ts](frontend/src/api/crawl.ts): 爬取控制 API (start/stop/status/batches)
- [listings.ts](frontend/src/api/listings.ts): 房源查询 API (过滤参数自动去除空值)

---

## 7. 界面一：数据爬取 (CrawlPage)

> 文件: [frontend/src/pages/CrawlPage.tsx](frontend/src/pages/CrawlPage.tsx)

### 7.1 功能概述

CrawlPage 是**数据爬取控制中心**，提供以下能力:

1. **配置并启动爬取**: 用户设定每区县最大页数 (5–200, step 5) → 点击"开始获取"
2. **实时监控进度**: SSE 推送当前批次/区县/页数/新增房源/更新房源
3. **停止爬取**: 运行中可随时终止
4. **查看历史**: 表格展示最近爬取批次摘要

### 7.2 用户交互流程

```
页面加载
  │
  ▼
reconnect() ─── GET /crawl/batches ─── 获取历史批次
  │                                     │
  │                          是否有 status="running"?
  │                            │               │
  │                           YES             NO
  │                            │               │
  │                    创建 EventSource      显示历史
  │                    重连 SSE 流
  │
用户设定 maxPages (默认100) → 点击 [开始获取]
  │
  ▼
POST /crawl/start { max_pages_per_district: N }
  │
  ▼ 返回 { batch_id, message }
创建 EventSource → GET /crawl/status/{batch_id}/stream
  │
  ▼ SSE 每 2s 推送
┌─────────────────────────────────────────┐
│ { batch_id, status, current_district,   │
│   completed_tasks, new_listings,        │
│   updated_listings, tasks[] }           │
└─────────────────────────────────────────┘
  │
  ▼ 状态流转
"running" ──→ "completed" / "failed" / "stopped"
  │                │
  ▼                ▼
更新进度卡片    自动关闭 SSE → 重新加载历史
```

### 7.3 组件渲染层级

```
CrawlPage
├── 控制面板
│   ├── Input (maxPages: 5–200, step 5)
│   ├── <span> 预计耗时 (maxPages × 5 / 60 分钟)
│   └── Button [开始获取/停止获取] (状态切换)
│       └── Lucide Play / Square 图标
│
├── 实时进度卡片 (progress 存在时渲染)
│   ├── StatCard: 批次 ID
│   ├── StatCard: 当前区县
│   ├── StatCard: 已完成页数
│   ├── StatCard: 新增房源
│   └── StatCard: 更新房源
│
└── 任务历史表格
    ├── <h2> + Spinner (加载中时)
    └── <table> (sticky header)
        ├── 活跃批次行 (高亮 + 橙色"运行中")
        └── 历史批次行 (排除活跃批次)
            ├── 状态标签 (绿=完成, 红=失败, 灰=其他)
            ├── 区县摘要 (最多3个, 其余显示 "...&N个")
            └── 统计: 新增数 / 页数 / 完成时间
```

### 7.4 状态管理细节

| 状态 | 类型 | 来源 | 生命周期 |
|------|------|------|----------|
| maxPages | number | 本地 useState (初始值来自 useSettingsStore) | 页面级 |
| batches | CrawlBatch[] | API + 本地 | 页面级, 历史+活跃合并 |
| historyLoading | boolean | 本地 | API 请求期间 |
| loaded | useRef | 本地 | 确保首次挂载只加载一次 |
| prevRunning | useRef | 本地 | 检测 running→stopped 转换 |
| activeBatchId | number\|null | useCrawlStore | 全局 |
| progress | CrawlProgress\|null | useCrawlStore (SSE 更新) | 全局 |
| isRunning | boolean | useCrawlProgress (派生) | 全局 |

### 7.5 边界场景处理

| 场景 | 处理方式 |
|------|----------|
| 页面刷新时爬取正在运行 | `reconnect()` 检测 running 批次 → 重建 SSE |
| SSE 连接中断 | EventSource 自动重连; `es.onerror` 仅在 CLOSED 时触发 onComplete |
| SSE 推送错误事件 | `data.error` 存在 → 立即关闭连接 |
| 爬取完成 | `prevRunning` ref 检测 true→false → 自动重新加载历史 |
| 多次点击开始 | `asyncio.Lock` 后端互斥 + 前端按钮切换为"停止" |
| 活跃批次去重 | 历史列表中过滤掉当前活跃批次 |
| 区县名过长 | 超过3个区县时折叠显示 "… &N个区县" |

---

## 8. 界面二：数据浏览 (DataStoragePage)

> 文件: [frontend/src/pages/DataStoragePage.tsx](frontend/src/pages/DataStoragePage.tsx)

### 8.1 功能概述

DataStoragePage 是**房源数据浏览器**，提供:

1. **分页表格浏览**: 所有爬取房源的列表展示
2. **多维度筛选**: 12 个筛选条件 (区县/装修/朝向/户型/类型/价格区间/面积区间/关键词)
3. **列排序**: 点击 total_price / unit_price / area 表头排序
4. **重置/刷新**: 一键清空筛选 + 手动刷新数据

### 8.2 筛选器布局

```
┌──────────────────────────────────────────────────────────────────┐
│  Row 1:                                                          │
│  [区县▼] [装修▼] [朝向▼] [户型▼] [类型▼] [单价: min ___ max ___] │
│  [⇅排序] [重置] [刷新]                                            │
├──────────────────────────────────────────────────────────────────┤
│  Row 2:                                                          │
│  [总价: min ___ max ___] [面积: min ___ max ___] [关键词: _____]  │
└──────────────────────────────────────────────────────────────────┘
```

### 8.3 表格列定义

| 列 | 数据字段 | 渲染 | 排序 |
|----|----------|------|------|
| # | (计算) | `(page-1)*pageSize + idx + 1` | — |
| 标题 | title | truncate 180px + 法拍徽章 | — |
| 小区 | community_name | 文本 | — |
| 总价 | total_price | `${price}万` | ✅ (点击切换) |
| 单价 | unit_price | `toLocaleString()` | ✅ |
| 面积 | area | `${area}㎡` | ✅ |
| 户型 | room/hall/bath | 拼接 (如"3室2厅1卫") | — |
| 楼层 | floor_level | 低/中/高 | — |
| 朝向 | orientation | 文本 | — |
| 装修 | decoration | 文本 | — |
| 状态 | status | 文本 | — |

### 8.4 useListings Hook 核心逻辑

```typescript
function useListings(initialFilters: ListingFilter) {
  const [data, setData] = useState<Listing[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [filters, setFilters] = useState<ListingFilter>(initialFilters)
  const filtersRef = useRef(filters)  // 防闭包过期

  // 筛选变更 → 重置 page=1 → 触发 API
  const updateFilter = (key, value) => {
    setFilters(prev => {
      const next = { ...prev, [key]: value, page: 1 }  // ← page 归 1
      filtersRef.current = next
      load(next)
      return next
    })
  }

  // 分页变更 → 只改 page → 触发 API
  const setPage = (page: number) => {
    setFilters(prev => {
      const next = { ...prev, page }
      filtersRef.current = next
      load(next)
      return next
    })
  }

  // 初次加载 + 路由变化时刷新
  useEffect(() => { load(filters) }, [])
  useEffect(() => { reload() }, [location.pathname])
}
```

### 8.5 API 调用策略

```
fetchListings(filters)
  │
  ├── 过滤空值: 去除 undefined/null/"" 的参数
  ├── request: GET /listings?district_id=1&page=1&page_size=30&...
  │
  └── response: APIResponse<PaginatedResponse<Listing>>
       └── 提取 resp.data.data
            ├── items: Listing[]
            ├── total: 1000
            ├── page: 1
            ├── page_size: 30
            └── total_pages: 34
```

### 8.6 边界场景处理

| 场景 | 处理方式 |
|------|----------|
| 数据为空 | Table emptyText: "暂无数据, 请先执行数据获取任务" |
| 加载中 | Table 居中显示 "加载中..." |
| 所有列值为 null | 每列渲染器检查 null → 显示 "-" |
| totalPages 为 0 | `Math.max(1, Math.ceil(total / pageSize))` 防止除零 |
| 首页/末页按钮 | disabled 在边界位置 |
| 总记录 ≤ 单页 | 简化信息栏 "共 N 条" (不显示完整分页) |
| 筛选修改时 | page 自动归 1, 立即触发 API 请求 |
| filter 闭包过期 | `filtersRef` 始终持有最新 filter 引用 |
| 语言切换 | 选项 label 依赖 `lang` 通过 useMemo 自动重算 |

---

## 9. 界面三：数据分析 (AnalysisPage)

> 文件: [frontend/src/pages/AnalysisPage.tsx](frontend/src/pages/AnalysisPage.tsx)

### 9.1 功能概述

AnalysisPage 是**数据分析仪表盘**，7 个分析 Tab + 1 个全局开关:

```
┌────────────────────────────────────────────────────────────────┐
│  [总览] [地图] [区县对比] [因素分析] [聚类画像] [趋势] [预测]  │
│                                          □ 含法拍房源          │
├────────────────────────────────────────────────────────────────┤
│                         Tab 内容区                              │
└────────────────────────────────────────────────────────────────┘
```

### 9.2 七个 Tab 逐个解析

---

#### Tab 1: 总览 (Overview)

```
┌──────────┬──────────┬──────────┬──────────┬──────────┬──────────┐
│ 总房源数  │ 均价(万) │ 中位价    │ 单价(元/㎡)│ 均面积    │ 标准差    │
└──────────┴──────────┴──────────┴──────────┴──────────┴──────────┘
┌─────────────────────┐  ┌──────────────┐  ┌──────────────────────┐
│ 城区/郊区 对比条     │  │ 装修分布饼图  │  │ 区县排名 (Top15横柱) │
└─────────────────────┘  └──────────────┘  └──────────────────────┘
┌─────────────────────────────────────────┐
│ 价格分布柱状图 (6档: <50→300+万)         │
└─────────────────────────────────────────┘
```

- **数据源**: `GET /analytics/overview` + `GET /analytics/district-compare`
- **加载策略**: `Promise.all` 并行请求
- **缓存**: 后端 LRU (60s TTL, 50 entries)
- **含法拍开关**: `include_court_auction` query param (默认 false)

---

#### Tab 2: 地图 (Map)

```
┌─────────────────────────────────────────────────────┐
│  [总房源] [均价] [最高] [最低]   4 个 MiniStat       │
├─────────────────────────────────────────────────────┤
│                                                     │
│           重庆区县地图 (ECharts Map)                  │
│           颜色深浅 = 均价高低                         │
│           zoom/pan + visualMap slider               │
│                                                     │
└─────────────────────────────────────────────────────┘
```

- **数据源**: `GET /map/district-prices` (后端 GROUP BY district, AVG unit_price)
- **GeoJSON**: `public/chongqing.json` (前端异步加载)
- **渲染**: ECharts `map` + `visualMap` (连续色阶) + `emphasis` (hover 高亮)
- **加载态**: GeoJSON 加载前显示 Spinner; 失败仍渲染空白地图区域

---

#### Tab 3: 区县对比 (Districts)

```
┌─────────────────────────────────────────┐
│         区县均价柱状图 (竖向)              │
│         所有区县按均价降序                │
├─────────────────────────────────────────┤
│ 区县     │ 均价    │ 中位数  │ 标准差    │
│ 两江新区  │ 15800  │ 15200  │ 3200     │
│ 渝中区    │ 14200  │ 13800  │ 2800     │
│ ...      │ ...    │ ...    │ ...      │
└─────────────────────────────────────────┘
```

- **数据源**: `GET /analytics/district-compare`
- **与 Overview 共享加载** (Promise.all 同批次)

---

#### Tab 4: 因素分析 (Factors)

```
┌──────────────┬──────────────┐
│ 样本量: 1234 │ R²: 0.723    │
└──────────────┴──────────────┘
┌──────────────────────────────────────┐
│     特征重要性 (横向柱状图)            │
│     面积     ████████████  32%        │
│     装修     ██████        18%        │
│     朝向     ████          12%        │
│     ...                              │
└──────────────────────────────────────┘
┌──────────────────────────────────────┐
│  ⚠ 模型局限性: 缺少学区/地铁/楼层系数  │
└──────────────────────────────────────┘
```

- **数据源**: `GET /analytics/feature-importance`
- **算法**: RandomForestRegressor (100 trees, depth 15)
- **特征映射**: `FEATURE_LABEL_MAP` 英文 key → 中文标签
- **One-Hot 聚合**: 分类特征一热编码后的多个重要性求和回原始特征

---

#### Tab 5: 聚类画像 (Clusters)

```
┌──────────────┬──────────────┬──────────────┬──────────────┐
│ 改善型·大户型 │ 刚需型·小户型 │ 品质型·中户型 │ 豪宅型·大户型 │
│ 高层          │ 高层          │ 多层          │ 高层          │
│ 123套  ¥15800│ 456套  ¥9800 │ 234套  ¥12500│ 89套   ¥22000│
│ 均126㎡       │ 均62㎡        │ 均95㎡        │ 均185㎡       │
└──────────────┴──────────────┴──────────────┴──────────────┘
┌─────────────────────────────────────────────────────────┐
│              PCA 2D 散点图 (聚类着色)                      │
└─────────────────────────────────────────────────────────┘
PCA 方差解释率: PC1 XX%, PC2 XX%  |  K=5 (自动选择)
```

- **数据源**: `GET /analytics/clusters`
- **聚类特征 (纯物理)**: area, room_count, decoration_code, total_floors, listing_age_days
- **价格排除原因**: 避免循环论证 — 价格是输出标签而非输入特征
- **K 自动选择**: 肘部法则 + Silhouette Score (K=5–8)
- **标签生成**: `_auto_label()` → 价格档位 × 户型档位 × 楼层类型
- **PCA 2D**: 仅用于可视化, 聚类在高维原始空间进行

---

#### Tab 6: 价格趋势 (Trends)

```
┌─────────────────────────────────────┐
│  🔮 明日预测: ¥15,200/㎡            │
│  基于最近30天线性回归, 范围±30%      │
└─────────────────────────────────────┘
┌─────────────────────────────────────────┐
│    价格趋势折线图                         │
│    ─ 实线: 实际日均价                    │
│    - - 虚线: SMA-7 (7日移动平均)        │
│    ··· 点线: 明日预测点                  │
│    时间跨度: 最近 60 天                  │
└─────────────────────────────────────────┘
┌──────────────────────────────────────┐
│ 日期       │ 均价    │ SMA-7  │ 来源  │
│ 2026-07-01 │ 15800  │ 15600  │ price_history│
│ ...                                  │
└──────────────────────────────────────┘
数据来源: price_history (优先) / listing_date / first_seen_at
```

- **数据源**: `GET /analytics/trends` (内存缓存, 零数据库查询)
- **预测算法**: 最后 30 天线性回归 → 外推 1 天 → clamp ±30%
- **缓存调度**: 每日 6:00 AM 计算 + 启动后 2s bootstrap
- **来源标注**: price_history / listings / first_seen_at / none

---

#### Tab 7: 价格预测 (Predict)

```
┌──────────────────────────────────────────┐
│  预测表单                                   │
│  [区县▼] [面积: ──●── 150㎡]               │
│  [户型: 3室 2厅] [楼层▼] [朝向▼] [装修▼]   │
│  [开始预测] (带 Spinner 的按钮)             │
├──────────────────────────────────────────┤
│  预测结果 (result 非空时显示)              │
│  ┌──────────────┬──────────────┐          │
│  │ 预测单价       │ 预测总价       │          │
│  │ ¥15,200/㎡     │ ¥228万        │          │
│  │ [高置信度]     │               │          │
│  └──────────────┴──────────────┘          │
│  基于 1234 条活跃房源, K=30                │
├──────────────────────────────────────────┤
│  相似房源卡片 (Top 5, 可点击跳转)          │
│  [小区名] [总价] [户型] [朝向] [装修]      │
└──────────────────────────────────────────┘
```

- **数据源**: `POST /analytics/predict` (KNN 加权估值)
- **交互**: 面积滑块 30–300㎡ (step 5, 实时数值显示)
- **置信度**: high (距离小+偏差小) / medium / low (红/黄/绿)
- **相似房源**: 点击卡片跳转 `source_url` (fang.com) 新标签页
- **错误处理**: try/catch → 红色错误横幅, 表单保留 (可重试)

### 9.3 状态管理

| 状态 | 类型 | 说明 |
|------|------|------|
| tab | Tab (string union) | 当前选中 Tab (默认 "overview") |
| overview | OverviewStats\|null | 概览数据 (与 compare 共享加载) |
| compare | DistrictCompareItem[] | 区县对比数据 |
| importance | FeatureImportance\|null | 特征重要性 |
| cluster | ClusterResult\|null | 聚类结果 |
| trends | PriceTrends\|null | 趋势数据 |
| mapData | MapPriceItem[] | 地图数据 |
| loading | boolean | 全局 loading (Tab 切换粒度) |
| includeAuction | boolean | 是否含法拍 (默认 false) |
| form (PredictTab) | PredictRequest | 预测表单值 |
| result (PredictTab) | PredictResponse\|null | 预测结果 |

### 9.4 图表色泽系统

所有图表共享统一的 Shopify 风格色板:

```typescript
const colors = [
  '#1e2c31', '#3d5a62', '#6b838a', '#9dabad', '#bdbdca',
  '#d4a76a', '#e8c48a', '#f2dba8', '#c4a882', '#8c7a6b'
]
```

暗色/亮色模式通过 `useThemeStore.resolved` 自动切换轴线/网格/提示框/背景色。

### 9.5 边界场景处理

| 场景 | 处理方式 |
|------|----------|
| 数据库为空 | 每个 Tab 检查 null/[] → EmptyHint (琥珀色提示框) |
| 预测失败 | try/catch → 红色错误横幅 + 表单保留 |
| 趋势缓存未就绪 | `get_cached_trends()` 返回 status_note + 空数据 |
| 趋势数据不足 | `hasPrediction` 需要 items≥3 + 有效 predicted_price |
| GeoJSON 加载失败 | `cancelled` flag 防止卸载后 setState → 仍渲染地图区 |
| Cluster 无数据 | PCA 方差回退显示 "0.0%" |
| 特征名无映射 | 显示原始英文名 (英文模式) / 回退中文映射 |
| 0 值数据 | 均值为 0 是合法值 (与 null 区分) |
| 路由返回刷新 | `useEffect([location.pathname])` 确保数据新鲜 |
| Tab+开关双重触发 | `useEffect([tab, includeAuction])` 统一管理 |

---

## 10. 数据流与系统交互

### 10.1 请求生命周期

```
┌──────────────────────────────────────────────────────────────┐
│  典型 API 请求生命周期                                         │
│                                                               │
│  前端                             后端                         │
│  ────                             ────                        │
│  fetchOverview(districtId)        @router.get("/overview")   │
│    │                                │                         │
│    │  GET /api/v1/analytics/       │  try:                   │
│    │    overview?district_id=1     │    db = get_db()        │
│    │                                │    result = await       │
│    │                                │      get_overview_stats │
│    │                                │      (db, district_id)  │
│    │                                │    return ok(data=...) │
│    │                                │  except Exception:     │
│    │                                │    return error(...)   │
│    │  ◄───────────────────────────  │                         │
│    │  APIResponse<OverviewStats>    │                         │
│    │                                │                         │
│  check resp.data.code === 200      │                         │
│    │                                │                         │
│  setOverview(resp.data.data)       │                         │
│    │                                │                         │
│  render Charts                    │                         │
└──────────────────────────────────────────────────────────────┘
```

### 10.2 SSE 实时推送流程

```
┌──────────────────────────────────────────────────────────────┐
│  SSE (Server-Sent Events) 爬取进度推送                         │
│                                                               │
│  前端                                 后端                     │
│  ────                                 ────                    │
│  new EventSource(                      @router.get(           │
│    "/api/v1/crawl/status/              "/crawl/status/        │
│     {id}/stream"                       {batch_id}/stream")    │
│  )                                      │                     │
│    │                                    │ StreamingResponse(  │
│    │                                    │   generate_sse())   │
│    │                                    │   │                 │
│    │                                    │   while True:       │
│    │                                    │     progress =      │
│    │                                    │       get_crawl_    │
│    │                                    │       progress()    │
│    │                                    │     yield f"data:   │
│    │                                    │       {json}\n\n"   │
│    │                                    │     await asyncio   │
│    │                                    │       .sleep(2)     │
│    │                                    │     if status in    │
│    │                                    │       terminal:     │
│    │                                    │       break         │
│    │                                    │                     │
│  es.onmessage = (e) =>                 │                     │
│    progress = JSON.parse(e.data)       │                     │
│    store.updateProgress(progress)      │                     │
│    if terminal: es.close()             │                     │
│    if error: es.close()                │                     │
└──────────────────────────────────────────────────────────────┘
```

---

## 11. 定时任务与运维

### 11.1 任务矩阵

| 任务 | 调度方式 | 频率 | 功能 |
|------|----------|------|------|
| `run_periodic_update` | APScheduler IntervalTrigger | 每 6 小时 | 房龄刷新 + 增量爬取 + 趋势缓存 |
| `run_daily_listing_age_update` | 作为 periodic 子任务 | 每 6 小时 | SQL 批量更新 listing_age_days |
| `run_weekly_incremental_crawl` | 作为 periodic 子任务 | 每 6 小时 | 增量爬取 (最多 2 页/区县) |
| `compute_and_cache` | 作为 periodic 子任务 | 每 6 小时 | 价格趋势缓存刷新 |
| `trends_scheduler` | CronTrigger | 每日 6:00 AM | 独立趋势计算 |
| `trends_bootstrap` | DateTrigger | 启动后 2s | 首次趋势计算 |
| `resume_incomplete_batches` | 启动时 | 一次 | 标记 running→stopped 崩溃批次 |

### 11.2 增量爬取逻辑

```
run_weekly_incremental_crawl()
  │
  ├── 检查是否有手动爬取运行中 (互斥)
  ├── 检查是否有未完成的增量批次
  │   ├── running → 不重复启动
  │   ├── pending/stopped → 恢复运行
  │   └── 无 → 创建新批次 (max_pages=2)
  │
  └── 启动 CrawlEngine
```

### 11.3 启动流程

```
start.py / start.bat
  │
  ├── 检查 Python 3.12+ 和 Node.js 18+
  ├── 首次运行: python seed_data.py (初始化 37 区县)
  ├── 检查前端 npm 依赖 (npm install if needed)
  │
  ├── 子进程 1: uvicorn app.main:app --host 127.0.0.1 --port 8000
  └── 子进程 2: npm run dev (Vite on :5173, proxy /api → :8000)
```

---

## 12. 测试体系

### 12.1 测试结构

```
backend/tests/
├── conftest.py              # async DB session + TestClient fixtures
├── test_crawl_safety.py     # 爬取安全/鲁棒性
├── test_data_integrity.py   # 数据完整性
├── test_data_pollution.py   # 数据防污染
├── test_dedup.py            # MD5 去重逻辑
├── test_cleaner.py          # 数据清洗单元测试
├── test_api_integration.py  # API 集成测试
└── test_district_mapping.py # 区县映射验证
```

- **总测试数**: 99 个 (全部通过)
- **框架**: pytest 8.2.2 + pytest-asyncio 0.23.7
- **Fixture 模式**: 异步测试数据库 + FastAPI TestClient

---

## 附录 A: 关键技术决策

| 决策 | 选择 | 原因 |
|------|------|------|
| 数据库 | SQLite (非 PostgreSQL) | 零运维, WAL 模式满足并发读需求 |
| ORM | SQLAlchemy async | 与 FastAPI 异步模型一致 |
| 状态管理 | Zustand (非 Redux) | 轻量, 适合中小型 SPA |
| 爬虫渲染 | Playwright (非 requests) | 目标站点需要 JS 渲染 |
| 图表 | ECharts (非 Recharts/D3) | 内置地图支持, 中文生态好 |
| 容器化 | 无 Docker | 个人项目, 本地直接运行 |
| 国际化 | react-i18next | 成熟稳定的 i18n 方案 |
| CSS | Tailwind v4 | 原子化, 开发效率高 |

## 附录 B: 系统限制与改进方向

| 限制 | 影响 | 改进方向 |
|------|------|----------|
| SQLite 单写锁 | 高并发写入阻塞 | PostgreSQL / MySQL 迁移 |
| 无容器化 | 环境依赖手动管理 | Docker Compose 编排 |
| 爬虫无分布式 | 大范围爬取受单机限制 | Scrapy + Redis 分布式 |
| 趋势缓存进程内 | 重启丢失, 需 bootstrap | 引入 Redis 持久化 |
| 前端无虚拟滚动 | 大量房源列表性能 | react-window / tanstack virtual |
| 无认证授权 | 任何人可触发爬取 | JWT + RBAC |
| 特征局限性 | 缺少学区/地铁等关键变量 | 接入第三方数据源 |
| 无 CI/CD | 手动测试/部署 | GitHub Actions |

---

> **文档生成方式**: 通过 3 个并行分析 Agent (项目结构 + 前端页面 + 后端代码) 深度阅读全部源文件后, 交叉验证合成。
> **分析范围**: 后端 50+ 源文件, 前端 30+ 源文件, 总计 ~168K tokens 分析量。
