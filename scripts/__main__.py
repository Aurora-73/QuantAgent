"""
Quant System CLI

用法：
    python -m scripts update-data          # 更新数据
    python -m scripts daily-research       # 运行每日研究
    python -m scripts backtest             # 运行回测
    python -m scripts show-knowledge       # 查看知识库
    python -m scripts health-check         # 系统健康检查
"""
import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def main():
    parser = argparse.ArgumentParser(description="Quant System CLI")
    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # update-data
    update_parser = subparsers.add_parser("update-data", help="更新数据")
    update_parser.add_argument("--universe", default="csi300")
    update_parser.add_argument("--tickers", default=None)
    update_parser.add_argument("--start", default="2020-01-01")

    # daily-research
    research_parser = subparsers.add_parser("daily-research", help="运行每日研究")
    research_parser.add_argument("--date", default=None)
    research_parser.add_argument("--no-llm", action="store_true")

    # backtest
    bt_parser = subparsers.add_parser("backtest", help="运行回测")
    bt_parser.add_argument("--strategy", default="momentum")
    bt_parser.add_argument("--ticker", default="600519")
    bt_parser.add_argument("--start", default="2025-01-01")
    bt_parser.add_argument("--end", default=None)

    # show-knowledge
    kb_parser = subparsers.add_parser("show-knowledge", help="查看知识库")
    kb_parser.add_argument("--type", default="stats",
                          choices=["stats", "daily", "weekly", "monthly",
                                   "events", "hypotheses", "failures"])
    kb_parser.add_argument("--limit", type=int, default=10)
    kb_parser.add_argument("--date", default=None)

    # health-check
    health_parser = subparsers.add_parser("health-check", help="系统健康检查")
    health_parser.add_argument("--json", action="store_true", help="JSON 输出")

    args = parser.parse_args()

    if args.command == "update-data":
        from scripts.update_data import update_data
        tickers = [t.strip().zfill(6) for t in args.tickers.split(",")] if args.tickers else None
        update_data(args.universe, tickers, args.start)

    elif args.command == "daily-research":
        from scripts.daily_research import run_daily_research
        from datetime import date
        target = date.fromisoformat(args.date) if args.date else date.today()
        run_daily_research(target, use_llm=not args.no_llm)

    elif args.command == "backtest":
        from scripts.backtest import run_backtest
        run_backtest(args.strategy, args.ticker, args.start, args.end)

    elif args.command == "show-knowledge":
        from scripts.show_knowledge import show_knowledge
        show_knowledge(args.type, args.limit, args.date)

    elif args.command == "health-check":
        from scripts.health_check import HealthChecker
        import json
        checker = HealthChecker()
        results = checker.check_all()
        if args.json:
            print(json.dumps(results, ensure_ascii=False, indent=2))
        failed = sum(1 for r in results if r["status"] == "fail")
        sys.exit(1 if failed > 0 else 0)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
