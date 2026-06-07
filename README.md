# Crypto Quant Agent OS

> 全功能加密货币量化交易 Agent 操作系统 —— 数据、因子、策略、回测、模拟交易、AI 分析、飞书推送一体化。

## 概述

Crypto Quant Agent OS 是一个面向 Binance Futures 的量化交易系统。它从行情获取到策略信号、从回测验证到模拟交易、从 AI 分析到飞书推送，覆盖了量化交易的全链路。

设计目标：运行在本地服务器上，用 DeepSeek 做 AI 分析，用 PostgreSQL + pgvector 做长期记忆，用飞书做日常日报推送。

## 核心功能

| 模块 | 功能 |
|------|------|
| **Market Data** | Binance Futures REST + WebSocket，K线/资金费率/持仓量实时获取 |
| **Factor Engine** | 技术指标计算：MA、EMA、MACD、RSI、BOLL、ATR、成交量比、价格变化等 |
| **Strategy Engine** | 三种策略：趋势跟踪(Trend Following)、均值回归(Mean Reversion)、突破(Breakout) |
| **Backtest Engine** | 历史数据回测，输出收益率、夏普比率、最大回撤、胜率等 |
| **Execution Sandbox** | 模拟交易沙箱，不碰实盘，验证策略逻辑 |
| **Risk Engine** | 风险控制：仓位限制、杠杆限制、最大亏损限制 |
| **AI Analyst** | DeepSeek 驱动的 AI 分析，生成每日行情解读 |
| **Long-Term Memory** | PostgreSQL + pgvector 语义记忆，存储历史分析和市场状态 |
| **Feishu Notification** | 飞书自定义机器人，交互式卡片格式推送日报 |
| **MCP Server** | Model Context Protocol 服务，AI Agent 可直接调用交易工具 |
| **Scheduler** | 定时任务系统，自动执行每日分析推送 |

## 架构图

```
┌──────────────────────────────────────────────────────────────┐
│                     FastAPI Server (:8000)                    │
│                                                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────────┐  │
│  │ Market   │  │ Factor   │  │ Strategy │  │ Execution   │  │
│  │ Data     │→│ Engine   │→│ Engine   │→│ Sandbox     │  │
│  │ (REST/WS)│  │          │  │          │  │ + Risk      │  │
│  └──────────┘  └──────────┘  └──────────┘  └─────────────┘  │
│       │              │              │              │          │
│       ▼              ▼              ▼              ▼          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────────┐  │
│  │Backtest  │  │  AI      │  │ Memory   │  │ Feishu      │  │
│  │Engine    │  │ Analyst  │  │ (PGVector)│  │ Notifier    │  │
│  └──────────┘  └──────────┘  └──────────┘  └─────────────┘  │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐    │
│  │              MCP Server (:8001 / stdio)               │    │
│  └──────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────┘
         │                    │                    │
         ▼                    ▼                    ▼
   ┌─────────┐         ┌──────────┐         ┌──────────┐
   │ Binance │         │PostgreSQL│         │  Redis   │
   │ Futures │         │+pgvector │         │  Cache   │
   └─────────┘         └──────────┘         └──────────┘
```

## 技术栈

- **运行时**: Python 3.12+, FastAPI, Uvicorn
- **数据源**: Binance Futures (REST + WebSocket)
- **数据库**: PostgreSQL 16 + pgvector, SQLAlchemy 2.0 (async), Alembic
- **缓存**: Redis
- **AI**: DeepSeek (兼容 OpenAI SDK)
- **通知**: 飞书自定义机器人 Webhook (交互式卡片)
- **测试**: pytest, pytest-asyncio

## 快速开始

### 前置依赖

- Python 3.12+
- PostgreSQL 16 + pgvector 扩展
- Redis

### 安装

```bash
# 克隆
git clone https://github.com/xyh7448/crypto-agent.git
cd crypto-agent

# 创建虚拟环境
uv venv
source .venv/bin/activate

# 安装依赖
uv pip install -e .

# 配置环境变量
cp .env.example .env
# 编辑 .env，填入 API Key
```

