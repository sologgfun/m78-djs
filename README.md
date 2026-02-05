# 白马梯级轮动策略 - A股回测系统

基于"白马梯级轮动策略"的量化回测系统，提供Web界面进行股票选择、回测配置和结果展示。

## 策略逻辑

**入场信号** — 现价 ≤ MA120 × 入场比例（默认88%），使用首次仓位资金入场

**梯级管理**
- 向下补仓：按自定义梯级逐步加仓
- 向上止盈：单层盈利达标卖出，或价格回到 MA120 × 清仓比例全清

**资金回滚** — 分红复投，空仓后重新筛选

## 快速开始

```bash
# 安装依赖
make install

# 启动系统（后端 + 前端）
make dev

# 浏览器打开 http://localhost:5173
```

## 使用流程

1. **选择股票** — 搜索/推荐列表中选择
2. **配置参数** — 时间范围、资金、策略参数（入场比例/梯级/止盈等均可调）
3. **创建回测** — 查看进度
4. **查看结果** — 收益率、胜率、回撤、交易明细等

## 项目结构

```
djs/
├── backend/              # 后端服务（Flask API）
│   ├── app.py            # API 路由
│   ├── backtest_worker.py# 回测工作线程
│   ├── database.py       # SQLite 数据库
│   └── stock_service.py  # 股票搜索/筛选
├── frontend-vite/        # 前端界面（Vue 3 + PrimeVue）
├── backtest_engine.py    # 回测引擎
├── strategy.py           # 策略逻辑
├── portfolio.py          # 持仓管理
├── config.py             # 默认参数常量
├── example_config.py     # 预设配置方案
├── data_fetcher.py       # 数据获取（东财API）
├── indicators.py         # 技术指标计算
└── Makefile              # 命令集合
```

## 系统要求

- Python 3.8+
- Node.js 18+
- 网络连接（获取股票数据）

## 免责声明

仅供学习研究，不构成投资建议。
