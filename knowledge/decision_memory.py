"""
Decision Memory — track trading decisions and their outcomes.

Records each decision with:
  - date, ticker, direction, weight, reasoning
  - 1/3/5/10 day forward returns (back-filled by scheduler)
  - signal type tags for accuracy breakdown

Usage:
    dm = DecisionMemory(storage)
    dm.record_decision(ticker="600519", direction="bullish", weight=0.3,
                       reason="momentum breakout", signal_type="momentum")
    accuracy = dm.get_accuracy(signal_type="momentum")
    dm.backfill_returns(target_date)  # back-fill forward returns
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

import pandas as pd
from loguru import logger


class DecisionMemory:
    """
    决策记忆 — 记录调仓决策并追踪事后收益验证。

    用 DuckDB 持久化，支持按信号类型/策略查询滚动准确率。
    """

    def __init__(self, storage):
        self.storage = storage

    def record_decision(self,
                        ticker: str,
                        direction: str,
                        weight: float,
                        reason: str,
                        signal_type: str = "generic",
                        strategy: str = "momentum",
                        decision_date: date = None,
                        price: float = None) -> str:
        """
        记录一次调仓决策。

        Args:
            ticker: 股票代码
            direction: bullish / bearish / neutral
            weight: 权重 [-1, +1]
            reason: 决策理由
            signal_type: 信号类型 (momentum, reversal, event, sentiment, ...)
            strategy: 策略名称
            decision_date: 决策日期 (默认今天)
            price: 决策时价格

        Returns:
            decision_id
        """
        return self.storage.save_decision(
            ticker=ticker,
            direction=direction,
            weight=weight,
            reason=reason,
            signal_type=signal_type,
            strategy=strategy,
            decision_date=decision_date or date.today(),
            price=price,
        )

    def get_accuracy(self,
                     signal_type: str = None,
                     strategy: str = None,
                     days: int = 90) -> dict:
        """
        查询滚动准确率。

        Args:
            signal_type: 按信号类型过滤
            strategy: 按策略过滤
            days: 回溯天数

        Returns:
            {signal_type: {total, correct, accuracy}} 或总体统计
        """
        return self.storage.get_decision_accuracy(
            signal_type=signal_type,
            strategy=strategy,
            days=days,
        )

    def backfill_returns(self, target_date: date = None):
        """
        回填决策的事后收益 (1/3/5/10 日)。

        对每个尚未回填的决策，从行情数据计算 forward returns。
        由 scheduler 每日自动调用。

        Args:
            target_date: 基准日期 (默认今天)
        """
        target_date = target_date or date.today()
        pending = self.storage.get_pending_decision_returns()

        if pending.empty:
            return

        count = 0
        for _, row in pending.iterrows():
            dec_date = row["decision_date"]
            if isinstance(dec_date, str):
                dec_date = date.fromisoformat(dec_date)
            ticker = row["ticker"]
            decision_id = row["decision_id"]

            # 加载行情数据获取事后收益
            try:
                df = self.storage.load_stock_daily(
                    ticker,
                    start_date=dec_date.isoformat(),
                    end_date=(dec_date + timedelta(days=15)).isoformat(),
                )
            except Exception:
                continue

            if df.empty or "close" not in df.columns:
                continue

            closes = df["close"].values
            entry_price = closes[0] if len(closes) > 0 else None

            returns = {}
            for offset, label in [(1, "return_1d"), (3, "return_3d"),
                                  (5, "return_5d"), (10, "return_10d")]:
                if len(closes) > offset:
                    r = closes[offset] / closes[0] - 1
                    returns[label] = round(float(r), 6)
                else:
                    returns[label] = None

            if any(v is not None for v in returns.values()):
                self.storage.update_decision_returns(decision_id, returns)
                count += 1

        if count > 0:
            logger.info(f"  已回填 {count} 条决策收益")

    def get_recent_decisions(self, limit: int = 20) -> pd.DataFrame:
        """获取最近决策记录"""
        return self.storage.load_decisions(limit=limit)

    def get_accuracy_summary(self, days: int = 90) -> str:
        """生成可读的准确率摘要"""
        overall = self.get_accuracy(days=days)
        by_signal = self.get_accuracy(signal_type="__all__", days=days)

        lines = [f"## 决策准确率 (近 {days} 天)\n"]
        if overall and overall.get("total", 0) > 0:
            lines.append(f"- **总体**: {overall['correct']}/{overall['total']} "
                        f"({overall['accuracy']:.1%})")
        else:
            lines.append("- 暂无决策记录")

        if by_signal and isinstance(by_signal, dict):
            lines.append("\n### 按信号类型\n")
            for sig, stats in sorted(by_signal.items()):
                if stats.get("total", 0) > 0:
                    lines.append(f"- **{sig}**: {stats['correct']}/{stats['total']} "
                                f"({stats['accuracy']:.1%})")

        return "\n".join(lines)
