"""
知识库 — 层级记忆系统

核心功能：
  1. 日报/周报/月报/季报的存储与检索
  2. 事件数据库 (结构化事件)
  3. 假设库 (待验证假设)
  4. 教训库 (经验教训)
  5. 层级压缩 (日→周→月→季→年)

存储方式：
  - Markdown 文件: 报告内容 (人类可读)
  - DuckDB: 结构化数据 (事件/预测/教训)
  - 向量检索: 语义搜索 (可选，后续接入 ChromaDB)
"""
import json
import uuid
from datetime import date, timedelta, datetime
from pathlib import Path
from typing import Optional

import pandas as pd

from configs.settings import settings


# 状态机定义：假设生命周期
# draft → active → verified → obsolete
# draft → active → invalidated → obsolete
# draft → rejected → obsolete
HYPOTHESIS_TRANSITIONS = {
    "draft": {"active", "rejected"},
    "active": {"verified", "invalidated", "obsolete"},
    "verified": {"obsolete"},
    "invalidated": {"obsolete"},
    "rejected": {"obsolete"},
    "obsolete": set(),  # 终态
}

# 状态机定义：失败案例生命周期
FAILURE_TRANSITIONS = {
    "new": {"reviewed"},
    "reviewed": {"actioned", "archived"},
    "actioned": {"archived"},
    "archived": set(),
}

# 假设的初始状态
HYPOTHESIS_INITIAL_STATUS = "draft"
# 失败案例的初始状态
FAILURE_INITIAL_STATUS = "new"


class StatusError(ValueError):
    """状态转换非法时抛出的异常"""
    pass


