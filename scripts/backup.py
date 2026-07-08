"""
DuckDB backup — EXPORT DATABASE to a timestamped directory, retain N days.

Runs daily (02:00) via the scheduler. Backs up on every calendar day, not
just trading days, since the database accumulates research artefacts
(decisions, reports, hypotheses) on non-trading days too.

Usage:
    python -m scripts.backup                    # backup now with defaults
    python -m scripts.backup --retain-days 14   # keep 14 days
"""
from __future__ import annotations

import shutil
from datetime import date, timedelta
from pathlib import Path

import duckdb
from loguru import logger

from configs.settings import settings

DEFAULT_BACKUP_ROOT = "/backup/quantagent"
DEFAULT_RETAIN_DAYS = 7


def backup_database(backup_root: str = None,
                    retain_days: int = DEFAULT_RETAIN_DAYS,
                    db_path: str = None) -> dict:
    """
    Back up the DuckDB database via `EXPORT DATABASE`.

    Uses a read-only connection so it is safe to run alongside other readers.
    The export directory is named YYYY-MM-DD under `backup_root`; a re-run on
    the same day overwrites the existing directory.

    Args:
        backup_root: root dir for backups (default /backup/quantagent)
        retain_days: delete backups older than this many days
        db_path: source DB path (default settings.db_path)

    Returns:
        {"backup_path": str, "size_mb": float, "cleaned": [str, ...]}
    """
    backup_root = Path(backup_root or DEFAULT_BACKUP_ROOT)
    db_path = db_path or settings.db_path

    today = date.today()
    backup_dir = backup_root / today.isoformat()

    if backup_dir.exists():
        shutil.rmtree(backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)

    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        conn.execute(f"EXPORT DATABASE '{backup_dir}'")
    finally:
        conn.close()

    size_mb = sum(f.stat().st_size for f in backup_dir.rglob("*") if f.is_file()) / 1e6

    cleaned = clean_old_backups(backup_root, retain_days, keep=today)

    logger.success(f"备份完成: {backup_dir} ({size_mb:.1f} MB), "
                   f"清理 {len(cleaned)} 个旧备份")
    return {
        "backup_path": str(backup_dir),
        "size_mb": round(size_mb, 2),
        "cleaned": cleaned,
    }


def clean_old_backups(backup_root: Path, retain_days: int, keep: date = None) -> list:
    """
    Delete backup directories older than `retain_days`.

    Only directories whose name parses as YYYY-MM-DD are considered, so
    unrelated files/dirs in `backup_root` are left untouched.

    Args:
        backup_root: directory containing dated backup subdirectories
        retain_days: keep backups from the last `retain_days` days
        keep: reference "today" (default date.today())

    Returns:
        list of removed directory names
    """
    keep = keep or date.today()
    removed = []

    if not backup_root.exists():
        return removed

    for entry in sorted(backup_root.iterdir()):
        if not entry.is_dir():
            continue
        try:
            entry_date = date.fromisoformat(entry.name)
        except ValueError:
            continue  # not a dated backup dir
        # Age in days; remove once it reaches retain_days (keep last retain_days days)
        age_days = (keep - entry_date).days
        if age_days >= retain_days:
            shutil.rmtree(entry)
            removed.append(entry.name)

    return removed


def main():
    import argparse
    parser = argparse.ArgumentParser(description="DuckDB 数据库备份")
    parser.add_argument("--backup-root", default=None, help="备份根目录")
    parser.add_argument("--retain-days", type=int, default=DEFAULT_RETAIN_DAYS,
                        help=f"保留天数 (默认 {DEFAULT_RETAIN_DAYS})")
    args = parser.parse_args()

    result = backup_database(
        backup_root=args.backup_root,
        retain_days=args.retain_days,
    )
    print(f"备份路径: {result['backup_path']}")
    print(f"大小: {result['size_mb']} MB")
    print(f"清理旧备份: {result['cleaned'] or '无'}")


if __name__ == "__main__":
    main()
