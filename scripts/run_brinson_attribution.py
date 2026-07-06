"""
Brinson 收益归因脚本

用法：
    python -m scripts.run_brinson_attribution --portfolio sector_weights.json --benchmark csi300

将投资组合超额收益分解为: 配置效应 + 选股效应 + 交互效应。
"""
import sys
import argparse
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from data.storage import DataStorage
from risk.attribution import BrinsonAttribution


def main():
    parser = argparse.ArgumentParser(description="Brinson 收益归因")
    parser.add_argument("--portfolio", default=None,
                       help="组合权重 JSON: '{\"sector1\":0.4,\"sector2\":0.3}' "
                            "或 JSON 文件路径")
    parser.add_argument("--benchmark", default="csi300",
                       help="基准名称 (csi300 或自定义 JSON 权重)")
    parser.add_argument("--portfolio-returns", default=None,
                       help="组合各板块收益率 JSON")
    parser.add_argument("--benchmark-returns", default=None,
                       help="基准各板块收益率 JSON")
    args = parser.parse_args()

    # 使用示例数据运行演示
    if not args.portfolio or not args.portfolio_returns:
        logger.info("使用示例数据演示 Brinson 归因...")

        # CSI300 行业权重（近似值）
        benchmark_weights = {
            "金融": 0.22, "信息技术": 0.16, "工业": 0.14,
            "消费": 0.13, "医疗": 0.10, "材料": 0.09,
            "能源": 0.05, "地产": 0.04, "公用事业": 0.04, "通信": 0.03,
        }

        # 模拟组合权重（超配信息技术、低配金融）
        portfolio_weights = {
            "金融": 0.15, "信息技术": 0.25, "工业": 0.14,
            "消费": 0.13, "医疗": 0.12, "材料": 0.07,
            "能源": 0.04, "地产": 0.03, "公用事业": 0.04, "通信": 0.03,
        }

        # 模拟各板块收益率
        benchmark_returns = {
            "金融": 0.01, "信息技术": 0.05, "工业": 0.02,
            "消费": 0.03, "医疗": -0.01, "材料": 0.01,
            "能源": -0.02, "地产": -0.03, "公用事业": 0.0, "通信": 0.02,
        }
        portfolio_returns = benchmark_returns.copy()
    else:
        # 从参数解析
        def parse_json_arg(val):
            if val.startswith("{") or val.startswith("["):
                return json.loads(val)
            else:
                with open(val, encoding="utf-8") as f:
                    return json.load(f)

        portfolio_weights = parse_json_arg(args.portfolio)
        benchmark_weights = parse_json_arg(args.benchmark) if args.benchmark.startswith("{") else {
            "金融": 0.22, "信息技术": 0.16, "工业": 0.14,
            "消费": 0.13, "医疗": 0.10, "材料": 0.09,
            "能源": 0.05, "地产": 0.04, "公用事业": 0.04, "通信": 0.03,
        }
        portfolio_returns = parse_json_arg(args.portfolio_returns or '{}')
        benchmark_returns = parse_json_arg(args.benchmark_returns or json.dumps(portfolio_returns))

    attribution = BrinsonAttribution()
    result = attribution.attribute(
        portfolio_weights=portfolio_weights,
        benchmark_weights=benchmark_weights,
        portfolio_returns=portfolio_returns,
        benchmark_returns=benchmark_returns,
    )

    logger.info(f"{'='*60}")
    logger.info(f" Brinson 收益归因")
    logger.info(f"{'='*60}")
    logger.info(f"  总超额收益:     {result.total_excess_return:+.4%}")
    logger.info(f"  配置效应 (AR):  {result.allocation_effect:+.4%}")
    logger.info(f"  选股效应 (SR):  {result.selection_effect:+.4%}")
    logger.info(f"  交互效应 (IR):  {result.interaction_effect:+.4%}")
    logger.info(f"  合计:           {result.sum_of_parts:+.4%}")
    logger.info(f"{'='*60}")

    if result.sector_details:
        logger.info(f"\n  行业明细:")
        logger.info(f"  {'行业':<12s} {'配置效应':>10s} {'选股效应':>10s} {'合计':>10s}")
        logger.info(f"  {'-'*44}")
        for det in result.sector_details:
            logger.info(f"  {det.get('sector', ''):<12s} {det.get('allocation', 0):>+10.4%} "
                       f"{det.get('selection', 0):>+10.4%} "
                       f"{det.get('interaction', 0):>+10.4%}")

    logger.info(f"\n解读:")
    if abs(result.allocation_effect) > abs(result.selection_effect):
        logger.info(f"  → 超额收益主要来自行业配置能力")
    else:
        logger.info(f"  → 超额收益主要来自选股能力")

    sys.exit(0)


if __name__ == "__main__":
    main()
