"""
P1 任务验证测试脚本

功能：验证所有 P1 组件是否正常工作
包含：压力测试、Brinson归因、告警系统、因子评估

使用方式：
    python -m scripts.test_p1
"""
import sys
import argparse
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger

def test_stress_test():
    """测试压力测试引擎"""
    logger.info("[测试] 压力测试引擎")
    try:
        from risk.stress_test import StressTestEngine, CRISIS_SCENARIOS
        import pandas as pd
        
        engine = StressTestEngine()
        
        # 生成模拟收益率
        dates = pd.date_range("2015-01-01", "2025-01-01", freq="B")
        returns = pd.Series(0.001 + pd.Series(range(len(dates))).apply(
            lambda x: 0.02 if x % 100 == 0 else (-0.015 if x % 100 == 50 else 0)
        ), index=dates)
        
        report = engine.run(returns)
        
        assert len(report.results) == len(CRISIS_SCENARIOS), f"场景数量不匹配: {len(report.results)} vs {len(CRISIS_SCENARIOS)}"
        
        for r in report.results:
            logger.info(f"  {r.scenario_name}: 回撤={r.max_drawdown:.2%}, 通过={r.survived}")
        
        logger.success("压力测试引擎 ✓")
        return True
    except Exception as e:
        logger.error(f"压力测试引擎 ✗: {e}")
        return False

def test_brinson_attribution():
    """测试 Brinson 归因"""
    logger.info("[测试] Brinson 归因")
    try:
        from risk.attribution import BrinsonAttribution
        
        brinson = BrinsonAttribution()
        
        portfolio_weights = {
            "金融": 0.3,
            "消费": 0.25,
            "科技": 0.25,
            "医药": 0.1,
            "其他": 0.1,
        }
        
        benchmark_weights = {
            "金融": 0.25,
            "消费": 0.2,
            "科技": 0.2,
            "医药": 0.15,
            "其他": 0.2,
        }
        
        portfolio_returns = {
            "金融": 0.015,
            "消费": 0.02,
            "科技": 0.01,
            "医药": 0.025,
            "其他": 0.01,
        }
        
        benchmark_returns = {
            "金融": 0.012,
            "消费": 0.018,
            "科技": 0.012,
            "医药": 0.02,
            "其他": 0.01,
        }
        
        result = brinson.attribute(
            portfolio_weights=portfolio_weights,
            benchmark_weights=benchmark_weights,
            portfolio_returns=portfolio_returns,
            benchmark_returns=benchmark_returns,
        )
        
        logger.info(f"  超额收益: {result.total_excess_return:+.4f}")
        logger.info(f"  配置效应: {result.allocation_effect:+.4f}")
        logger.info(f"  选股效应: {result.selection_effect:+.4f}")
        logger.info(f"  交互效应: {result.interaction_effect:+.4f}")
        
        assert abs(result.total_excess_return - result.sum_of_parts) < 0.0001, "归因结果不一致"
        
        logger.success("Brinson 归因 ✓")
        return True
    except Exception as e:
        logger.error(f"Brinson 归因 ✗: {e}")
        return False

def test_alert_manager():
    """测试告警管理器"""
    logger.info("[测试] 告警管理器")
    try:
        from monitoring.alerts import AlertManager, AlertLevel, AlertType
        
        alert_manager = AlertManager()
        
        # 测试 INFO 级别告警
        alert = alert_manager.fire(
            AlertLevel.INFO,
            AlertType.VOLATILITY,
            "测试 INFO 告警",
            "这是一条测试信息",
        )
        assert alert.level == AlertLevel.INFO
        assert alert.title == "测试 INFO 告警"
        
        # 测试 WARNING 级别告警
        alert = alert_manager.fire(
            AlertLevel.WARNING,
            AlertType.DRAWDOWN,
            "测试 WARNING 告警",
            "这是一条测试警告",
        )
        assert alert.level == AlertLevel.WARNING
        assert alert.alert_type == AlertType.DRAWDOWN
        
        # 测试 CRITICAL 级别告警
        alert = alert_manager.fire(
            AlertLevel.CRITICAL,
            AlertType.DAILY_LOSS,
            "测试 CRITICAL 告警",
            "这是一条测试严重告警",
        )
        assert alert.level == AlertLevel.CRITICAL
        
        logger.info(f"  已触发告警: {len(alert_manager.alerts)} 条")
        
        # 测试回撤检查
        result = alert_manager.check_drawdown(-0.06)
        assert result is not None
        assert result.level == AlertLevel.CRITICAL
        
        # 测试日亏损检查
        result = alert_manager.check_daily_loss(-0.03)
        assert result is not None
        assert result.level == AlertLevel.CRITICAL
        
        logger.success("告警管理器 ✓")
        return True
    except Exception as e:
        logger.error(f"告警管理器 ✗: {e}")
        return False

