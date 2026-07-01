# 重庆二手房数据分析系统

> 数据源: fang.com · 零配置启动 · asyncio 异步并发 · 全栈 TypeScript + Python

基于房天下挂牌数据的重庆市二手房价格分析平台，支持**爬虫采集 → 数据浏览 → 多维分析 → 价格预测**全链路。

---

## 功能模块

### 数据采集
- 异步并发爬虫 (httpx + asyncio)，覆盖重庆 **31 个有数据的区县**
- 列表页解析 + 详情页解析，MD5 去重，数据清洗 (异常值/标准化)
- 前端控制台：一键启动/停止爬取，SSE 实时进度推送
- 定时增量更新 + 断点恢复，进程重启自动续传

### 数据浏览
- 多条件筛选：区县、户型、装修、朝向、**总价区间、单价区间**、面积区间
- 关键词搜索，字段排序，分页浏览
- 1721 条活跃挂牌数据 (85% 主城 + 15% 郊区)

### 数据分析 (6 个 Tab)
| Tab | 内容 |
|-----|------|
| **总览** | 全市均价/中位数/标准差、价格/面积/房龄/户型/装修分布、区县排名、**主城/郊区分组均价** |
| **地图** | ECharts 重庆地图着色 (各区均价热力图 + 房源密度) |
| **区县对比** | 各区县均价/中位数/标准差对比表 + 柱状图 |
| **因素分析** | RandomForest 特征重要性排序 (面积→区县→装修…) + 交叉验证 R² |
| **聚类画像** | KMeans 聚类 (肘部法则自动选 K) → PCA 2D 散点图，物理属性画像 |
| **价格趋势** | 日级均价折线 + SMA-7 均线 + **次日价格预测 (线性回归)** |
| **价格预测** | KNN 加权平均估值 + Top 5 相似房源推荐 + 置信度评级 |

### 后台任务
- 爬虫：每 6 小时增量爬取 + 每日 listing_age_days 刷新
- 趋势：每日 06:00 自动计算趋势快照，启动时 > 6 点则 5 分钟后补算

---

## 技术栈

| 层 | 技术 |
|---|---|
| 后端框架 | FastAPI (Python 3.12) + uvicorn |
| 数据库 | SQLite (WAL mode) + aiosqlite + SQLAlchemy 2.0 async |
| 爬虫 | httpx + BeautifulSoup4 + lxml + tenacity 指数退避 |
| 定时任务 | APScheduler (进程内 Cron + Interval) |
| 数据分析 | pandas + numpy + scikit-learn (RandomForest / KMeans / PCA / LinearRegression) |
| 前端框架 | React 19 + TypeScript + Vite 8 |
| 样式 | Tailwind CSS v4 |
| 图表 | ECharts 6 (bar / pie / line / scatter / map) |
| 状态管理 | Zustand 5 |
| 国际化 | react-i18next (中文 / English) |
| HTTP 客户端 | axios |

---

## 快速开始

### 环境要求

- Python 3.12+
- Node.js 20+

### 1. 后端

```bash
cd backend

# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 初始化数据库 + 区县种子数据
python seed_data.py

# 启动服务 (http://localhost:8000)
uvicorn app.main:app --reload
```

API 文档: `http://localhost:8000/docs`

### 2. 前端

```bash
cd frontend
npm install
npm run dev    # http://localhost:5173
```

Vite 开发服务器自动代理 `/api` → `http://127.0.0.1:8000`。

### 3. 爬虫 CLI

```bash
cd backend

# 全量爬取 (所有区县)
python -m crawler crawl --max-pages 10

# 增量爬取 (每区县 1-2 页)
python -m crawler crawl --type incremental

# 查看爬取状态
python -m crawler status
```

也可以在 Web UI (`/crawl` 页面) 中一键操作。

---

## 项目结构

