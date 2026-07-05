# QuantAgent — AI-Assisted Quantitative Trading Research System

> **Core Principle**: Traditional quantitative engines form the trading backbone, while LLM only handles research and information processing, never directly deciding trades.
> **Design Philosophy**: Stand on the shoulders of giants - directly integrate existing open-source projects, only write the necessary glue layer.

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Status](https://img.shields.io/badge/status-active-orange.svg)](https://github.com/Aurora-73/QuantAgent)

## 📖 Project Introduction

QuantAgent is a **personal implementable Agent fund company** that automates the entire quantitative trading research workflow through multi-Agent team collaboration:

- **Data Layer**: Multi-data-source auto-switching (AKShare/baostock/pytdx), unified data cleaning
- **Research Layer**: Factor analysis, strategy backtesting, Walk-forward validation
- **Strategy Layer**: Plugin-based architecture supporting momentum, event-driven, sentiment analysis and more
- **Risk Layer**: Systematic risk engine with single-stock limits, industry concentration, drawdown circuit breakers
- **Memory Layer**: Hierarchical memory system (Daily → Weekly → Monthly → Quarterly → Annual)
- **LLM Assistance**: Multi-Agent research team (News/Fundamental/Technical/Risk/Research Assistant)

## 🏗️ System Architecture

### System Context Diagram

![System Context Diagram](docs/images/SystemContextDiagram.png)

### Core Business Architecture

![Core Business Architecture](docs/images/CoreBusinessArchitecture.png)

### Agent Team Collaboration Architecture

![Agent Team Collaboration Architecture](docs/images/AgentTeamCollaborationArchitecture.png)

## 📁 Directory Structure

```
quant-system/
├── quant_system/              # Core source code package
│   ├── data/                  # Data layer
│   │   ├── provider.py        # Data acquisition
│   │   ├── storage.py         # DuckDB storage
│   │   └── cleaner.py         # Data cleaning
│   ├── strategies/            # Strategy layer
│   │   ├── base/              # Strategy base class
│   │   ├── momentum/          # Momentum strategy
│   │   ├── event_driven/      # Event-driven strategy
│   │   └── sentiment/         # Sentiment strategy
│   ├── research/              # Research layer
│   │   ├── backtest.py        # Backtest engine
│   │   └── factor_eval.py     # Factor evaluation
│   ├── risk/                  # Risk layer
│   │   ├── risk_engine.py     # Risk engine
│   │   └── portfolio.py       # Portfolio optimization
│   ├── knowledge/             # Memory layer
│   │   └── knowledge_base.py  # Hierarchical memory system
│   ├── llm/                   # LLM layer
│   │   └── report_agent.py    # Report generation agent
│   ├── integrations/          # Integration layer
│   │   ├── qlib_engine.py     # Qlib integration
│   │   ├── vnpy_engine.py     # vnpy integration
│   │   ├── trading_agents.py  # TradingAgents integration
│   │   └── openbb_data.py     # OpenBB integration
│   ├── configs/               # Configuration files
│   └── monitoring/            # Monitoring layer
├── examples/                  # Usage examples
│   ├── 00_quick_start.py      # Quick start
│   ├── 01_get_data.py         # Data acquisition
│   ├── 02_calc_factors.py     # Factor calculation
│   ├── 03_backtest.py         # Backtest demo
│   ├── 04_knowledge.py        # Knowledge base demo
│   └── 05_llm_analysis.py     # LLM analysis demo
├── tests/                     # Unit tests
├── scripts/                   # Script entry points
├── docs/                      # Documentation
├── requirements.txt           # Dependencies
├── pyproject.toml             # Project configuration
└── LICENSE                    # License
```

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- Git

### One-Click Installation (Recommended)

**Cross-platform (Recommended):**
```bash
python scripts/install.py
```

**Windows (PowerShell):**
```powershell
powershell -ExecutionPolicy Bypass -File scripts/install_windows.ps1
```

**Linux/Mac (Bash):**
```bash
bash scripts/install.sh
```

The script automatically completes:
1. ✅ Environment check (Python/Git)
2. ✅ Create virtual environment (auto-detect and fix platform mismatch)
3. ✅ Install core dependencies (requirements.txt)
4. ✅ Create config file (configs/.env)
5. ✅ Create necessary directories (data/, logs/, knowledge/)
6. ✅ Verify installation (run verify_project.py)

### Manual Installation

```bash
# Clone the project
git clone https://github.com/Aurora-73/QuantAgent.git
cd quant-system

# Create virtual environment
python -m venv .venv
source .venv/bin/activate    # Linux/macOS
.venv\Scripts\activate       # Windows

# Install dependencies
pip install -r requirements.txt

# Configure API Key
cp configs/.env.example configs/.env
# Edit configs/.env and fill in necessary API keys
```

### Optional Dependencies

| Module | Command | Description |
|--------|---------|-------------|
| Qlib | `pip install qlib` | Research core, factor analysis/backtest |
| vnpy | `pip install ta-lib vnpy vnpy-ctp` | Execution engine, live trading |
| OpenBB | `pip install openbb` | Global data sources |

### Run Examples

```bash
# Quick start: Get data and run backtest
python examples/00_quick_start.py

# Get stock data
python examples/01_get_data.py --ticker 600519 --start 2025-01-01

# Calculate factors
python examples/02_calc_factors.py

# Run backtest
python examples/03_backtest.py --strategy momentum

# Use knowledge base
python examples/04_knowledge.py

# LLM analysis
python examples/05_llm_analysis.py
```

### Daily Research Workflow

```bash
# Run daily research (without LLM)
python -m scripts daily-research --no-llm

# Run backtest
python -m scripts backtest --strategy momentum --ticker 600519 --start 2025-01-01

# Health check
python -m scripts health_check
```

## 🤖 The Right Place for LLM

```
✅ Appropriate (via TradingAgents)     ❌ Inappropriate
─────────────────────────────────────────────────────
Technical Analysis (Market Analyst)    Direct trading decisions
Fundamental Analysis                   Direct position generation
Sentiment Analysis                     Replace risk control rules
News Analysis                          Replace portfolio optimizer
Bull/Bear Debate                       Replace execution engine
Risk Debate                            Unconstrained free decisions
```

**In a nutshell: LLM is a researcher, not a trader.**

## 🧪 Run Tests

```bash
# Run all tests
pytest

# Run specific module tests
pytest tests/test_risk_engine.py -v

# Run strategy-related tests
pytest tests/test_momentum_strategy.py -v

# Generate coverage report
pytest --cov=quant_system --cov-report=html
```

## 🌐 Open Source Project Integrations

| Project | Purpose | Integration Method | Integration Module |
|---------|---------|-------------------|-------------------|
| **Qlib** | Research core | Direct import | `integrations/qlib_engine.py` |
| **vnpy** | Execution core | Direct import | `integrations/vnpy_engine.py` |
| **TradingAgents** | LLM Multi-Agent research | Direct import | `integrations/trading_agents.py` |
| **OpenBB** | Data entry | Direct import | `integrations/openbb_data.py` |
| **Riskfolio-Lib** | Portfolio optimization | pip install | `risk/portfolio.py` |
| **VectorBT** | Fast backtest | pip install | `research/backtest.py` |
| **AKShare** | A-Shares data | pip install | `data/provider.py` |

## 📊 Core Modules

### Strategy Interface (Must implement for each strategy)

```python
class StrategyBase(ABC):
    prepare_features()          # Prepare features
    generate_signal()           # Generate signals
    position_sizing()           # Position sizing
    risk_check()                # Risk check
    expected_holding_period()   # Expected holding period
    kill_switch_condition()     # Circuit breaker condition
```

### Knowledge Base Structure

```
knowledge/
  daily/          Daily reports (Markdown)
  weekly/         Weekly reports
  monthly/        Monthly reports
  quarterly/      Quarterly reports
  annual/         Annual reports
  events/         Event database (JSONL)
  hypotheses/     Hypothesis library
  failures/       Failure cases
```

## 🗺️ Development Roadmap

### Phase 1: Research + Reporting + Review ✅
- [x] Data integration (AKShare + OpenBB)
- [x] Qlib research engine integration
- [x] Factor calculation and evaluation
- [x] VectorBT backtesting
- [x] Knowledge base (events/hypotheses/lessons)
- [x] Daily/Weekly/Monthly report generation
- [x] Riskfolio-Lib portfolio optimization
- [x] Risk engine
- [x] Monitoring and alerts
- [x] TradingAgents multi-Agent integration

### Phase 2: Signal Engine + Backtesting ⚡
- [x] Strategy plugin interface
- [x] Momentum strategy implementation
- [ ] Qlib LightGBM model training
- [ ] Walk-forward validation

### Phase 3: Simulation Trading
- [ ] vnpy simulated trading
- [ ] Slippage and execution monitoring
- [ ] Backtest vs live trading deviation analysis

### Phase 4: Small-capacity Live Trading
- [ ] vnpy CTP/IB connection
- [ ] Risk circuit breaker mechanism
- [ ] Real-time monitoring and alerts

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙋‍♂️ Contributing

Welcome to submit Issues and Pull Requests! Please follow these guidelines:

1. Fork the project
2. Create a feature branch (`git checkout -b feature/foo`)
3. Commit your changes (`git commit -am 'Add foo'`)
4. Push to the branch (`git push origin feature/foo`)
5. Create a Pull Request

---

**LLM doesn't predict price movements; LLM improves the efficiency and quality of the entire research pipeline!** 🚀