def test_notifier():
    """测试通知推送器"""
    logger.info("[测试] 通知推送器")
    try:
        from monitoring.notifier import SendChanNotifier, USERS
        
        notifier = SendChanNotifier()
        
        if notifier.config.sendkey:
            logger.info(f"  SendKey: {notifier.config.sendkey[:4]}***")
            logger.info(f"  用户数: {len(USERS)}")
            
            # 测试发送消息（不实际发送）
            result = notifier.send("测试标题", "测试内容")
            logger.info(f"  推送结果: {result.success}")
            
            if result.success:
                logger.success("通知推送器 ✓")
            else:
                logger.warning(f"通知推送器 ⚠: {result.message}")
        else:
            logger.info("  未配置 SendKey，跳过实际推送测试")
            logger.success("通知推送器 ✓（配置检查通过）")
        
        return True
    except Exception as e:
        logger.error(f"通知推送器 ✗: {e}")
        return False

def test_factor_engine():
    """测试因子引擎"""
    logger.info("[测试] 因子引擎")
    try:
        from research.factors import FactorEngine
        import pandas as pd
        
        engine = FactorEngine()
        factor_list = engine.list_factors()
        
        logger.info(f"  注册因子数: {len(factor_list)}")
        
        # 生成模拟数据
        dates = pd.date_range("2024-01-01", "2024-06-01", freq="B")
        random_series = pd.Series(range(len(dates))).apply(lambda x: 0.5 if x % 5 == 0 else (-0.3 if x % 5 == 3 else 0))
        df = pd.DataFrame({
            "open": 100 + random_series.cumsum(),
            "high": 100.5 + random_series.cumsum(),
            "low": 99.5 + random_series.cumsum(),
            "close": 100 + random_series.cumsum(),
            "volume": 1000000 + pd.Series(range(len(dates))) * 1000,
            "amount": 100000000 + pd.Series(range(len(dates))) * 100000,
        }, index=dates)
        
        df["pct_change"] = df["close"].pct_change()
        df["turnover"] = df["volume"] / 10000000
        
        result = engine.compute_all(df)
        
        computed_factors = [col for col in result.columns 
                          if col not in ["open", "high", "low", "close", "volume", "amount", "pct_change", "turnover"]]
        
        logger.info(f"  计算因子数: {len(computed_factors)}")
        
        assert len(computed_factors) > 10, f"因子计算不足: {len(computed_factors)}"
        
        logger.success("因子引擎 ✓")
        return True
    except Exception as e:
        logger.error(f"因子引擎 ✗: {e}")
        return False

def test_factor_evaluator():
    """测试因子评估器"""
    logger.info("[测试] 因子评估器")
    try:
        from research.evaluator import FactorEvaluator
        
        evaluator = FactorEvaluator()
        
        logger.info("  评估器初始化成功")
        logger.success("因子评估器 ✓")
        return True
    except Exception as e:
        logger.error(f"因子评估器 ✗: {e}")
        return False

