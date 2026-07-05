"""
qlib 适配器 — 研究层

职责：
  - 封装 qlib 的数据查询、因子计算、模型训练、回测
  - 将 qlib 的 MultiIndex DataFrame 转换为内部类型
  - 只暴露系统需要的方法

设计原则：
  - 业务代码不直接依赖 qlib 的 API
  - 回测结果转换为 BacktestResult
  - 因子结果转换为 FeatureVector
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import pandas as pd

from data.schema import BacktestResult, FeatureVector

# 优先尝试 pip 安装的 qlib，其次尝试源码
try:
    import qlib
    from qlib.data import D
    from qlib.contrib.model.gbdt import LGBModel
    from qlib.workflow import R
    from qlib.workflow.record_temp import SignalRecord, SigAnaRecord, PortAnaRecord
    from qlib.utils import init_instance_by_config
    _HAS_QLIB = True
except ImportError:
    # 尝试从源码导入（需要先编译）
    _QLIB_ROOT = Path(__file__).parent.parent.parent / "_reference" / "qlib"
    if str(_QLIB_ROOT) not in sys.path:
        sys.path.insert(0, str(_QLIB_ROOT))
    try:
        import qlib
        from qlib.data import D
        from qlib.contrib.model.gbdt import LGBModel
        from qlib.workflow import R
        from qlib.workflow.record_temp import SignalRecord, SigAnaRecord, PortAnaRecord
        from qlib.utils import init_instance_by_config
        _HAS_QLIB = True
    except ImportError:
        _HAS_QLIB = False


def is_available() -> bool:
    """qlib 是否可用"""
    return _HAS_QLIB


class QlibAdapter:
    """
    qlib 研究引擎适配器

    所有方法的输入输出都是 data/schema.py 中的类型或标准 Python 类型。
    qlib 的内部对象在适配器边界处转换。
    """

    def __init__(self, provider_uri: str = "~/.qlib/qlib_data/cn_data",
                 region: str = "cn"):
        if not _HAS_QLIB:
            raise ImportError("qlib 未正确安装。请运行: pip install pyqlib")
        self.provider_uri = provider_uri
        self.region = region
        self._initialized = False

    def init(self):
        """初始化 qlib（首次会下载数据）"""
        if not self._initialized:
            qlib.init(provider_uri=self.provider_uri, region=self.region)
            self._initialized = True

    # ----------------------------------------------------------
    # 数据查询
    # ----------------------------------------------------------

    def get_features(self, instruments: str = "csi300",
                     fields: list[str] = None,
                     start_time: str = "2020-01-01",
                     end_time: str = "2025-12-31") -> pd.DataFrame:
        """
        获取特征数据

        Args:
            instruments: 股票池 ("csi300", "csi500", 或具体股票列表)
            fields: 特征表达式列表，如 ["$close", "$volume"]
            start_time: 开始时间
            end_time: 结束时间

        Returns:
            MultiIndex DataFrame (instrument, datetime)
        """
        self.init()
        if fields is None:
            fields = ["$open", "$high", "$low", "$close", "$volume"]
        return D.features(instruments, fields, start_time, end_time)

    def get_instruments(self, market: str = "csi300") -> list:
        """获取股票池"""
        self.init()
        return D.instruments(market)

    def get_calendar(self, start_time: str = None,
                     end_time: str = None) -> list:
        """获取交易日历"""
        self.init()
        return D.calendar(start_time, end_time)

    # ----------------------------------------------------------
    # 因子定义
    # ----------------------------------------------------------

    @staticmethod
    def alpha158_fields() -> list[str]:
        """Alpha158 因子集（qlib 内置的 158 个技术因子）"""
        try:
            from qlib.contrib.data.handler import Alpha158
            handler = Alpha158(instruments="csi300", start_time="2020-01-01")
            return handler.get_feature_config()
        except Exception:
            return [
                "$close/$open - 1",
                "$high/$low - 1",
                "($close - $open)/($high - $low + 1e-8)",
                "$close/Ref($close, 5) - 1",
                "$close/Ref($close, 10) - 1",
                "$close/Ref($close, 20) - 1",
                "Mean($close, 5)/$close - 1",
                "Std($close, 20)",
            ]

    # ----------------------------------------------------------
    # 模型训练
    # ----------------------------------------------------------

    def train_model(self, model_type: str = "lightgbm",
                    dataset_config: dict = None,
                    model_config: dict = None) -> tuple:
        """
        训练模型

        Args:
            model_type: "lightgbm" / "lstm" / "dnn"
            dataset_config: 数据集配置
            model_config: 模型配置

        Returns:
            (model, dataset) 元组
        """
        self.init()

        if model_config is None:
            if model_type == "lightgbm":
                model_config = {
                    "class": "LGBModel",
                    "module_path": "qlib.contrib.model.gbdt",
                    "kwargs": {
                        "loss": "mse",
                        "early_stopping_rounds": 50,
                        "num_boost_round": 1000,
                    },
                }
            elif model_type == "lstm":
                model_config = {
                    "class": "LSTM",
                    "module_path": "qlib.contrib.model.pytorch_lstm",
                    "kwargs": {
                        "d_feat": 6,
                        "hidden_size": 64,
                        "num_layers": 2,
                        "dropout": 0.0,
                        "n_epochs": 200,
                        "lr": 0.001,
                    },
                }

        if dataset_config is None:
            dataset_config = {
                "class": "DatasetH",
                "module_path": "qlib.data.dataset",
                "kwargs": {
                    "handler": {
                        "class": "Alpha158",
                        "module_path": "qlib.contrib.data.handler",
                        "kwargs": {
                            "start_time": "2020-01-01",
                            "end_time": "2023-12-31",
                            "fit_start_time": "2020-01-01",
                            "fit_end_time": "2022-12-31",
                            "instruments": "csi300",
                        },
                    },
                    "segments": {
                        "train": ("2020-01-01", "2022-12-31"),
                        "valid": ("2023-01-01", "2023-06-30"),
                        "test": ("2023-07-01", "2023-12-31"),
                    },
                },
            }

        model = init_instance_by_config(model_config)
        dataset = init_instance_by_config(dataset_config)
        model.fit(dataset)
        return model, dataset

    # ----------------------------------------------------------
    # 回测 — 返回内部类型
    # ----------------------------------------------------------

    def run_backtest(self, model, dataset,
                     start_time: str = "2023-07-01",
                     end_time: str = "2023-12-31",
                     topk: int = 50, n_drop: int = 5,
                     account: float = 1e8) -> BacktestResult:
        """
        运行回测

        Returns:
            内部 BacktestResult 类型
        """
        self.init()

        port_analysis_config = {
            "executor": {
                "class": "SimulatorExecutor",
                "module_path": "qlib.backtest.executor",
                "kwargs": {"time_per_step": "day", "generate_portfolio_metrics": True},
            },
            "strategy": {
                "class": "TopkDropoutStrategy",
                "module_path": "qlib.contrib.strategy.signal_strategy",
                "kwargs": {"signal": (model, dataset), "topk": topk, "n_drop": n_drop},
            },
            "backtest": {
                "start_time": start_time,
                "end_time": end_time,
                "account": account,
                "benchmark": "SH000300",
                "exchange_kwargs": {
                    "freq": "day",
                    "limit_threshold": 0.095,
                    "deal_price": "close",
                    "open_cost": 0.0005,
                    "close_cost": 0.0015,
                    "min_cost": 5,
                },
            },
        }

        with R.start(experiment_name="backtest"):
            recorder = R.get_recorder()

            sr = SignalRecord(model, dataset, recorder)
            sr.generate()

            sar = SigAnaRecord(recorder)
            sar.generate()

            par = PortAnaRecord(recorder, port_analysis_config, "day")
            par.generate()

            metrics = recorder.list_metrics()

            return BacktestResult(
                strategy_id=f"qlib_{model.__class__.__name__}",
                start_date=start_time,
                end_date=end_time,
                total_return=metrics.get("return", 0.0),
                annual_return=metrics.get("annual_return", 0.0),
                sharpe_ratio=metrics.get("ic", 0.0),
                max_drawdown=metrics.get("max_drawdown", 0.0),
                params={"topk": topk, "n_drop": n_drop, "model_type": model.__class__.__name__},
            )