```
data_web/
├── backend/
│   ├── app/                          # FastAPI 应用
│   │   ├── main.py                   # 入口: lifespan + CORS + 定时任务注册
│   │   ├── config.py                 # 配置 (数据库路径自动计算)
│   │   ├── database.py               # SQLAlchemy async engine + session
│   │   ├── models/                   # ORM 模型
│   │   │   ├── listing.py            # 房源 (30+ 字段, 6 索引)
│   │   │   ├── district.py           # 区县 (38 个)
│   │   │   ├── community.py          # 小区
│   │   │   ├── price_history.py      # 价格历史
│   │   │   └── crawl.py              # 爬取批次/任务
│   │   ├── schemas/                  # Pydantic 模型
│   │   │   ├── listing.py            # 房源列表/详情/筛选/汇总
│   │   │   ├── analytics.py          # 6 大分析模块响应
│   │   │   ├── crawl.py              # 爬取请求/进度
│   │   │   ├── district.py           # 区县
│   │   │   ├── community.py          # 小区
│   │   │   └── common.py             # 通用分页响应
│   │   ├── api/v1/                   # REST 端点
│   │   │   ├── analytics.py          # 7 个分析端点
│   │   │   ├── listings.py           # 房源 CRUD + 筛选分页
│   │   │   ├── crawl.py              # 爬取控制 + SSE 流
│   │   │   ├── map_data.py           # 地图数据
│   │   │   ├── districts.py          # 区县
│   │   │   ├── communities.py        # 小区
│   │   │   └── health.py             # 健康检查
│   │   ├── services/                 # 业务逻辑
│   │   │   ├── listing_service.py    # 查询构建 + 汇总统计
│   │   │   └── crawl_service.py      # 爬取流程编排
│   │   ├── utils/response.py         # ok() / error() 响应封装
│   │   └── api/deps.py               # 依赖注入 (get_db)
│   ├── crawler/                      # 爬虫引擎
│   │   ├── engine.py                 # 异步引擎 (Semaphore 并发控制)
│   │   ├── fetcher.py                # HTTP 客户端 (UA 轮换, 指数退避)
│   │   ├── playwright_fetcher.py     # Playwright 备选渲染
│   │   ├── parsers/
│   │   │   ├── list_parser.py        # 列表页 HTML 解析
│   │   │   └── detail_parser.py      # 详情页 HTML 解析
│   │   ├── cleaner.py                # 数据清洗 (异常值过滤/类型转换)
│   │   ├── dedup.py                  # MD5 去重 + 社区名模糊匹配
│   │   ├── pipelines.py              # DB 写入管线 (批量 upsert)
│   │   ├── constants.py              # 区县配置 + UA 池 + 速率限制
│   │   ├── district_resolver.py      # 区县归属推断
│   │   └── __main__.py               # CLI 入口
│   ├── analytics/                    # 数据分析模块
│   │   ├── stats.py                  # 描述统计 + 分布 + LRU 缓存
│   │   ├── trends.py                 # 日级趋势 + SMA-7 + 预测 (定时缓存)
│   │   ├── regression.py             # RandomForest 特征重要性
│   │   ├── clustering.py             # KMeans 聚类 + PCA (肘部法则)
│   │   └── predict.py                # KNN 加权估值 + 相似房源
│   ├── scheduler/
│   │   └── jobs.py                   # 增量爬取 + 龄期刷新
│   ├── tests/                        # 91 tests (pytest)
│   ├── seed_data.py                  # 初始化 38 区县
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── CrawlPage.tsx          # 爬取控制台 (启动/停止/进度)
│   │   │   ├── DataStoragePage.tsx    # 房源浏览 (筛选+排序+分页)
│   │   │   └── AnalysisPage.tsx       # 分析面板 (7 Tab)
│   │   ├── components/
│   │   │   ├── charts/               # BarChart / PieChart / LineChart / ScatterChart / MapChart
│   │   │   ├── layout/               # AppLayout + Navbar
│   │   │   └── ui/                   # Button / Select / Input / Table / Spinner / Chip
│   │   ├── stores/                   # useThemeStore / useCrawlStore / useSettingsStore
│   │   ├── hooks/                    # useListings / useCrawlProgress
│   │   ├── api/                      # analytics / crawl / listings / client
│   │   ├── i18n/                     # zh.json / en.json
│   │   ├── types/                    # TypeScript 公用类型
│   │   └── constants/                # 区县常量
│   └── public/
│       └── chongqing.json            # GeoJSON 重庆地图
└── README.md
```

