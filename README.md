# 重庆二手房数据分析系统

> 数据源: fang.com · 零配置启动 · Playwright 浏览器渲染 · 全栈 TypeScript + Python

基于房天下挂牌数据的重庆市二手房价格分析平台，支持**爬虫采集 → 数据浏览 → 多维分析 → 价格预测**全链路。

完整架构文档请参阅 [ARCHITECTURE.md](ARCHITECTURE.md)。

---

## 功能模块

### 数据采集
- Playwright 无头浏览器渲染 (Chromium Edge)，覆盖重庆 **37 个区县**
- 列表页自适应 HTML 解析 (BeautifulSoup)，MD5 去重 + 增量变更检测
- 前端控制台：一键启动/停止爬取，SSE 实时进度推送
- Round-Robin 区县调度 + 验证码自动退避 + 网络异常重试
- 定时增量更新 (每 6 小时) + 崩溃批次自动恢复

### 数据浏览
- 多条件筛选：区县、户型、装修、朝向、总价区间、单价区间、面积区间、关键词
- 列排序 (总价 / 单价 / 面积)，分页浏览
- 法拍房源特殊标记，中/英双语界面

### 数据分析 (7 个 Tab)
| Tab | 内容 |
|-----|------|
| **总览** | 全市均价/中位数/标准差、价格/面积/房龄/户型/装修分布、区县排名、主城/郊区分组均价 |
| **地图** | ECharts 重庆地图着色 (各区均价热力图 + 房源密度) |
| **区县对比** | 各区县均价/中位数/标准差对比表 + 柱状图 |
| **因素分析** | RandomForest 特征重要性排序 + 3-fold 交叉验证 R² + 模型局限性说明 |
| **聚类画像** | KMeans 聚类 (肘部法则 + Silhouette 自动选 K) → PCA 2D 散点图, 纯物理属性画像 |
| **价格趋势** | 日级均价折线 + SMA-7 均线 + 次日价格预测 (线性回归) |
| **价格预测** | KNN (K=30) 加权平均估值 + Top 5 相似房源推荐 + 置信度评级 (高/中/低) |

### 后台任务
- 爬虫：每 6 小时增量爬取 + 每日 listing_age_days SQL 批量刷新
- 趋势：每日 06:00 自动计算趋势快照，启动时 2s 后 bootstrap 首次计算

---

## 技术栈

| 层 | 技术 |
|---|---|
| 后端框架 | FastAPI 0.111 (Python 3.12) + uvicorn 0.30 |
| 数据库 | SQLite (WAL mode) + aiosqlite 0.20 + SQLAlchemy 2.0 async |
| 爬虫 | Playwright ≥1.45 + BeautifulSoup4 4.12 + lxml 5.2 + tenacity 8.5 |
| 定时任务 | APScheduler 3.10 (进程内 Cron + Interval) |
| 数据分析 | pandas 2.2 + numpy 1.26 + scikit-learn 1.5 (RandomForest / KMeans / PCA / KNN) |
| 前端框架 | React 19 + TypeScript 6 + Vite 8 |
| 样式 | Tailwind CSS v4 |
| 图表 | ECharts 6 (bar / pie / line / scatter / map) |
| 状态管理 | Zustand 5 |
| 路由 | react-router-dom 7 |
| 国际化 | react-i18next 17 + i18next 26 (中文 / English) |
| HTTP 客户端 | axios |

---

## 快速开始

### 环境要求

- Python 3.12+
- Node.js 20+
- Microsoft Edge 浏览器 (Playwright 依赖)

### 一键启动

```bash
# Windows
start.bat

# 跨平台
python start.py
```

启动脚本自动完成：检查环境 → 安装依赖 → 初始化数据库 → 启动前后端。

### 手动启动

#### 1. 后端

```bash
cd backend

# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 安装 Playwright 浏览器
playwright install chromium

# 初始化数据库 + 区县种子数据
python seed_data.py

# 启动服务 (http://localhost:8001)
uvicorn app.main:app --reload
```

API 文档: `http://localhost:8001/docs`

#### 2. 前端

```bash
cd frontend
npm install
npm run dev    # http://localhost:5173
```

Vite 开发服务器自动代理 `/api` → `http://127.0.0.1:8001`。

#### 3. 爬虫 CLI

```bash
cd backend

# 全量爬取 (所有区县)
python -m crawler crawl --max-pages 10

# 增量爬取 (每区县 1-2 页)
python -m crawler crawl --incremental

# 查看爬取状态
python -m crawler status
```