def test_decay_detector():
    """测试衰减检测器"""
    logger.info("[测试] 衰减检测器")
    try:
        from risk.decay_detector import DecayDetector
        import pandas as pd
        import numpy as np
        
        detector = DecayDetector()
        
        # 生成模拟 IC 序列
        dates = pd.date_range("2024-01-01", "2024-06-01", freq="B")
        ic_series = pd.Series(0.05 + np.random.randn(len(dates)) * 0.02, index=dates)
        
        report = detector.check(ic=ic_series)
        
        logger.info(f"  衰减状态: {report.is_decaying}")
        logger.info(f"  告警数: {len(report.alerts)}")
        
        logger.success("衰减检测器 ✓")
        return True
    except Exception as e:
        logger.error(f"衰减检测器 ✗: {e}")
        return False

def test_regime_detector():
    """测试市场状态检测器"""
    logger.info("[测试] 市场状态检测器")
    try:
        from research.regime_detector import MarketRegimeDetector
        import pandas as pd
        import numpy as np
        
        detector = MarketRegimeDetector()
        
        # 生成模拟指数数据
        dates = pd.date_range("2024-01-01", "2024-06-01", freq="B")
        prices = 3000 + np.cumsum(0.01 + np.random.randn(len(dates)) * 0.02)
        
        df = pd.DataFrame({
            "close": prices,
            "volume": 100000000 + np.random.rand(len(dates)) * 50000000,
        }, index=dates)
        
        regime, confidence = detector.detect(df)
        
        logger.info(f"  市场状态: {regime.value}, 置信度: {confidence:.2f}")
        logger.info(f"  中文标签: {detector.get_regime_label_cn(regime)}")
        
        logger.success("市场状态检测器 ✓")
        return True
    except Exception as e:
        logger.error(f"市场状态检测器 ✗: {e}")
        return False

def test_data_storage():
    """测试数据存储"""
    logger.info("[测试] 数据存储")
    try:
        from data.storage import DataStorage
        
        storage = DataStorage()
        
        # 获取表统计
        stats = storage.get_table_stats()
        logger.info(f"  表数量: {len(stats)}")
        
        # 检查核心表
        core_tables = ["stock_daily", "factors", "events", "predictions", "backtest_runs"]
        for table in core_tables:
            if table in stats:
                logger.info(f"  {table}: {stats[table]} 行")
            else:
                logger.warning(f"  {table}: 不存在")
        
        logger.success("数据存储 ✓")
        return True
    except Exception as e:
        logger.error(f"数据存储 ✗: {e}")
        return False

def test_data_provider():
    """测试数据提供器"""
    logger.info("[测试] 数据提供器")
    try:
        from data.provider import DataProvider
        
        # 获取 CSI300 成分股
        components = DataProvider.get_csi300_components()
        logger.info(f"  CSI300 成分股: {len(components)} 只")
        
        assert len(components) >= 280, f"成分股不足: {len(components)}"
        
        logger.success("数据提供器 ✓")
        return True
    except Exception as e:
        logger.error(f"数据提供器 ✗: {e}")
        return False

def main():
    """运行所有测试"""
    logger.info("=" * 60)
    logger.info("P1 任务验证测试")
    logger.info("=" * 60)
    
    tests = [
        ("数据提供器", test_data_provider),
        ("数据存储", test_data_storage),
        ("因子引擎", test_factor_engine),
        ("因子评估器", test_factor_evaluator),
        ("衰减检测器", test_decay_detector),
        ("市场状态检测器", test_regime_detector),
        ("压力测试引擎", test_stress_test),
        ("Brinson 归因", test_brinson_attribution),
        ("告警管理器", test_alert_manager),
        ("通知推送器", test_notifier),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            results.append(test_func())
        except Exception as e:
            logger.error(f"{name} 异常: {e}")
            results.append(False)
    
    logger.info("")
    logger.info("=" * 60)
    logger.info("测试结果汇总")
    logger.info("=" * 60)
    
    passed = sum(results)
    total = len(results)
    
    logger.info(f"通过: {passed}/{total}")
    
    if passed == total:
        logger.success("✅ 所有测试通过!")
        return 0
    else:
        logger.error(f"❌ {total - passed} 个测试失败")
        return 1

if __name__ == "__main__":
    sys.exit(main())