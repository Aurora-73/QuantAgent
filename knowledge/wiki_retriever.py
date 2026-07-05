"""
Wiki retriever — search OKF methodology wiki entries.

Uses loverMentor-style 5-dimensional scoring:
  1. Title match (keyword overlap)
  2. Keyword match (semantic relevance)
  3. Tag match (category alignment)
  4. Market regime match (applicability to current conditions)
  5. Timeframe match (strategy horizon alignment)

Fallback: ships with built-in core methodology entries so the retriever
is usable even before docs/wiki/ content is populated.

Usage:
    retriever = WikiRetriever()
    results = retriever.search("放量突破 白酒 趋势", regime="trend", top_k=5)
"""
import json
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Optional

from loguru import logger


@dataclass
class WikiEntry:
    """A single wiki methodology entry."""
    title: str
    type: str           # entity / scenario / source / synthesis
    tags: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    market_regime: list[str] = field(default_factory=list)
    timeframe: list[str] = field(default_factory=list)
    content: str = ""
    source: str = ""    # file path or reference

    @property
    def search_text(self) -> str:
        return f"{self.title} {' '.join(self.keywords)} {' '.join(self.tags)} {self.content[:200]}"


# Built-in core wiki entries so the retriever works before docs/wiki/ is populated
_BUILTIN_ENTRIES = [
    WikiEntry(
        title="突破交易",
        type="entity",
        tags=["技术分析", "入场", "趋势"],
        keywords=["突破", "新高", "放量", "阻力位"],
        market_regime=["trend", "oscillating"],
        timeframe=["日线", "周线"],
        content="突破交易是在价格突破关键阻力位或支撑位时入场的方法。核心要素：1) 明确的阻力/支撑位 2) 放量确认 3) 突破后回踩确认。常见于趋势市初期。",
        source="builtin",
    ),
    WikiEntry(
        title="趋势跟踪",
        type="entity",
        tags=["趋势", "动量", "持仓"],
        keywords=["趋势", "均线", "海龟", "跟踪止损"],
        market_regime=["trend"],
        timeframe=["日线", "周线", "月线"],
        content="趋势跟踪是跟随市场趋势方向交易的策略。核心原则：截断亏损，让利润奔跑。常用工具：移动平均线、通道突破、ATR止损。在趋势市中表现最佳。",
        source="builtin",
    ),
    WikiEntry(
        title="均值回归",
        type="entity",
        tags=["反转", "统计套利", "短线"],
        keywords=["均值回归", "布林带", "RSI", "超买超卖", "偏离"],
        market_regime=["oscillating"],
        timeframe=["日线", "60分钟"],
        content="均值回归策略基于价格会回归到统计均值水平的假设。适用于震荡市。常用指标：布林带、RSI超买超卖、标准差偏离。",
        source="builtin",
    ),
    WikiEntry(
        title="动量因子",
        type="entity",
        tags=["因子", "动量", "选股"],
        keywords=["动量", "收益率", "横截面", "时间序列"],
        market_regime=["trend", "oscillating"],
        timeframe=["日线", "周线"],
        content="动量因子衡量资产在过去一段时间的收益持续性。横截面动量比较不同资产间相对强弱，时间序列动量关注自身趋势。A股市场中短期动量（20-60日）效果较好。",
        source="builtin",
    ),
    WikiEntry(
        title="放量突破",
        type="entity",
        tags=["成交量", "突破", "确认"],
        keywords=["放量", "突破", "成交量", "确认"],
        market_regime=["trend", "oscillating"],
        timeframe=["日线"],
        content="放量突破策略要求在价格突破关键位的同时成交量显著放大（通常量比>1.5），以确认突破的有效性。缩量突破往往是假突破。",
        source="builtin",
    ),
    WikiEntry(
        title="资金管理",
        type="entity",
        tags=["风控", "仓位", "凯利公式"],
        keywords=["仓位", "风险", "凯利", "资金管理", "止损"],
        market_regime=["trend", "oscillating", "extreme_volatility"],
        timeframe=["所有"],
        content="资金管理是决定每笔交易投入多少资金的方法论。核心工具：固定比例仓位、凯利公式、风险预算、波动率目标。好的资金管理比好的入场更重要。",
        source="builtin",
    ),
    WikiEntry(
        title="牛市初期布局",
        type="scenario",
        tags=["牛市", "底部", "建仓"],
        keywords=["牛市", "底部", "放量", "政策底", "市场底"],
        market_regime=["trend"],
        timeframe=["周线", "月线"],
        content="牛市初期的特征：1) 政策底领先市场底 2) 成交量从地量逐步恢复 3) 权重股率先企稳。建仓策略：分批建仓，优先配置高beta板块。",
        source="builtin",
    ),
    WikiEntry(
        title="熊市防守",
        type="scenario",
        tags=["熊市", "防守", "减仓"],
        keywords=["熊市", "防守", "现金", "对冲", "债券"],
        market_regime=["extreme_volatility"],
        timeframe=["周线"],
        content="熊市防守策略：1) 降低仓位至30%以下 2) 增配债券/货币基金 3) 不做左侧抄底 4) 关注高股息防御板块。核心是保住本金。",
        source="builtin",
    ),
    WikiEntry(
        title="震荡市应对",
        type="scenario",
        tags=["震荡", "网格", "波段"],
        keywords=["震荡", "区间", "网格", "高抛低吸"],
        market_regime=["oscillating"],
        timeframe=["日线", "60分钟"],
        content="震荡市应对策略：1) 降低趋势策略权重 2) 增加均值回归策略 3) 缩小止损止盈幅度 4) 网格交易适合震荡区间。识别区间上下沿是关键。",
        source="builtin",
    ),
    WikiEntry(
        title="黑天鹅应对",
        type="scenario",
        tags=["黑天鹅", "极端风险", "对冲"],
        keywords=["黑天鹅", "极端", "崩盘", "流动性", "对冲"],
        market_regime=["extreme_volatility"],
        timeframe=["所有"],
        content="黑天鹅事件应对：1) 第一时间减仓（不要等反弹） 2) 检查流动性（避免跌停板无法卖出） 3) 利用期权对冲尾部风险 4) 保持冷静，不恐慌性清仓。",
        source="builtin",
    ),
    WikiEntry(
        title="海龟交易法则",
        type="source",
        tags=["经典", "趋势", "系统化"],
        keywords=["海龟", "趋势跟踪", "唐奇安通道", "ATR", "金字塔加仓"],
        market_regime=["trend"],
        timeframe=["日线", "周线"],
        content="Richard Dennis的海龟交易法则。核心规则：1) 20日/55日突破入场 2) ATR动态仓位 3) 金字塔加仓（最多4次） 4) 10日/20日低点止损。证明了简单的趋势跟踪系统可以盈利。",
        source="builtin",
    ),
    WikiEntry(
        title="笑傲股市 (CAN SLIM)",
        type="source",
        tags=["经典", "成长股", "基本面"],
        keywords=["CAN SLIM", "O'Neil", "杯柄形态", "每股收益", "相对强度"],
        market_regime=["trend"],
        timeframe=["周线"],
        content="William O'Neil的CAN SLIM选股系统。C=当期盈利增长、A=年度盈利增长、N=新产品新变化、S=供需关系、L=领涨股、I=机构持股、M=市场方向。强调技术面和基本面结合。",
        source="builtin",
    ),
]


