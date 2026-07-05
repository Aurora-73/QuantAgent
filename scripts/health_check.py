"""
System health check — 8 checks for operational readiness.

Checks:
  1. Database connectivity (DuckDB)
  2. Data freshness (latest stock data date)
  3. Data completeness (ticker coverage)
  4. Factor coverage (how many factors have data)
  5. LLM API connectivity
  6. Data source connectivity (AKShare)
  7. Disk space
  8. Python dependencies

Usage:
    python -m scripts.health_check
    python -m scripts.health_check --json  # JSON output
"""
import json
import shutil
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

from loguru import logger

sys.path.insert(0, str(Path(__file__).parent.parent))

from configs.settings import settings


class HealthChecker:
    """Run system health checks."""

    def __init__(self):
        self.results = []

    def check_all(self) -> list[dict]:
        """Run all 8 checks."""
        logger.info("健康检查开始...")
        self.results = []

        self._check_db()
        self._check_data_freshness()
        self._check_data_completeness()
        self._check_factor_coverage()
        self._check_llm_api()
        self._check_data_source()
        self._check_backtest_persistence()
        self._check_disk()
        self._check_dependencies()

        passed = sum(1 for r in self.results if r["status"] == "pass")
        failed = sum(1 for r in self.results if r["status"] == "fail")
        warn = sum(1 for r in self.results if r["status"] == "warn")

        logger.info(f"健康检查完成: {passed}通过, {warn}警告, {failed}失败")
        return self.results

    def _add_result(self, name: str, status: str, detail: str, suggestion: str = ""):
        self.results.append({
            "name": name,
            "status": status,
            "detail": detail,
            "suggestion": suggestion,
        })
        icon = {"pass": "[OK]", "warn": "[!!]", "fail": "[XX]"}.get(status, "[??]")
        logger.info(f"  {icon} {name}: {detail}")

    # ============================================================
    # Check 1: Database
    # ============================================================

    def _check_db(self):
        db_path = Path(settings.db_path)
        if not db_path.exists():
            self._add_result("数据库连接", "fail",
                           f"DuckDB 文件不存在: {db_path}",
                           "运行 python -m scripts update-data 初始化数据库")
            return

        try:
            import duckdb
            conn = duckdb.connect(str(db_path))
            tables = conn.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema='main'"
            ).fetchall()
            table_names = [t[0] for t in tables]
            conn.close()
            self._add_result("数据库连接", "pass",
                           f"DuckDB 正常, {len(table_names)} 张表: {', '.join(table_names[:5])}")
        except Exception as e:
            self._add_result("数据库连接", "fail", str(e),
                           "检查 duckdb 安装和文件完整性")

    # ============================================================
    # Check 2: Data Freshness
    # ============================================================

    def _check_data_freshness(self):
        db_path = Path(settings.db_path)
        if not db_path.exists():
            self._add_result("数据时效", "warn", "数据库不存在", "先运行数据更新")
            return

        try:
            import duckdb
            conn = duckdb.connect(str(db_path))
            result = conn.execute(
                "SELECT MAX(date) FROM stock_daily"
            ).fetchone()
            conn.close()

            if result and result[0]:
                latest = result[0]
                if isinstance(latest, str):
                    latest = date.fromisoformat(latest)
                elif hasattr(latest, 'date'):
                    latest = latest.date()
                days_behind = (date.today() - latest).days

                if days_behind <= 1:
                    self._add_result("数据时效", "pass",
                                   f"最新数据日期 {latest} ({days_behind}天前)")
                elif days_behind <= 3:
                    self._add_result("数据时效", "warn",
                                   f"数据滞后 {days_behind} 天 (最新: {latest})",
                                   "运行 python -m scripts update-data")
                else:
                    self._add_result("数据时效", "fail",
                                   f"数据严重滞后 {days_behind} 天 (最新: {latest})",
                                   "立即运行 python -m scripts update-data")
            else:
                self._add_result("数据时效", "warn", "无数据记录", "运行数据更新")
        except Exception as e:
            self._add_result("数据时效", "warn", str(e))

    # ============================================================
    # Check 3: Data Completeness
    # ============================================================

    def _check_data_completeness(self):
        db_path = Path(settings.db_path)
        if not db_path.exists():
            self._add_result("数据完整性", "warn", "数据库不存在")
            return

        try:
            import duckdb
            conn = duckdb.connect(str(db_path))
            ticker_count = conn.execute(
                "SELECT COUNT(DISTINCT ticker) FROM stock_daily"
            ).fetchone()[0]
            conn.close()

            if ticker_count >= 300:
                self._add_result("数据完整性", "pass", f"覆盖 {ticker_count} 只标的")
            elif ticker_count >= 20:
                self._add_result("数据完整性", "warn",
                               f"仅 {ticker_count} 只标的",
                               "扩展股票池: python -m scripts update-data --universe csi300")
            else:
                self._add_result("数据完整性", "fail",
                               f"仅 {ticker_count} 只标的, 严重不足",
                               "运行 python -m scripts update-data --universe csi300")
        except Exception as e:
            self._add_result("数据完整性", "warn", str(e))

    # ============================================================
    # Check 4: Factor Coverage
    # ============================================================

    def _check_factor_coverage(self):
        try:
            from research.factors import FactorEngine
            engine = FactorEngine()
            factors = engine.list_factors()
            n = len(factors)

            if n >= 20:
                self._add_result("因子覆盖", "pass", f"{n} 个因子已注册")
            elif n >= 10:
                self._add_result("因子覆盖", "warn", f"仅 {n} 个因子")
            else:
                self._add_result("因子覆盖", "fail", f"因子数量过少 ({n})")
        except Exception as e:
            self._add_result("因子覆盖", "fail", str(e))

    # ============================================================
    # Check 5: LLM API
    # ============================================================

    def _check_llm_api(self):
        if not settings.openai_api_key:
            self._add_result("LLM API", "warn",
                           "未配置 OPENAI_API_KEY",
                           "在 .env 中设置 openai_api_key")
            return

        try:
            from openai import OpenAI
            client = OpenAI(
                api_key=settings.openai_api_key,
                base_url=settings.openai_base_url,
            )
            # Lightweight check: list models
            models = client.models.list()
            model_ids = [m.id for m in models.data[:5]]
            self._add_result("LLM API", "pass",
                           f"连接正常, 可用模型: {', '.join(model_ids[:3])}")
        except Exception as e:
            self._add_result("LLM API", "warn",
                           f"连接异常: {str(e)[:80]}",
                           "检查 API Key 和网络连接")

    # ============================================================
    # Check 6: Data Source (AKShare)
    # ============================================================

    def _check_data_source(self):
        try:
            import akshare as ak
            # Quick test: get CSI300 index
            df = ak.stock_zh_index_daily(symbol="sh000300")
            if df is not None and not df.empty:
                self._add_result("数据源", "pass",
                               f"AKShare 正常, 沪深300最新{len(df)}条")
            else:
                self._add_result("数据源", "warn", "AKShare 返回空数据")
        except ImportError:
            self._add_result("数据源", "warn",
                           "AKShare 未安装",
                           "pip install akshare")
        except Exception as e:
            self._add_result("数据源", "warn",
                           f"AKShare 异常: {str(e)[:80]}",
                           "检查网络连接（国内数据不需要代理）")

    # ============================================================
    # Check 7: Disk Space
    # ============================================================

    def _check_disk(self):
        try:
            usage = shutil.disk_usage(Path.cwd())
            free_gb = usage.free / (1024 ** 3)
            total_gb = usage.total / (1024 ** 3)

            if free_gb > 10:
                self._add_result("磁盘空间", "pass",
                               f"可用 {free_gb:.1f}GB / 总计 {total_gb:.1f}GB")
            elif free_gb > 2:
                self._add_result("磁盘空间", "warn",
                               f"仅剩 {free_gb:.1f}GB",
                               "清理磁盘空间")
            else:
                self._add_result("磁盘空间", "fail",
                               f"磁盘空间严重不足 ({free_gb:.1f}GB)",
                               "立即清理磁盘")
        except Exception as e:
            self._add_result("磁盘空间", "warn", str(e))

    # ============================================================
    # Check 8: Backtest Persistence
    # ============================================================

    def _check_backtest_persistence(self):
        db_path = Path(settings.db_path)
        if not db_path.exists():
            self._add_result("回测持久化", "warn", "数据库不存在")
            return

        try:
            import duckdb
            conn = duckdb.connect(str(db_path))
            tables = [t[0] for t in conn.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema='main'"
            ).fetchall()]
            conn.close()

            has_runs = "backtest_runs" in tables
            has_equity = "backtest_equity" in tables

            if has_runs and has_equity:
                self._add_result("回测持久化", "pass", "backtest_runs + backtest_equity 表就绪")
            elif has_runs:
                self._add_result("回测持久化", "pass", "backtest_runs 表就绪")
            else:
                self._add_result("回测持久化", "warn", "回测表未创建，需运行一次回测以初始化",
                               "python -m scripts backtest")
        except Exception as e:
            self._add_result("回测持久化", "warn", str(e))

    # ============================================================
    # Check 9: Dependencies
    # ============================================================

    def _check_dependencies(self):
        critical = ["pandas", "numpy", "duckdb"]
        optional = ["akshare", "openai", "vectorbt", "riskfolio", "loguru"]

        missing_critical = []
        for pkg in critical:
            try:
                __import__(pkg)
            except ImportError:
                missing_critical.append(pkg)

        missing_optional = []
        for pkg in optional:
            try:
                __import__(pkg)
            except ImportError:
                missing_optional.append(pkg)

        if missing_critical:
            self._add_result("依赖检查", "fail",
                           f"缺少关键依赖: {', '.join(missing_critical)}",
                           f"pip install {' '.join(missing_critical)}")
        elif missing_optional:
            self._add_result("依赖检查", "warn",
                           f"缺少可选依赖: {', '.join(missing_optional)}",
                           f"pip install {' '.join(missing_optional)}")
        else:
            self._add_result("依赖检查", "pass", "所有核心依赖已安装")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="系统健康检查")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    args = parser.parse_args()

    checker = HealthChecker()
    results = checker.check_all()

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))

    # Return exit code
    failed = sum(1 for r in results if r["status"] == "fail")
    sys.exit(1 if failed > 0 else 0)


if __name__ == "__main__":
    main()