也可以在 Web UI (`/crawl` 页面) 中一键操作。

---

## 项目结构

```
data_web/
├── README.md                       # 项目文档
├── ARCHITECTURE.md                 # 完整架构文档
├── start.py / start.bat            # 一键启动脚本
├── tasks/                          # Windows 批处理任务
│   ├── daily-update-ages.bat       # 每日房龄刷新
│   └── weekly-incremental.bat      # 每周增量爬取
│
├── backend/
│   ├── app/                        # FastAPI 应用
│   │   ├── main.py                 # 入口: lifespan + CORS + 定时任务注册
│   │   ├── config.py               # 配置 (数据库路径自动计算)
│   │   ├── database.py             # SQLAlchemy async engine + session
│   │   ├── models/                 # ORM 模型 (6 表)
│   │   │   ├── listing.py          # 房源 (30+ 字段, 6 索引)
│   │   │   ├── district.py         # 区县 (37 个)
│   │   │   ├── community.py        # 小区
│   │   │   ├── price_history.py    # 价格历史
│   │   │   └── crawl.py            # 爬取批次/任务
│   │   ├── schemas/                # Pydantic 模型
│   │   ├── api/v1/                 # REST 端点 (22 个)
│   │   │   ├── analytics.py        # 7 个分析端点
│   │   │   ├── listings.py         # 房源 CRUD + 筛选分页
│   │   │   ├── crawl.py            # 爬取控制 + SSE 流
│   │   │   ├── map_data.py         # 地图数据
│   │   │   ├── districts.py        # 区县
│   │   │   ├── communities.py      # 小区
│   │   │   └── health.py           # 健康检查
│   │   ├── services/               # 业务逻辑层
│   │   │   ├── listing_service.py  # 查询构建 + 汇总统计
│   │   │   └── crawl_service.py    # 爬取流程编排
│   │   ├── utils/response.py       # ok() / error() 响应封装
│   │   └── api/deps.py             # 依赖注入 (get_db)
│   ├── crawler/                    # 爬虫引擎
│   │   ├── engine.py               # 异步引擎 (Round-Robin + 容灾)
│   │   ├── playwright_fetcher.py   # Playwright 无头获取 + 反检测
│   │   ├── parsers/
│   │   │   ├── list_parser.py      # 列表页自适应 HTML 解析
│   │   │   └── detail_parser.py    # 详情页 HTML 解析
│   │   ├── cleaner.py              # 数据清洗 (异常值过滤/归一化)
│   │   ├── dedup.py                # MD5 去重 + 变更检测
│   │   ├── pipelines.py            # DB 写入管线 (批量 upsert + 写锁)
│   │   ├── constants.py            # 37 区县配置 + URL 模板 + 速率限制
│   │   ├── district_resolver.py    # 区县归属推断 (120+ 别名)
│   │   └── __main__.py             # CLI 入口
│   ├── analytics/                  # 数据分析模块
│   │   ├── stats.py                # 描述统计 + 分布 + LRU 缓存 (TTL 60s)
│   │   ├── trends.py               # 日级趋势 + SMA-7 + 线性预测 (内存缓存)
│   │   ├── regression.py           # RandomForest 特征重要性 + 3-fold CV
│   │   ├── clustering.py           # KMeans + PCA + 肘部法则 + Silhouette
│   │   └── predict.py              # KNN (K=30) 加权估值 + 相似房源
│   ├── scheduler/
│   │   └── jobs.py                 # 增量爬取 + 龄期刷新 + 趋势缓存
│   ├── tests/                      # 99 个测试用例 (pytest + async)
│   ├── seed_data.py                # 初始化 37 区县
│   └── requirements.txt
│
└── frontend/
    ├── src/
    │   ├── pages/
    │   │   ├── CrawlPage.tsx        # 爬取控制台 (启动/停止/进度)
    │   │   ├── DataStoragePage.tsx  # 房源浏览 (12维筛选+排序+分页)
    │   │   └── AnalysisPage.tsx     # 分析仪表盘 (7 Tab)
    │   ├── components/
    │   │   ├── charts/              # BarChart / PieChart / LineChart / ScatterChart / MapChart
    │   │   ├── layout/              # AppLayout + Navbar
    │   │   └── ui/                  # Button / Select / Input / Table / Spinner / Chip
    │   ├── stores/                  # Zustand: useThemeStore / useCrawlStore / useSettingsStore
    │   ├── hooks/                   # useListings / useCrawlProgress
    │   ├── api/                     # analytics / crawl / listings / client
    │   ├── i18n/                    # zh.json / en.json
    │   ├── types/                   # TypeScript 公用类型
    │   └── constants/               # 区县常量
    └── public/
        └── chongqing.json           # GeoJSON 重庆地图
```