class WikiRetriever:
    """Search OKF methodology wiki for relevant trading frameworks."""

    def __init__(self, wiki_dir: str = None):
        self.wiki_dir = Path(wiki_dir) if wiki_dir else Path("docs/wiki")
        self.entries: list[WikiEntry] = []
        self._index: dict[str, list[int]] = {}  # token → entry indices
        self._load_entries()

    def _load_entries(self):
        """Load entries from wiki directory, fall back to built-in."""
        loaded = 0

        # Try loading from wiki directory
        if self.wiki_dir.exists():
            for md_file in self.wiki_dir.rglob("*.md"):
                try:
                    entry = self._parse_wiki_file(md_file)
                    if entry:
                        self.entries.append(entry)
                        loaded += 1
                except Exception as e:
                    logger.warning(f"Failed to parse wiki file {md_file}: {e}")

        # Fall back to built-in entries
        if loaded == 0:
            logger.info(f"No wiki files found in {self.wiki_dir}, using {len(_BUILTIN_ENTRIES)} built-in entries")
            self.entries = list(_BUILTIN_ENTRIES)
        else:
            logger.info(f"Loaded {loaded} wiki entries from {self.wiki_dir}")

        self._build_index()

    def _parse_wiki_file(self, filepath: Path) -> Optional[WikiEntry]:
        """Parse an OKF-format wiki markdown file."""
        text = filepath.read_text(encoding="utf-8")

        # Try YAML frontmatter first
        frontmatter = {}
        body = text
        if text.startswith("---"):
            parts = text.split("---", 2)
            if len(parts) >= 3:
                try:
                    import yaml
                    frontmatter = yaml.safe_load(parts[1]) or {}
                except Exception:
                    pass
                body = parts[2]

        title = frontmatter.get("title", filepath.stem)
        return WikiEntry(
            title=title,
            type=frontmatter.get("type", "entity"),
            tags=frontmatter.get("tags", []),
            keywords=frontmatter.get("keywords", []),
            market_regime=frontmatter.get("market_regime", []),
            timeframe=frontmatter.get("timeframe", []),
            content=body.strip(),
            source=str(filepath),
        )

    def _build_index(self):
        """Build inverted index for fast keyword search."""
        self._index = {}
        for i, entry in enumerate(self.entries):
            tokens = set(re.findall(r"[\w一-鿿]+", entry.search_text.lower()))
            for token in tokens:
                if token not in self._index:
                    self._index[token] = []
                self._index[token].append(i)

    def search(self, query: str = "",
               regime: str = None,
               timeframe: str = None,
               entry_type: str = None,
               top_k: int = 5) -> list[tuple[WikiEntry, float]]:
        """
        Search wiki entries using 5-dimensional scoring.

        Args:
            query: Natural language search query
            regime: Current market regime for relevance matching
            timeframe: Target timeframe for relevance matching
            entry_type: Filter by type (entity/scenario/source/synthesis)
            top_k: Number of results to return

        Returns:
            List of (WikiEntry, score) sorted by relevance
        """
        if not self.entries:
            return []

        query_tokens = set(re.findall(r"[\w一-鿿]+", query.lower())) if query else set()

        scored = []
        for i, entry in enumerate(self.entries):
            if entry_type and entry.type != entry_type:
                continue

            score = self._score_entry(entry, i, query_tokens, regime, timeframe)
            if score > 0:
                scored.append((entry, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

    def _score_entry(self, entry: WikiEntry, idx: int,
                     query_tokens: set, regime: str,
                     timeframe: str) -> float:
        """5-dimensional scoring for a wiki entry."""
        scores = []

        # 1. Title match (weight: 0.35)
        if query_tokens:
            title_tokens = set(re.findall(r"[\w一-鿿]+", entry.title.lower()))
            overlap = len(query_tokens & title_tokens)
            if overlap > 0:
                scores.append(0.35 * min(overlap / len(query_tokens), 1.0))

        # 2. Keyword match (weight: 0.25)
        if query_tokens:
            kw_tokens = set()
            for kw in entry.keywords:
                kw_tokens.update(re.findall(r"[\w一-鿿]+", kw.lower()))
            overlap = len(query_tokens & kw_tokens)
            if overlap > 0:
                scores.append(0.25 * min(overlap / len(query_tokens), 1.0))

        # 3. Tag content match (weight: 0.15)
        if query_tokens:
            tag_tokens = set()
            for tag in entry.tags:
                tag_tokens.update(re.findall(r"[\w一-鿿]+", tag.lower()))
            overlap = len(query_tokens & tag_tokens)
            # Also check content
            content_tokens = set(re.findall(r"[\w一-鿿]+", entry.content[:200].lower()))
            content_overlap = len(query_tokens & content_tokens)
            combined = max(overlap, content_overlap * 0.5)
            if combined > 0:
                scores.append(0.15 * min(combined / max(len(query_tokens), 1), 1.0))

        # 4. Market regime match (weight: 0.15)
        if regime and entry.market_regime:
            regime_lower = regime.lower().replace(" ", "_")
            for mr in entry.market_regime:
                if regime_lower in mr.lower() or mr.lower() in regime_lower:
                    scores.append(0.15)
                    break

        # 5. Timeframe match (weight: 0.10)
        if timeframe and entry.timeframe:
            tf_lower = timeframe.lower()
            for tf in entry.timeframe:
                if tf_lower in tf.lower() or "所有" in tf:
                    scores.append(0.10)
                    break

        return sum(scores) if scores else 0.02  # Minimal score for inclusion

    def list_entries(self, entry_type: str = None) -> list[WikiEntry]:
        """List all entries, optionally filtered by type."""
        if entry_type:
            return [e for e in self.entries if e.type == entry_type]
        return list(self.entries)

    def get_entry(self, title: str) -> Optional[WikiEntry]:
        """Get a specific entry by title."""
        for e in self.entries:
            if e.title == title:
                return e
        return None

    def enrich_prompt(self, query: str, regime: str = None,
                      top_k: int = 3) -> str:
        """Generate a prompt enrichment string with relevant methodologies."""
        results = self.search(query, regime=regime, top_k=top_k)
        if not results:
            return ""

        lines = ["## 相关方法论 (Wiki)"]
        for entry, score in results:
            lines.append(f"- **{entry.title}** (匹配度: {score:.2f})")
            if entry.content:
                lines.append(f"  {entry.content[:120]}...")
        return "\n".join(lines)
