"""
爬虫引擎 — cq.esf.fang.com 桌面站。

模块:
  engine.py              Playwright 全局列表分页爬虫
  playwright_fetcher.py  Playwright/Edge 浏览器抓取（绕过滑块验证）
  fetcher.py             httpx 快速首页抓取（备用）
  parsers/               HTML 解析器（列表页 / 详情页）
  cleaner.py             数据清洗
  dedup.py               去重
  pipelines.py           数据库写入管线
  constants.py           全局配置
"""