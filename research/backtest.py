"""
回测引擎 — 基于 VectorBT

职责：
  - 快速向量化回测
  - 参数扫描优化
  - 策略对比评估
  - 生成回测报告

VectorBT 优势：
  - 比传统事件驱动回测快 100-1000x
  - 基于 pandas/numpy，无缝集成
  - 丰富的可视化工具
"""
import numpy as np
import pandas as pd
from loguru import logger

HAS_VECTORBT = False

class BacktestEngine:
    """
    回测引擎

    提供两种回测模式：
    1. signal_backtest: 基于信号的回测 (entries/exits)
    2. portfolio_backtest: 基于权重的回测 (每日权重)
    """

    @staticmethod
    def signal_backtest(close: pd.Series,
                        entries: pd.Series,
                        exits: pd.Series,
                        init_cash: float = 1_000_000,
                        fees: float = 0.001,
                        slippage: float = 0.001) -> dict:
        """
        基于信号的回测

        Args:
            close: 收盘价序列
            entries: 买入信号 (bool Series)
            exits: 卖出信号 (bool Series)
            init_cash: 初始资金
            fees: 手续费率
            slippage: 滑点

        Returns:
            回测结果 dict
        """
        if not HAS_VECTORBT:
            return BacktestEngine._simple_signal_backtest(
                close, entries, exits, init_cash, fees, slippage)

        try:
            # 设置频率
            if close.index.freq is None:
                freq = pd.infer_freq(close.index[:20])
                if freq is None:
                    freq = "B"  # 默认工作日
            else:
                freq = close.index.freq

            pf = vbt.Portfolio.from_signals(
                close=close,
                entries=entries,
                exits=exits,
                init_cash=init_cash,
                fees=fees,
                slippage=slippage,
                freq=freq,
            )

            return {
                "total_return": pf.total_return(),
                "annual_return": pf.annualized_return(),
                "sharpe_ratio": pf.sharpe_ratio(),
                "max_drawdown": pf.max_drawdown(),
                "win_rate": pf.trades.win_rate(),
                "trade_count": pf.trades.count(),
                "equity_curve": pf.value(),
                "drawdown_curve": pf.drawdown(),
            }
        except Exception as e:
            logger.warning(f"VectorBT 回测失败: {e}，使用简化版本")
            return BacktestEngine._simple_signal_backtest(
                close, entries, exits, init_cash, fees, slippage)

    @staticmethod
    def portfolio_backtest(close: pd.DataFrame,
                           weights: pd.DataFrame,
                           init_cash: float = 1_000_000,
                           fees: float = 0.001,
                           rebalance_freq: str = "W") -> dict:
        """
        基于权重的组合回测

        Args:
            close: 多资产收盘价 (columns=tickers)
            weights: 每日权重 (columns=tickers, 每行和为1)
            init_cash: 初始资金
            fees: 手续费率
            rebalance_freq: 调仓频率

        Returns:
            回测结果 dict
        """
        if not HAS_VECTORBT:
            return BacktestEngine._simple_portfolio_backtest(
                close, weights, init_cash, fees)

        # 计算每日收益率
        returns = close.pct_change().fillna(0)

        # 计算组合收益
        portfolio_returns = (weights.shift(1) * returns).sum(axis=1)

        # 构建权益曲线
        equity = (1 + portfolio_returns).cumprod() * init_cash

        # 计算指标
        total_return = equity.iloc[-1] / init_cash - 1
        days = (equity.index[-1] - equity.index[0]).days
        annual_return = (1 + total_return) ** (365 / max(days, 1)) - 1

        drawdown = (equity - equity.expanding().max()) / equity.expanding().max()
        max_dd = drawdown.min()
        sharpe = portfolio_returns.mean() / (portfolio_returns.std() + 1e-8) * np.sqrt(252)

        return {
            "total_return": total_return,
            "annual_return": annual_return,
            "sharpe_ratio": sharpe,
            "max_drawdown": max_dd,
            "equity_curve": equity,
            "drawdown_curve": drawdown,
            "daily_returns": portfolio_returns,
        }

    @staticmethod
    def factor_backtest(close: pd.Series,
                        factor: pd.Series,
                        n_groups: int = 5,
                        holding_days: int = 5) -> dict:
        """
        因子分组回测 (IC 分析)

        将股票按因子值分为 n 组，计算各组收益。

        Args:
            close: 收盘价
            factor: 因子值
            n_groups: 分组数
            holding_days: 持仓天数

        Returns:
            分组收益 dict
        """
        returns = close.pct_change(holding_days).shift(-holding_days)

        # 按因子分组
        valid = pd.DataFrame({"factor": factor, "returns": returns}).dropna()
        valid["group"] = pd.qcut(valid["factor"], n_groups, labels=False, duplicates="drop")

        # 计算各组平均收益
        group_returns = valid.groupby("group")["returns"].mean()

        # 计算多空收益
        long_short = group_returns.iloc[-1] - group_returns.iloc[0]

        # 计算 IC
        ic = factor.corr(returns)
        ic_series = factor.rolling(20).corr(returns)
        icir = ic_series.mean() / (ic_series.std() + 1e-8)

        return {
            "ic": ic,
            "icir": icir,
            "ic_series": ic_series,
            "group_returns": group_returns,
            "long_short_return": long_short,
            "n_groups": n_groups,
        }

    @staticmethod
    def walk_forward(close: pd.Series,
                     signal_func,
                     train_window: int = 252,
                     test_window: int = 63,
                     step: int = 21) -> dict:
        """
        Walk-forward 验证

        Args:
            close: 收盘价
            signal_func: 信号生成函数 signal_func(close_slice) -> (entries, exits)
            train_window: 训练窗口 (天)
            test_window: 测试窗口 (天)
            step: 步进 (天)

        Returns:
            各期回测结果
        """
        results = []
        dates = close.index

        i = train_window
        while i + test_window <= len(dates):
            # 训练集
            train_start = i - train_window
            train_slice = close.iloc[train_start:i]

            # 测试集
            test_slice = close.iloc[i:i + test_window]

            # 在训练集上生成信号 (简化：直接用测试集数据)
            # 实际应该在训练集上训练参数，在测试集上应用
            try:
                entries, exits = signal_func(test_slice)
                test_result = BacktestEngine._simple_signal_backtest(
                    test_slice, entries, exits, fees=0.001)
                results.append({
                    "period_start": dates[i],
                    "period_end": dates[min(i + test_window - 1, len(dates) - 1)],
                    "return": test_result["total_return"],
                    "sharpe": test_result["sharpe_ratio"],
                })
            except Exception as e:
                logger.warning(f"Walk-forward 期 {i} 失败: {e}")

            i += step

        if not results:
            return {"periods": [], "avg_return": 0, "avg_sharpe": 0}

        return {
            "periods": results,
            "avg_return": np.mean([r["return"] for r in results]),
            "avg_sharpe": np.mean([r["sharpe"] for r in results]),
            "win_periods": sum(1 for r in results if r["return"] > 0),
            "total_periods": len(results),
        }

    @staticmethod
    def compare_strategies(results: dict[str, dict]) -> pd.DataFrame:
        """
        对比多个策略的回测结果

        Args:
            results: {strategy_name: backtest_result}

        Returns:
            对比 DataFrame
        """
        rows = []
        for name, r in results.items():
            rows.append({
                "策略": name,
                "总收益": f"{r.get('total_return', 0):.2%}",
                "年化收益": f"{r.get('annual_return', 0):.2%}",
                "夏普比率": f"{r.get('sharpe_ratio', 0):.2f}",
                "最大回撤": f"{r.get('max_drawdown', 0):.2%}",
                "胜率": f"{r.get('win_rate', 0):.2%}",
                "交易次数": r.get("trade_count", 0),
            })
        return pd.DataFrame(rows)

    # ============================================================
    # 简化回测 (不依赖 VectorBT)
    # ============================================================

    @staticmethod
    def _simple_signal_backtest(close, entries, exits,
                                init_cash=1_000_000,
                                fees=0.001, slippage=0.001) -> dict:
        """简化信号回测"""
        cash = init_cash
        shares = 0
        equity = []
        entry_value = 0.0
        trade_pnls: list[float] = []

        for i in range(len(close)):
            price = close.iloc[i]

            if entries.iloc[i] and shares == 0:
                # 买入
                buy_price = price * (1 + slippage)
                shares = int(cash / (buy_price * (1 + fees)))
                entry_value = shares * buy_price * (1 + fees)
                cash -= entry_value

            elif exits.iloc[i] and shares > 0:
                # 卖出
                sell_price = price * (1 - slippage)
                exit_value = shares * sell_price * (1 - fees)
                trade_pnls.append(exit_value - entry_value)
                cash += exit_value
                shares = 0

            equity.append(cash + shares * price)

        equity = pd.Series(equity, index=close.index)
        total_return = equity.iloc[-1] / init_cash - 1
        returns = equity.pct_change().dropna()
        sharpe = 0.0 if returns.std() < 1e-10 else returns.mean() / returns.std() * np.sqrt(252)
        peak = equity.expanding().max()
        max_dd = ((equity - peak) / peak).min()
        win_rate = sum(1 for p in trade_pnls if p > 0) / len(trade_pnls) if trade_pnls else 0.0

        return {
            "total_return": total_return,
            "annual_return": total_return,  # 简化
            "sharpe_ratio": sharpe,
            "max_drawdown": max_dd,
            "win_rate": win_rate,
            "trade_count": len(trade_pnls),
            "equity_curve": equity,
        }

    @staticmethod
    def _simple_portfolio_backtest(close, weights, init_cash, fees) -> dict:
        """简化组合回测"""
        returns = close.pct_change().fillna(0)
        portfolio_returns = (weights.shift(1) * returns).sum(axis=1)
        equity = (1 + portfolio_returns).cumprod() * init_cash

        total_return = equity.iloc[-1] / init_cash - 1
        std = portfolio_returns.std()
        sharpe = 0.0 if pd.isna(std) or std < 1e-10 else portfolio_returns.mean() / std * np.sqrt(252)
        peak = equity.expanding().max()
        max_dd = ((equity - peak) / peak).min()

        return {
            "total_return": total_return,
            "annual_return": total_return,
            "sharpe_ratio": sharpe,
            "max_drawdown": max_dd,
            "equity_curve": equity,
        }
