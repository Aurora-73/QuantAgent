"""
报告生成器 — 层级记忆系统

职责：
  - 日报生成 (每日收盘后)
  - 周报生成 (每周五，压缩5份日报)
  - 月报生成 (每月末，压缩4份周报)
  - 季报生成 (每季末，压缩3份月报)

这是 LLM 在量化系统中最有价值的用法之一：
  信息压缩 — 把大量原始信息压缩成可决策的摘要。
"""
import json
from datetime import date, timedelta, datetime
from pathlib import Path

from openai import OpenAI

from configs.settings import settings


class ReportAgent:
    """
    报告生成器

    实现层级记忆的核心逻辑：
    原始数据 → 日报 → 周报 → 月报 → 季报 → 年报

    每一层都在做信息压缩，保留关键决策信息。
    """

    def __init__(self, api_key: str = None, model: str = None,
                 knowledge_dir: str = None):
        self.llm = OpenAI(
            api_key=api_key or settings.openai_api_key,
            base_url=settings.openai_base_url,
        )
        self.model = model or settings.llm_model
        self.knowledge_dir = Path(knowledge_dir or settings.knowledge_dir)

    # ============================================================
    # 日报
    # ============================================================

    def generate_daily_report(self, market_data: dict,
                              events: list[dict] = None,
                              portfolio: dict = None,
                              analyst_notes: dict = None) -> str:
        """
        生成日报

        Args:
            market_data: 市场行情数据
            events: 当日重要事件
            portfolio: 持仓表现
            analyst_notes: 各分析师备注

        Returns:
            Markdown 格式的日报
        """
        prompt = f"""请生成今日量化研究日报（OKF 格式）。

## 市场行情
{json.dumps(market_data, ensure_ascii=False, indent=2)}

## 今日重要事件
{json.dumps(events or [], ensure_ascii=False, indent=2)}

## 持仓表现
{json.dumps(portfolio or {}, ensure_ascii=False, indent=2)}

## 分析师备注
{json.dumps(analyst_notes or {}, ensure_ascii=False, indent=2)}

---

请按以下 8 段结构生成 Markdown 日报，每段以 "## N. 标题" 开头：

## 1. 市场状态
判断当前市场 regime（趋势市/震荡市/极端波动/财报季/政策窗口），给出置信度。

## 2. 行情快照
记录指数点位、涨跌幅、成交额、北向资金等关键数据。

## 3. 因子信号
列出驱动因子（同向因子）和警告因子（反向因子），标注方向和强度。

## 4. 风控检查
总结仓位、回撤、风险等级是否在安全范围内。

## 5. 事件与新闻
摘要当日重要事件，标注其对持仓的潜在影响。

## 6. Wiki 方法论匹配
列出相关的交易方法论框架及其匹配度。

## 7. 预测
给出短期（1-5日）展望和关键观察点。标注 prediction_id。

## 8. 昨日预测验证
如果存在昨日预测，验证其准确性。如果正确，分析原因；如果错误，记录教训。

注意：
- 区分事实（facts）和判断（judgments），不要混为一谈
- 只做客观分析，不做买卖推荐
- 每个判断应有对应的置信度"""

        return self._call_llm_text(prompt)

    # ============================================================
    # 周报
    # ============================================================

    def generate_weekly_report(self, daily_reports: list[str],
                               week_num: int = None) -> str:
        """
        生成周报 (压缩5份日报)

        Args:
            daily_reports: 本周5份日报内容
            week_num: 周数

        Returns:
            Markdown 格式的周报
        """
        if not daily_reports:
            return "本周无日报数据。"

        combined = "\n\n---\n\n".join(
            [f"=== 日报 {i+1} ===\n{r}" for i, r in enumerate(daily_reports)]
        )

        prompt = f"""请阅读本周 {len(daily_reports)} 份日报，生成周报。

本周日报：
{combined[:12000]}

---

请生成 Markdown 格式的周报，包含：
1. 本周市场总结（主线、风格）
2. 热点演变趋势（逐日）
3. 策略表现汇总
4. 本周预测回顾（成功/失败统计）
5. 经验教训
6. 下周展望

这是信息压缩任务：从5份日报中提炼出最有决策价值的信息。"""

        return self._call_llm_text(prompt)

    # ============================================================
    # 月报
    # ============================================================

    def generate_monthly_report(self, weekly_reports: list[str],
                                factor_stats: dict = None) -> str:
        """
        生成月报 (压缩4份周报)

        Args:
            weekly_reports: 本月4份周报
            factor_stats: 因子表现统计

        Returns:
            Markdown 格式的月报
        """
        if not weekly_reports:
            return "本月无周报数据。"

        combined = "\n\n---\n\n".join(
            [f"=== 周报 {i+1} ===\n{r}" for i, r in enumerate(weekly_reports)]
        )

        prompt = f"""请阅读本月 {len(weekly_reports)} 份周报，生成月报。

本月周报：
{combined[:12000]}

因子表现统计：
{json.dumps(factor_stats or {}, ensure_ascii=False, indent=2)}

---

请生成 Markdown 格式的月报，包含：
1. 月度市场总结（大盘走势、行业表现）
2. 最强主线 / 最弱行业
3. 策略收益（月度收益、超额收益）
4. 因子表现评估（IC、ICIR）
5. Regime 变化记录
6. 假设验证结果
7. 经验总结
8. 下月展望"""

        return self._call_llm_text(prompt)

    # ============================================================
    # 季报
    # ============================================================

    def generate_quarterly_report(self, monthly_reports: list[str]) -> str:
        """
        生成季报 (压缩3份月报)
        """
        if not monthly_reports:
            return "本季度无月报数据。"

        combined = "\n\n---\n\n".join(
            [f"=== 月报 {i+1} ===\n{r}" for i, r in enumerate(monthly_reports)]
        )

        prompt = f"""请阅读本季度 {len(monthly_reports)} 份月报，生成季度战略报告。

本季度月报：
{combined[:12000]}

---

请生成 Markdown 格式的季度报告，包含：
1. 季度市场回顾
2. 策略表现评估（收益、回撤、夏普）
3. 因子有效性评估
4. Regime 总结
5. 成功经验 / 失败教训
6. 下季度战略方向
7. 策略调整建议"""

        return self._call_llm_text(prompt)

    # ============================================================
    # 存储
    # ============================================================

    def save_report(self, report_type: str, content: str,
                    report_date: date = None) -> Path:
        """
        保存报告到 knowledge 目录

        Args:
            report_type: daily / weekly / monthly / quarterly / annual
            content: 报告内容
            report_date: 报告日期

        Returns:
            文件路径
        """
        report_date = report_date or date.today()
        dir_path = self.knowledge_dir / report_type
        dir_path.mkdir(parents=True, exist_ok=True)

        if report_type == "daily":
            filename = f"{report_date.isoformat()}.md"
        elif report_type == "weekly":
            week = report_date.isocalendar()[1]
            filename = f"week{week:02d}-{report_date.year}.md"
        elif report_type == "monthly":
            filename = f"{report_date.year}-{report_date.month:02d}.md"
        elif report_type == "quarterly":
            quarter = (report_date.month - 1) // 3 + 1
            filename = f"Q{quarter}-{report_date.year}.md"
        else:
            filename = f"{report_date.year}.md"

        filepath = dir_path / filename
        filepath.write_text(content, encoding="utf-8")
        return filepath

    def load_reports(self, report_type: str, limit: int = 10) -> list[dict]:
        """加载最近的报告"""
        dir_path = self.knowledge_dir / report_type
        if not dir_path.exists():
            return []

        files = sorted(dir_path.glob("*.md"), reverse=True)[:limit]
        result = []
        for f in files:
            result.append({
                "filename": f.stem,
                "content": f.read_text(encoding="utf-8"),
            })
        return result

    # ============================================================
    # 辅助
    # ============================================================

    def _call_llm_text(self, prompt: str) -> str:
        response = self.llm.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "你是一位专业的量化研究员，负责生成研究报告。使用中文，Markdown 格式输出。"},
                {"role": "user", "content": prompt},
            ],
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
        )
        return response.choices[0].message.content