---

## API 总览

### 通用
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/health` | 健康检查 |

### 房源
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/listings` | 列表 (区县/总价/单价/面积/户型/装修/朝向/关键词 + 排序分页) |
| GET | `/api/v1/listings/{id}` | 详情 (含价格历史) |
| GET | `/api/v1/listings/{id}/history` | 价格变动历史 |
| GET | `/api/v1/listings/stats/summary` | 汇总统计 (均价/中位数/价格段) |

### 区县 & 小区
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/districts` | 区县列表 |
| GET | `/api/v1/districts/{id}` | 区县详情 + 统计 |
| GET | `/api/v1/communities` | 小区列表 |
| GET | `/api/v1/communities/{id}` | 小区详情 + 房源 |

### 爬取控制
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/crawl/start` | 启动爬取 |
| GET | `/api/v1/crawl/status/{batch_id}` | 进度查询 |
| GET | `/api/v1/crawl/status/{batch_id}/stream` | SSE 实时进度 |
| POST | `/api/v1/crawl/stop/{batch_id}` | 停止爬取 |
| GET | `/api/v1/crawl/batches` | 历史批次 |

### 数据分析
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/analytics/overview` | 市场概览 (均价/分布/区县排名/主城vs郊区) |
| GET | `/api/v1/analytics/district-compare` | 区县对比 (均价/中位数/标准差) |
| GET | `/api/v1/analytics/price-distribution` | 价格/面积/龄期分布 |
| GET | `/api/v1/analytics/feature-importance` | RandomForest 特征重要性 |
| GET | `/api/v1/analytics/clusters` | KMeans 聚类画像 + PCA 散点 |
| GET | `/api/v1/analytics/trends` | 日级趋势 + SMA-7 + 次日预测 (定时缓存) |
| POST | `/api/v1/analytics/predict` | KNN 价格预估 + 相似房源 |

### 地图
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/map/district-prices` | 各区均价 (地图着色) |
| GET | `/api/v1/map/district-heatmap` | 房源密度热力 |

---

## 架构决策

### SQLite 而非 MySQL/PostgreSQL
- **零配置**: 无需安装外部数据库，`pip install` 后即用
- **WAL 模式**: 读写并发不互斥，3 协程爬虫足够
- **单机场景**: 非商业化项目，数据量 ~2000 条 × 30 字段 ≈ 3MB
- **可移植**: 单个 `.db` 文件即完整数据库

### APScheduler 而非 Celery
- **进程内调度**: 4 个定时任务（爬虫/龄期/趋势），无需消息队列
- **零运维**: 无 Redis/Broker 依赖
- **asyncio 原生**: 与 FastAPI 共享事件循环

### fang.com 桌面站
- **SSR 渲染**: HTML 源码包含全部数据，无需 JS 执行
- **无反爬**: 区县列表页无滑块/验证码
- **覆盖 31/38 区县**: 7 个区县在 fang.com 无独立频道

### 并发控制
- 列表页 1 并发 + 详情页 3 并发 (Semaphore 限流)
- SQLite 写操作共用 asyncio.Lock 串行化
- tenacity 指数退避重试 (429/403)

---

## 数据说明

- 数据来源为 **fang.com 挂牌房源**，主城区占比约 85%，郊区样本稀疏
- 全局均价为房源数加权平均，偏向主城区价格水平
- 价格预测基于近 30 日线性回归外推，约束 ±30%，仅供参考
- 特征重要性模型的 R² 通常 < 0.6，定位是因素排序而非精准估值

---

## 许可证

MIT