### 配置 `.env`

```ini
# Binance Futures API
BINANCE_API_KEY=your_key
BINANCE_API_SECRET=your_secret

# LLM (DeepSeek)
OPENAI_API_KEY=sk-your_deepseek_key
OPENAI_BASE_URL=https://api.deepseek.com
MODEL_NAME=deepseek-v4-flash

# 飞书机器人 Webhook
FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/xxx

# 数据库
POSTGRES_URI=postgresql+asyncpg://user:pass@localhost:5432/crypto_agent
REDIS_URI=redis://localhost:6379/0
```

### 运行

```bash
# 初始化数据库
alembic upgrade head

# 启动服务
uvicorn app.main:app --host 0.0.0.0 --port 8000

# 触发每日分析
curl -X POST http://localhost:8000/api/v1/scheduler/trigger-daily
```

## 项目结构

```
crypto-agent/
├── app/
│   ├── main.py                  # FastAPI 入口，路由
│   ├── core/                    # 配置、数据库、日志、Redis
│   ├── market_data/             # Binance REST + WebSocket 客户端
│   ├── factors/                 # 技术因子引擎
│   ├── strategies/              # 交易策略 (趋势跟踪/均值回归/突破)
│   ├── backtest/                # 回测引擎 + 参数优化
│   ├── execution/               # 模拟交易沙箱 + 风控
│   ├── memory/                  # pgvector 长期记忆
│   ├── analyst/                 # DeepSeek AI 分析 Agent
│   ├── notification/            # 飞书通知 (交互式卡片)
│   ├── scheduler/               # 定时任务 (日报)
│   ├── mcp/                     # MCP 协议服务器
│   ├── models/                  # SQLAlchemy ORM 模型
│   └── schemas/                 # Pydantic V2 数据模型
├── tests/                       # 单元测试
├── Dockerfile                   # Docker 构建 (可选)
├── docker-compose.yml           # Docker Compose (可选)
├── Makefile                     # 常用命令
└── pyproject.toml               # 项目配置
```

## API 端点

| 路径 | 方法 | 说明 |
|------|------|------|
| `/health` | GET | 健康检查 |
| `/health/db` | GET | 数据库连接检查 |
| `/api/v1/market/klines/{symbol}` | GET | 获取 K 线数据 |
| `/api/v1/market/funding/{symbol}` | GET | 获取资金费率 |
| `/api/v1/market/oi/{symbol}` | GET | 获取持仓量 |
| `/api/v1/factors/{symbol}` | GET | 计算技术因子 |
| `/api/v1/signals/{symbol}` | GET | 获取交易信号 |
| `/api/v1/backtest` | POST | 运行回测 |
| `/api/v1/sandbox/order` | POST | 模拟开仓 |
| `/api/v1/sandbox/close/{symbol}` | POST | 模拟平仓 |
| `/api/v1/sandbox/portfolio` | GET | 查看持仓 |
| `/api/v1/sandbox/reset` | POST | 重置沙箱 |
| `/api/v1/memory/save` | POST | 保存记忆 |
| `/api/v1/memory/search` | GET | 搜索记忆 |
| `/api/v1/analysis/daily/{symbol}` | GET | AI 日报分析 |
| `/api/v1/scheduler/trigger-daily` | POST | 触发日报推送 |

## MCP 服务

支持 MCP (Model Context Protocol) stdio 模式，AI Agent 可直接调用以下工具：

- `get_market_data` — 获取 K 线数据
- `calculate_factors` — 计算技术因子
- `run_backtest` — 运行回测
- `generate_signal` — 生成交易信号
- `execute_sandbox_order` — 模拟开仓
- `save_memory` / `query_memory` — 读写长期记忆
- `generate_daily_report` — 生成 AI 日报
- `get_portfolio` — 查看持仓
- `get_funding_rate` — 查看资金费率/持仓量

```bash
# 启动 MCP 服务
python -m app.mcp.server
```

## 许可

MIT
