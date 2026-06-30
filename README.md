# 重庆市二手房源价格数据分析与可视化

## 快速启动

```bash
# 1. 后端
cd backend
pip install -r requirements.txt
python seed_data.py
uvicorn app.main:app --reload          # http://localhost:8000

# 2. 前端
cd frontend
npm install
npm run dev                            # http://localhost:5173
```

## 技术栈

- **后端**: Python 3.12 + FastAPI + SQLAlchemy + SQLite
- **前端**: React 18 + TypeScript + Tailwind CSS + ECharts + Zustand
- **爬虫**: httpx + BeautifulSoup4 + fontTools
- **数据分析**: pandas + scikit-learn

## 项目结构

```
data_web/
├── .env                         # 环境变量（DATABASE_URL）
├── .gitignore
├── README.md                    # 本文件
├── guide.md                     # 完整技术方案文档
├── requirements.txt             # 项目级依赖（同 backend/）
│
├── backend/
│   ├── requirements.txt         # Python 依赖
│   ├── alembic.ini              # Alembic 配置
│   ├── seed_data.py             # 初始化 38 个区县数据
│   ├── alembic/
│   │   ├── env.py               # 异步迁移环境
│   │   └── versions/            # 迁移文件（待生成）
│   │
│   ├── app/
│   │   ├── main.py              # FastAPI 入口 + CORS + lifespan
│   │   ├── config.py            # pydantic-settings 配置
│   │   ├── database.py          # SQLAlchemy async 引擎
│   │   ├── models/              # ORM 模型
│   │   │   ├── district.py      #   区县
│   │   │   ├── community.py     #   小区
│   │   │   ├── listing.py       #   房源（核心表）
│   │   │   ├── price_history.py #   价格历史
│   │   │   └── crawl.py         #   爬取批次/任务
│   │   ├── schemas/             # Pydantic 请求/响应
│   │   │   ├── common.py        #   APIResponse / PaginatedResponse
│   │   │   ├── district.py      #   District 相关
│   │   │   ├── listing.py       #   Listing 相关（7 个 Schema）
│   │   │   ├── community.py     #   Community 相关
│   │   │   └── crawl.py         #   爬取控制相关
│   │   ├── api/                 # 路由
│   │   │   ├── deps.py          #   DB session 依赖注入
│   │   │   └── v1/
│   │   │       ├── router.py    #     路由聚合
│   │   │       ├── health.py    #     GET /api/v1/health
│   │   │       ├── districts.py #     GET /api/v1/districts, /districts/{id}/stats
│   │   │       ├── listings.py  #     GET /api/v1/listings, /listings/{id}, /stats/summary
│   │   │       ├── communities.py#    GET /api/v1/communities, /communities/{id}
│   │   │       └── crawl.py     #     POST /crawl/start, GET /status/{id}, SSE stream
│   │   ├── services/            # 业务逻辑层
│   │   │   ├── listing_service.py#   房源查询/统计
│   │   │   └── crawl_service.py  #   爬虫启停/SSE
│   │   └── utils/               # 工具
│   │       └── response.py      #   统一响应格式
│   │
│   ├── crawler/                 # 爬虫模块
│   │   ├── constants.py         #   全局常量（区县/URL/UA池）
│   │   ├── fetcher.py           #   HTTP 客户端（UA轮换/retry/限速）
│   │   ├── engine.py            #   爬虫引擎（asyncio 并发编排）
│   │   ├── pipelines.py         #   数据库管线（WAL+写锁）
│   │   ├── cleaner.py           #   数据清洗
│   │   ├── dedup.py             #   MD5 去重 + 小区匹配
│   │   ├── __main__.py          #   CLI 测试入口
│   │   └── parsers/
│   │       ├── list_parser.py   #     列表页解析器
│   │       ├── detail_parser.py #     详情页解析器
│   │       └── font_parser.py   #     fontTools 字体解密
│   ├── tests/                   # 单元测试
│   ├── analytics/               # 数据分析（Phase 5）
│   └── scheduler/               # 定时任务（Phase 6）
│
└── frontend/
    ├── index.html
    ├── package.json
    ├── vite.config.ts
    ├── tsconfig.json
    └── src/
        ├── main.tsx             # React 入口
        ├── App.tsx              # 路由配置
        ├── index.css            # Tailwind + CSS 变量（亮/暗主题）
        ├── api/
        │   ├── client.ts        # Axios 实例
        │   ├── listings.ts      #   房源 API
        │   ├── districts.ts     #   区县 API
        │   └── crawl.ts         #   爬取 API + SSE
        ├── types/
        │   └── common.ts        # TS 类型定义
        ├── stores/
        │   └── useThemeStore.ts # 主题/语言状态
        ├── components/
        │   ├── layout/
        │   │   ├── Navbar.tsx   #   顶部导航栏
        │   │   └── AppLayout.tsx#   整体布局
        │   ├── ui/              # 基础 UI 组件 (Button/Select/Chip/Table/Spinner)
        │   └── charts/          # 图表封装（Phase 5）
        ├── pages/
        │   ├── CrawlPage.tsx    #   数据爬取页
        │   ├── DataStoragePage.tsx # 数据浏览页
        │   └── AnalysisPage.tsx #   数据分析页
        ├── hooks/               # 自定义 Hooks (useListings/useCrawlProgress/useAnalytics)
        └── i18n/               # 国际化文件 (zh.json/en.json)
```

## 开发阶段

| Phase | 内容 | 状态 |
|-------|------|------|
| Phase 1 | 项目骨架：FastAPI + React + SQLite + 数据模型 | ✅ 完成 |
| Phase 2 | 爬虫开发：fang.com 解析 + 字体解密 + 并发调度 | ✅ 完成 |
| Phase 3 | 后端 API：房源 CRUD + 筛选排序 + 爬取控制 + SSE | ✅ 完成 |
| Phase 4 | 前端页面：三个主界面 + UI 组件 + 图表 + i18n | ✅ 完成 |
| Phase 5 | 数据分析：统计 + 因素分析 + 聚类 + 趋势 | ⏳ |
| Phase 6 | 增量更新：APScheduler 定时任务 + 价格历史 | ⏳ |
| Phase 7 | 地图可视化：ECharts Map + GeoJSON | ⏳ |
