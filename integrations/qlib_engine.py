"""
Qlib 集成 — 研究层核心引擎

直接使用 qlib 的：
  - 数据 API (D 对象)
  - 表达式引擎 (因子定义)
  - 模型库 (LightGBM, LSTM 等)
  - 回测框架 (TopkDropoutStrategy 等)
  - 实验管理 (R 对象)

不重复实现 qlib 已有的功能。

适配器:
  QlibResearchAdapter — 实现 ResearchEngine 接口
  QlibEngine — 旧接口，保留向后兼容
"""
import warnings
import sys
from pathlib import Path
from typing import Optional

import pandas as pd

from loguru import logger

from integrations.base import ResearchEngine

# 将 qlib 源码加入 path
QLIB_ROOT = Path(__file__).parent.parent.parent / "_reference" / "qlib"
if str(QLIB_ROOT) not in sys.path:
    sys.path.insert(0, str(QLIB_ROOT))

try:
    import qlib
    from qlib.data import D
    from qlib.data.ops import (
        Ref, Mean, Std, Sum, Max, Min, EMA, WMA, Rank, Delta,
        Corr, Abs, Sign, Log, If,
    )
    from qlib.contrib.model.gbdt import LGBModel
    from qlib.contrib.model.pytorch_lstm import LSTM
    from qlib.contrib.model.pytorch_nn import DNNModelPytorch
    from qlib.contrib.strategy.signal_strategy import TopkDropoutStrategy
    from qlib.backtest import backtest as qlib_backtest
    from qlib.workflow import R
    from qlib.workflow.record_temp import SignalRecord, SigAnaRecord, PortAnaRecord
    from qlib.utils import init_instance_by_config
    HAS_QLIB = True
except ImportError as e:
    HAS_QLIB = False
    logger.warning(f"qlib 导入失败: {e}")


class QlibResearchAdapter(ResearchEngine):
    """
    Qlib 研究适配器 — 实现统一的 ResearchEngine 接口

    用法:
        adapter = QlibResearchAdapter()
        adapter.init()
        features = adapter.get_features("csi300")
        result = adapter.backtest(model, dataset)
    """

    def __init__(self, provider_uri: str = "~/.qlib/qlib_data/cn_data",
                 region: str = "cn"):
        if not HAS_QLIB:
            raise ImportError("qlib 未正确安装")
        self.provider_uri = provider_uri
        self.region = region
        self._engine = None

    def init(self):
        if self._engine is None:
            self._engine = QlibEngine(self.provider_uri, self.region)
            self._engine.init()

    def get_features(self, instruments="csi300", fields=None,
                     start_time="2020-01-01", end_time="2025-12-31") -> pd.DataFrame:
        self.init()
        return self._engine.get_features(instruments, fields, start_time, end_time)

    def backtest(self, model, dataset, **kwargs) -> dict:
        self.init()
        return self._engine.run_backtest(model, dataset, **kwargs)


class QlibEngine:
    """
    Qlib 研究引擎

    提供：
    1. 数据查询 (行情、因子)
    2. 因子定义与计算
    3. 模型训练与预测
    4. 回测评估
    5. 实验管理

    已弃用: 请使用 QlibResearchAdapter 替代。
    """

    def __init__(self, provider_uri: str = "~/.qlib/qlib_data/cn_data",
                 region: str = "cn"):
        warnings.warn(
            "QlibEngine 已弃用，请使用 QlibResearchAdapter（实现统一的 ResearchEngine 接口）",
            DeprecationWarning, stacklevel=2,
        )
        if not HAS_QLIB:
            raise ImportError("qlib 未正确安装")

        self.provider_uri = provider_uri
        self.region = region
        self._initialized = False

    def init(self):
        """初始化 qlib"""
        if not self._initialized:
            qlib.init(
                provider_uri=self.provider_uri,
                region=self.region,
            )
            self._initialized = True
            logger.success("qlib 初始化完成")

    # ============================================================
    # 数据查询
    # ============================================================

    def get_features(self, instruments: str = "csi300",
                     fields: list[str] = None,
                     start_time: str = "2020-01-01",
                     end_time: str = "2025-12-31") -> pd.DataFrame:
        """
        获取特征数据

        Args:
            instruments: 股票池 ("csi300", "csi500", 或具体股票列表)
            fields: 特征表达式列表，如 ["$close", "$volume", "Ref($close, 5)/$close - 1"]
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

    # ============================================================
    # 因子定义 (使用 qlib 表达式引擎)
    # ============================================================

    @staticmethod
    def define_factor(expression: str, name: str = None) -> str:
        """
        定义因子表达式

        表达式语法：
          $close, $open, $high, $low, $volume
          Mean($close, 5) - 5日均值
          Ref($close, 1) - 1日前收盘价
          $close / Ref($close, 20) - 1 - 20日动量
          Std($close, 20) - 20日标准差

        Args:
            expression: qlib 表达式
            name: 因子名称

        Returns:
            表达式字符串
        """
        return expression

    @staticmethod
    def alpha158_fields() -> list[str]:
        """
        Alpha158 因子集 (qlib 内置的 158 个技术因子)

        包含：K线形态、价格、滚动统计等
        """
        # 从 qlib 的 Alpha158 handler 中获取
        try:
            from qlib.contrib.data.handler import Alpha158
            # 返回其默认的特征列
            handler = Alpha158(instruments="csi300", start_time="2020-01-01")
            return handler.get_feature_config()
        except Exception:
            # 简化版本
            return [
                "$close/$open - 1",           # KMID
                "$high/$low - 1",             # KLEN
                "($close - $open)/($high - $low + 1e-8)",  # KSFT
                "$close/Ref($close, 5) - 1",  # 5日动量
                "$close/Ref($close, 10) - 1", # 10日动量
                "$close/Ref($close, 20) - 1", # 20日动量
                "Mean($close, 5)/$close - 1", # 5日均线偏离
                "Std($close, 20)",            # 20日波动率
            ]

    # ============================================================
    # 模型训练
    # ============================================================

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

        # 默认模型配置
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

        # 默认数据集配置
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

    # ============================================================
    # 回测
    # ============================================================

    def run_backtest(self, model, dataset,
                     start_time: str = "2023-07-01",
                     end_time: str = "2023-12-31",
                     topk: int = 50, n_drop: int = 5,
                     account: float = 1e8) -> dict:
        """
        运行 qlib 回测

        Args:
            model: 训练好的模型
            dataset: 数据集
            start_time: 回测开始时间
            end_time: 回测结束时间
            topk: 持仓数量
            n_drop: 每期调仓替换数量
            account: 初始资金

        Returns:
            回测结果 dict
        """
        self.init()

        port_analysis_config = {
            "executor": {
                "class": "SimulatorExecutor",
                "module_path": "qlib.backtest.executor",
                "kwargs": {
                    "time_per_step": "day",
                    "generate_portfolio_metrics": True,
                },
            },
            "strategy": {
                "class": "TopkDropoutStrategy",
                "module_path": "qlib.contrib.strategy.signal_strategy",
                "kwargs": {
                    "signal": (model, dataset),
                    "topk": topk,
                    "n_drop": n_drop,
                },
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

            # 生成预测信号
            sr = SignalRecord(model, dataset, recorder)
            sr.generate()

            # 信号分析
            sar = SigAnaRecord(recorder)
            sar.generate()

            # 组合回测
            par = PortAnaRecord(recorder, port_analysis_config, "day")
            par.generate()

            # 获取结果
            metrics = recorder.list_metrics()
            return {
                "recorder": recorder,
                "metrics": metrics,
            }