class KnowledgeBase:
    """
    知识库

    目录结构：
    knowledge/
      daily/          日报 (Markdown)
      weekly/         周报
      monthly/        月报
      quarterly/      季报
      annual/         年报
      events/         事件数据库 (JSONL)
      hypotheses/     假设库 (JSONL)
      failures/       失败案例 (JSONL)
    """

    def __init__(self, base_dir: str = None):
        if base_dir is None:
            base_dir = settings.knowledge_dir
        self.base_dir = Path(base_dir)
        self.dirs = {
            "daily": self.base_dir / "daily",
            "weekly": self.base_dir / "weekly",
            "monthly": self.base_dir / "monthly",
            "quarterly": self.base_dir / "quarterly",
            "annual": self.base_dir / "annual",
            "events": self.base_dir / "events",
            "hypotheses": self.base_dir / "hypotheses",
            "failures": self.base_dir / "failures",
        }
        for d in self.dirs.values():
            d.mkdir(parents=True, exist_ok=True)

    # ============================================================
    # 报告管理
    # ============================================================

    def save_report(self, report_type, content: str = None,
                    report_date: date = None) -> Path:
        """
        保存报告

        Args:
            report_type: 报告类型字符串，或 ResearchReport 对象
            content: Markdown 内容（当 report_type 为字符串时必填）
            report_date: 报告日期
        """
        # 支持传入 ResearchReport 对象
        if hasattr(report_type, '__dataclass_fields__'):
            rr = report_type
            report_type = rr.report_type
            content = f"# {rr.title}\n\n{rr.summary}\n\n" + \
                      "\n".join(f"- {p}" for p in rr.key_points)
            if rr.risk_flags:
                content += "\n\n## 风险提示\n" + "\n".join(f"- ⚠️ {r}" for r in rr.risk_flags)
            report_date = rr.timestamp.date() if hasattr(rr.timestamp, 'date') else date.today()

        if content is None:
            raise ValueError("content is required when report_type is a string")

        report_date = report_date or date.today()

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
        elif report_type == "annual":
            filename = f"{report_date.year}.md"
        else:
            filename = f"{report_date.isoformat()}.md"

        # 确保目录存在
        dir_path = self.dirs.get(report_type)
        if dir_path is None:
            dir_path = self.base_dir / report_type
            dir_path.mkdir(parents=True, exist_ok=True)

        filepath = dir_path / filename
        filepath.write_text(content, encoding="utf-8")
        return filepath

    def load_report(self, report_type: str, report_date: date = None) -> Optional[str]:
        """加载报告"""
        report_date = report_date or date.today()

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
        elif report_type == "annual":
            filename = f"{report_date.year}.md"
        else:
            return None

        filepath = self.dirs[report_type] / filename
        if filepath.exists():
            return filepath.read_text(encoding="utf-8")
        return None

    def list_reports(self, report_type: str, limit: int = 10) -> list[dict]:
        """列出最近的报告"""
        dir_path = self.dirs[report_type]
        files = sorted(dir_path.glob("*.md"), reverse=True)[:limit]
        return [{"filename": f.stem, "path": str(f)} for f in files]

    def load_daily_range(self, start: date, end: date) -> list[dict]:
        """加载日期范围内的日报"""
        reports = []
        current = start
        while current <= end:
            content = self.load_report("daily", current)
            if content:
                reports.append({"date": current.isoformat(), "content": content})
            current += timedelta(days=1)
        return reports

    # ============================================================
    # 事件管理
    # ============================================================

    def save_event(self, event):
        """
        保存事件

        Args:
            event: Event 对象或 dict
        """
        from dataclasses import asdict
        if hasattr(event, '__dataclass_fields__'):
            event = asdict(event)

        if not isinstance(event, dict):
            raise TypeError(f"Expected dict or dataclass, got {type(event)}")

        event["event_id"] = event.get("event_id", f"evt_{uuid.uuid4().hex[:8]}")
        ts = event.get("timestamp", datetime.now().isoformat())
        if hasattr(ts, 'isoformat'):
            ts = ts.isoformat()
        event["timestamp"] = ts

        # 按日期分文件
        date_str = str(event["timestamp"])[:10]
        filepath = self.dirs["events"] / f"{date_str}.jsonl"

        with open(filepath, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False, default=str) + "\n")

        return event["event_id"]

    def load_events(self, start_date: str = None,
                    end_date: str = None,
                    event_type: str = None,
                    ticker: str = None,
                    limit: int = 100) -> list[dict]:
        """加载事件"""
        events = []

        for filepath in sorted(self.dirs["events"].glob("*.jsonl")):
            file_date = filepath.stem
            if start_date and file_date < start_date:
                continue
            if end_date and file_date > end_date:
                continue

            with open(filepath, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        event = json.loads(line)
                        if event_type and event.get("event_type") != event_type:
                            continue
                        if ticker and event.get("symbol") != ticker and event.get("ticker") != ticker:
                            continue
                        events.append(event)
                    except json.JSONDecodeError:
                        continue

            if len(events) >= limit:
                break

        return events[:limit]

    # ============================================================
    # 假设管理
    # ============================================================

    def save_hypothesis(self, hypothesis: dict) -> str:
        """保存假设"""
        hypothesis["id"] = hypothesis.get("id", f"hyp_{uuid.uuid4().hex[:8]}")
        hypothesis["created_date"] = hypothesis.get("created_date", date.today().isoformat())
        hypothesis["status"] = hypothesis.get("status", HYPOTHESIS_INITIAL_STATUS)

        filepath = self.dirs["hypotheses"] / "hypotheses.jsonl"
        with open(filepath, "a", encoding="utf-8") as f:
            f.write(json.dumps(hypothesis, ensure_ascii=False) + "\n")

        return hypothesis["id"]

    def load_hypotheses(self, status: str = None) -> list[dict]:
        """加载假设"""
        filepath = self.dirs["hypotheses"] / "hypotheses.jsonl"
        if not filepath.exists():
            return []

        hypotheses = []
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    h = json.loads(line)
                    if status and h.get("status") != status:
                        continue
                    hypotheses.append(h)
                except json.JSONDecodeError:
                    continue

        return hypotheses

    # ============================================================
    # 失败案例管理
    # ============================================================

    def save_failure(self, failure: dict) -> str:
        """保存失败案例"""
        failure["id"] = failure.get("id", f"fail_{uuid.uuid4().hex[:8]}")
        failure["date"] = failure.get("date", date.today().isoformat())
        failure["status"] = failure.get("status", FAILURE_INITIAL_STATUS)

        filepath = self.dirs["failures"] / "failures.jsonl"
        with open(filepath, "a", encoding="utf-8") as f:
            f.write(json.dumps(failure, ensure_ascii=False) + "\n")

        return failure["id"]

    def load_failures(self, category: str = None,
                      status: str = None,
                      limit: int = 50) -> list[dict]:
        """加载失败案例"""
        filepath = self.dirs["failures"] / "failures.jsonl"
        if not filepath.exists():
            return []

        failures = []
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    fail = json.loads(line)
                    if category and fail.get("category") != category:
                        continue
                    if status and fail.get("status") != status:
                        continue
                    failures.append(fail)
                except json.JSONDecodeError:
                    continue

        return failures[:limit]

    # ============================================================
    # 假设状态管理
    # ============================================================

    def set_hypothesis_status(self, hypothesis_id: str, new_status: str) -> dict:
        """
        更新假设状态，带转换验证。

        Args:
            hypothesis_id: 假设 ID
            new_status: 目标状态

        Returns:
            更新后的假设 dict

        Raises:
            StatusError: 非法状态转换
            ValueError: 假设不存在
        """
        filepath = self.dirs["hypotheses"] / "hypotheses.jsonl"
        if not filepath.exists():
            raise ValueError(f"假设 {hypothesis_id} 不存在")

        records = []
        found = None
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                if record.get("id") == hypothesis_id:
                    old_status = record.get("status", HYPOTHESIS_INITIAL_STATUS)
                    allowed = HYPOTHESIS_TRANSITIONS.get(old_status, set())
                    if new_status not in allowed:
                        raise StatusError(
                            f"非法状态转换: {old_status} -> {new_status}，"
                            f"允许的目标: {allowed or '(无，终态)'}"
                        )
                    record["status"] = new_status
                    record["updated_date"] = date.today().isoformat()
                    found = record
                records.append(record)

        if found is None:
            raise ValueError(f"假设 {hypothesis_id} 不存在")

        with open(filepath, "w", encoding="utf-8") as f:
            for record in records:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

        return found

    def load_hypotheses_by_status(self, status: str) -> list[dict]:
        """按状态加载假设"""
        return self.load_hypotheses(status=status)

    def get_hypothesis_stats(self) -> dict:
        """获取假设状态分布"""
        all_hypotheses = self.load_hypotheses()
        stats = {"total": len(all_hypotheses)}
        for h in all_hypotheses:
            s = h.get("status", "unknown")
            stats[s] = stats.get(s, 0) + 1
        return stats

    # ============================================================
    # 失败案例状态管理
    # ============================================================

    def set_failure_status(self, failure_id: str, new_status: str) -> dict:
        """
        更新失败案例状态，带转换验证。

        Args:
            failure_id: 失败案例 ID
            new_status: 目标状态

        Returns:
            更新后的失败案例 dict

        Raises:
            StatusError: 非法状态转换
            ValueError: 失败案例不存在
        """
        filepath = self.dirs["failures"] / "failures.jsonl"
        if not filepath.exists():
            raise ValueError(f"失败案例 {failure_id} 不存在")

        records = []
        found = None
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                if record.get("id") == failure_id:
                    old_status = record.get("status", FAILURE_INITIAL_STATUS)
                    allowed = FAILURE_TRANSITIONS.get(old_status, set())
                    if new_status not in allowed:
                        raise StatusError(
                            f"非法状态转换: {old_status} -> {new_status}，"
                            f"允许的目标: {allowed or '(无，终态)'}"
                        )
                    record["status"] = new_status
                    record["updated_date"] = date.today().isoformat()
                    found = record
                records.append(record)

        if found is None:
            raise ValueError(f"失败案例 {failure_id} 不存在")

        with open(filepath, "w", encoding="utf-8") as f:
            for record in records:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

        return found

    def load_failures_by_status(self, status: str) -> list[dict]:
        """按状态加载失败案例"""
        return self.load_failures(status=status, limit=9999)

    def get_failure_stats(self) -> dict:
        """获取失败案例状态分布"""
        all_failures = self.load_failures()
        stats = {"total": len(all_failures)}
        for f in all_failures:
            s = f.get("status", "unknown")
            stats[s] = stats.get(s, 0) + 1
        return stats

    # ============================================================
    # 层级压缩
    # ============================================================

    def get_week_daily_reports(self, year: int, week: int) -> list[str]:
        """获取某周的所有日报内容"""
        start = date.fromisocalendar(year, week, 1)
        end = date.fromisocalendar(year, week, 7)
        reports = self.load_daily_range(start, end)
        return [r["content"] for r in reports]

    def get_month_weekly_reports(self, year: int, month: int) -> list[str]:
        """获取某月的所有周报内容"""
        import calendar
        weeks = set()
        _, last_day = calendar.monthrange(year, month)
        for day in range(1, last_day + 1):
            d = date(year, month, day)
            weeks.add(d.isocalendar()[1])

        reports = []
        for week in sorted(weeks):
            content = self.load_report("weekly")
            if content:
                reports.append(content)
        return reports

    def get_quarter_monthly_reports(self, year: int, quarter: int) -> list[str]:
        """获取某季的所有月报内容"""
        months = [(quarter - 1) * 3 + i for i in range(1, 4)]
        reports = []
        for month in months:
            content = self.load_report("monthly", date(year, month, 1))
            if content:
                reports.append(content)
        return reports

    # ============================================================
    # 统计
    # ============================================================

    def get_stats(self) -> dict:
        """获取知识库统计"""
        stats = {}
        for name, dir_path in self.dirs.items():
            if name in ["events", "hypotheses", "failures"]:
                # JSONL 文件，计算行数
                count = 0
                for f in dir_path.glob("*.jsonl"):
                    with open(f, encoding="utf-8") as fh:
                        count += sum(1 for line in fh if line.strip())
                stats[name] = count
            else:
                # Markdown 文件
                stats[name] = len(list(dir_path.glob("*.md")))
        return stats
