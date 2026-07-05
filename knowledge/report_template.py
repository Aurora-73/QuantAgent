"""
OKF 报告元数据 schema + 报告模板

OKF 格式 = YAML frontmatter + 结构化 Markdown body

- YAML frontmatter: 机器可读的元数据（预测追踪、置信度、数据源）
- Markdown body: 人类可读的 8 段结构化报告
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import date, datetime
from typing import Optional

import yaml


# ============================================================
# Factor Signal 子结构
# ============================================================

@dataclass
class FactorSignal:
    """单个因子的信号"""
    value: float
    direction: str = "neutral"   # bullish / bearish / neutral
    strength: str = "weak"       # strong / moderate / weak


# ============================================================
# Wiki Reference 子结构
# ============================================================

@dataclass
class WikiRef:
    """方法论匹配引用"""
    title: str
    score: float = 0.0


# ============================================================
# Data Source 子结构
# ============================================================

@dataclass
class DataSource:
    """数据来源追踪"""
    source: str = ""
    ticker: str = ""
    count: int = 0
    query: str = ""
    version: str = ""


# ============================================================
# OKF Report Metadata (YAML frontmatter)
# ============================================================

@dataclass
class OKFReportMetadata:
    """OKF 报告元数据 — 对应 YAML frontmatter"""
    report_id: str = ""
    report_type: str = "daily_prediction"  # daily_prediction / deep_analysis / thematic / backtest
    ticker: str = ""
    date: str = ""
    market_regime: str = ""                # trend / oscillating / extreme_volatility / earnings_season / policy_window
    regime_confidence: float = 0.0
    input_weights: dict = field(default_factory=dict)
    factors_used: list[str] = field(default_factory=list)
    factor_signals: dict[str, FactorSignal] = field(default_factory=dict)
    wiki_refs: list[WikiRef] = field(default_factory=list)
    overall_confidence: float = 0.0
    risk_level: str = "medium"             # low / medium / high / critical
    risk_engine_passed: bool = True
    prediction_id: str = ""
    previous_prediction_id: str = ""
    previous_prediction_correct: Optional[bool] = None
    facts: list[str] = field(default_factory=list)
    judgments: list[str] = field(default_factory=list)
    data_sources: dict[str, DataSource] = field(default_factory=dict)

    def to_frontmatter(self) -> str:
        """生成 YAML frontmatter 字符串"""
        data = {}
        for k, v in asdict(self).items():
            if v is None or v == "" or v == [] or v == {}:
                continue
            # 处理嵌套 dataclass
            if k == "factor_signals":
                data[k] = {
                    name: asdict(sig) for name, sig in self.factor_signals.items()
                }
            elif k == "wiki_refs":
                data[k] = [asdict(ref) for ref in self.wiki_refs]
            elif k == "data_sources":
                data[k] = {
                    name: asdict(src) for name, src in self.data_sources.items()
                }
            else:
                data[k] = v
        return yaml.dump(data, allow_unicode=True, default_flow_style=False, sort_keys=False)

    @classmethod
    def create(cls, report_type: str = "daily_prediction",
               ticker: str = "", target_date: date = None) -> "OKFReportMetadata":
        """创建新的元数据实例"""
        target_date = target_date or date.today()
        date_str = target_date.isoformat()
        return cls(
            report_id=f"rpt_{date_str.replace('-', '')}_{ticker or 'market'}",
            report_type=report_type,
            ticker=ticker,
            date=date_str,
            prediction_id=f"pred_{date_str.replace('-', '')}_{ticker or 'market'}",
        )


# ============================================================
# Report Body Templates (8 standard sections)
# ============================================================

REPORT_SECTIONS = [
    "market_regime",       # 1. 市场状态
    "price_snapshot",      # 2. 行情快照
    "factor_signals",      # 3. 因子信号
    "risk_check",          # 4. 风控检查
    "events_news",         # 5. 事件与新闻
    "wiki_methodology",    # 6. Wiki 方法论匹配
    "prediction",          # 7. 预测
    "previous_verification",  # 8. 昨日预测验证
]


def render_okf_report(metadata: OKFReportMetadata, body_sections: dict[str, str]) -> str:
    """
    将元数据和正文章节组合为完整的 OKF 报告。

    Args:
        metadata: YAML frontmatter 元数据
        body_sections: {section_key: markdown_content} 映射

    Returns:
        完整的 OKF 格式报告字符串
    """
    parts = ["---"]
    parts.append(metadata.to_frontmatter().rstrip())
    parts.append("---\n")

    # 标题
    ticker_label = f" {metadata.ticker}" if metadata.ticker else ""
    parts.append(f"# {_report_type_label(metadata.report_type)} — {metadata.date}{ticker_label}\n")

    # 按顺序渲染8段
    section_headers = {
        "market_regime": "## 1. 市场状态",
        "price_snapshot": "## 2. 行情快照",
        "factor_signals": "## 3. 因子信号",
        "risk_check": "## 4. 风控检查",
        "events_news": "## 5. 事件与新闻",
        "wiki_methodology": "## 6. Wiki 方法论匹配",
        "prediction": "## 7. 预测",
        "previous_verification": "## 8. 昨日预测验证",
    }

    for key in REPORT_SECTIONS:
        if key in body_sections and body_sections[key]:
            parts.append(section_headers[key])
            parts.append(body_sections[key])
            parts.append("")

    # 页脚
    parts.append("---")
    parts.append(f"*报告生成于 {datetime.now().strftime('%Y-%m-%d %H:%M')} | "
                 f"report_id: `{metadata.report_id}` | "
                 f"prediction_id: `{metadata.prediction_id}`*")

    return "\n".join(parts)


def render_okf_report_json(metadata: OKFReportMetadata,
                           body_sections: dict[str, str]) -> dict:
    """
    生成 OKF 报告的 JSON 表示（供 API 或程序消费）。

    Returns:
        {metadata: {...}, body: {...}}
    """
    meta_dict = {}
    for k, v in asdict(metadata).items():
        if v is None:
            continue
        if k == "factor_signals":
            meta_dict[k] = {
                name: asdict(sig) for name, sig in metadata.factor_signals.items()
            }
        elif k == "wiki_refs":
            meta_dict[k] = [asdict(ref) for ref in metadata.wiki_refs]
        elif k == "data_sources":
            meta_dict[k] = {
                name: asdict(src) for name, src in metadata.data_sources.items()
            }
        else:
            meta_dict[k] = v

    return {
        "metadata": meta_dict,
        "body": body_sections,
    }


def _report_type_label(report_type: str) -> str:
    labels = {
        "daily_prediction": "每日研究日报",
        "deep_analysis": "深度分析报告",
        "thematic": "专题研究报告",
        "backtest": "回测评估报告",
    }
    return labels.get(report_type, "研究报告")