---

## API 总览

### 通用
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/health` | 健康检查 + 数据库连接状态 |

### 房源
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/listings` | 列表 (12 维筛选 + 排序分页) |
| GET | `/api/v1/listings/{id}` | 详情 (含价格历史) |
| GET | `/api/v1/listings/{id}/history` | 价格变动历史 |
| GET | `/api/v1/listings/stats/summary` | 汇总统计 (均价/中位数/价格段) |

### 区县 & 小区
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/districts` | 区县列表 (含房源计数) |
| GET | `/api/v1/districts/{id}/stats` | 区县详情 + 统计 |
| GET | `/api/v1/communities` | 小区列表 |
| GET | `/api/v1/communities/{id}` | 小区详情 |

### 爬取控制
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/crawl/start` | 启动爬取 (max_pages: 1–200) |
| GET | `/api/v1/crawl/status/{batch_id}` | 进度查询 |
| GET | `/api/v1/crawl/status/{batch_id}/stream` | SSE 实时进度推送 (2s 间隔) |
| POST | `/api/v1/crawl/stop/{batch_id}` | 停止爬取 |
| GET | `/api/v1/crawl/batches` | 历史批次 (最近 18 个) |

### 数据分析
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/analytics/overview` | 市场概览 (均价/分布/区县排名/主城vs郊区) |
| GET | `/api/v1/analytics/district-compare` | 区县对比 (均价/中位数/标准差) |
| GET | `/api/v1/analytics/price-distribution` | 价格/面积/龄期分布 |
| GET | `/api/v1/analytics/feature-importance` | RandomForest 特征重要性 + R² |
| GET | `/api/v1/analytics/clusters` | KMeans 聚类画像 + PCA 散点 |
| GET | `/api/v1/analytics/trends` | 日级趋势 + SMA-7 + 次日预测 (内存缓存) |
| GET | `/api/v1/analytics/trends/status` | 趋势缓存状态 |
| POST | `/api/v1/analytics/predict` | KNN 价格预估 + Top 5 相似房源 |

### 地图
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/map/district-prices` | 各区均价 (地图着色) |
| GET | `/api/v1/map/district-heatmap` | 房源密度热力 |

---

## 架构决策

### SQLite 而非 MySQL/PostgreSQL
- **零配置**: 无需安装外部数据库，`pip install` 后即用
- **WAL 模式**: 读写并发不互斥，单进程爬虫足够
- **单机场景**: 非商业化项目，单文件 `.db` 即完整数据库
- **可移植**: 数据文件可直接复制备份

### APScheduler 而非 Celery
- **进程内调度**: 3 个定时任务（爬虫/龄期/趋势），无需消息队列
- **零运维**: 无 Redis/Broker 依赖
- **asyncio 原生**: 与 FastAPI 共享事件循环

### Playwright 而非 httpx
- **JS 渲染必要**: 目标站点 (m.fang.com) 需要浏览器执行 JS 才能展示完整数据
- **反检测**: 覆盖 `navigator.webdriver`、注入 `window.chrome`、模拟地理位置
- **验证码处理**: 自动检测滑块/文字验证码，指数退避后跳区县

### 爬虫容灾
- Round-Robin 区县调度 (非顺序)，单区县异常不影响全局
- 验证码: 5 次打击 → 跳区县 (30s→150s 退避)
- 网络: 3 次失败 → 跳区县 (30s→120s 退避)
- DRY 检测: 连续 3 页 0 数据 → 区县完成
- 致命异常: try/finally 确保批次状态正确落库

### 数据库写入
- 所有写操作共用 `asyncio.Lock` (SQLite 单写者限制)
- 每 3 页 flush 一次 (减少 WAL 检查点压力)
- upsert 逻辑: 新 / 同MD5 (仅更新时间戳) / 不同MD5 (全量更新 + 价格历史)

---

## 数据说明

- 数据来源为 **fang.com 挂牌房源**，主城区占比约 85%，郊区样本稀疏
- 全局均价为房源数加权平均，偏向主城区价格水平
- 价格预测基于近 30 日线性回归外推，约束 ±30%，仅供参考
- 特征重要性模型的 R² 通常 < 0.6，定位是因素排序而非精准估值
- 价格预测使用 KNN 加权平均 (K=30)，置信度基于邻居距离和偏差

---

## 许可证

MIT
