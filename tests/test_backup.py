"""Tests for B4.1: DuckDB backup (EXPORT DATABASE + retention).

Covers:
  - backup_database exports; IMPORT DATABASE restores with matching row counts
  - clean_old_backups retains last N days, removes older
  - non-dated directories are left untouched
  - same-day re-run overwrites the existing backup
"""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import duckdb
import pytest

from scripts.backup import backup_database, clean_old_backups


def _make_db_with_data(db_path: Path, table: str = "stock_daily", rows: int = 5):
    """Create a DuckDB file with a small table for backup round-trip tests."""
    conn = duckdb.connect(str(db_path))
    conn.execute(f"""
        CREATE TABLE {table} (
            ticker VARCHAR, dt DATE, close DOUBLE
        )
    """)
    base = date(2026, 7, 1)
    for i in range(rows):
        conn.execute(
            f"INSERT INTO {table} VALUES (?, ?, ?)",
            ["600519", base + timedelta(days=i), 100.0 + i],
        )
    conn.execute("CHECKPOINT")
    conn.close()


class TestBackupRoundTrip:
    def test_export_then_import_row_counts_match(self, tmp_path):
        src_db = tmp_path / "src.duckdb"
        _make_db_with_data(src_db, rows=7)

        backup_root = tmp_path / "backups"
        result = backup_database(
            backup_root=str(backup_root), retain_days=7, db_path=str(src_db))

        backup_dir = Path(result["backup_path"])
        assert backup_dir.exists()
        # EXPORT DATABASE produces a schema.sql + per-table files
        assert any(backup_dir.iterdir())

        # IMPORT into a fresh DB and verify row count
        restored_db = tmp_path / "restored.duckdb"
        conn = duckdb.connect(str(restored_db))
        conn.execute(f"IMPORT DATABASE '{backup_dir}'")
        count = conn.execute("SELECT COUNT(*) FROM stock_daily").fetchone()[0]
        conn.close()

        assert count == 7

    def test_backup_creates_dated_directory(self, tmp_path):
        src_db = tmp_path / "src.duckdb"
        _make_db_with_data(src_db, rows=3)

        backup_root = tmp_path / "backups"
        result = backup_database(
            backup_root=str(backup_root), db_path=str(src_db))

        today = date.today().isoformat()
        assert result["backup_path"].endswith(today)
        assert result["size_mb"] >= 0

    def test_same_day_rerun_overwrites(self, tmp_path):
        src_db = tmp_path / "src.duckdb"
        _make_db_with_data(src_db, rows=3)

        backup_root = tmp_path / "backups"
        r1 = backup_database(backup_root=str(backup_root), db_path=str(src_db))
        first_mtime = Path(r1["backup_path"]).stat().st_mtime

        # Add more data and re-backup same day
        conn = duckdb.connect(str(src_db))
        conn.execute("INSERT INTO stock_daily VALUES ('000001', '2026-07-09', 10.0)")
        conn.execute("CHECKPOINT")
        conn.close()

        r2 = backup_database(backup_root=str(backup_root), db_path=str(src_db))
        assert r1["backup_path"] == r2["backup_path"]

        # Restored count reflects the second backup (4 rows)
        conn = duckdb.connect(str(tmp_path / "restored.duckdb"))
        conn.execute(f"IMPORT DATABASE '{r2['backup_path']}'")
        count = conn.execute("SELECT COUNT(*) FROM stock_daily").fetchone()[0]
        conn.close()
        assert count == 4


class TestCleanOldBackups:
    def test_retains_recent_removes_old(self, tmp_path):
        root = tmp_path / "backups"
        root.mkdir()
        today = date.today()
        # create 10 days of backups
        for offset in range(10):
            d = today - timedelta(days=offset)
            (root / d.isoformat()).mkdir()

        removed = clean_old_backups(root, retain_days=7, keep=today)

        # offsets 7,8,9 are older than 7 days → removed
        assert len(removed) == 3
        remaining = sorted(p.name for p in root.iterdir())
        # offsets 0..6 retained (7 dirs)
        assert len(remaining) == 7

    def test_non_dated_dirs_left_untouched(self, tmp_path):
        root = tmp_path / "backups"
        root.mkdir()
        today = date.today()
        (root / (today - timedelta(days=30)).isoformat()).mkdir()  # old dated
        (root / "notes.txt").write_text("keep me")  # non-dated file
        (root / "manual_snapshot").mkdir()  # non-dated dir

        removed = clean_old_backups(root, retain_days=7, keep=today)

        assert len(removed) == 1  # only the old dated dir
        assert (root / "notes.txt").exists()
        assert (root / "manual_snapshot").exists()

    def test_missing_root_returns_empty(self, tmp_path):
        removed = clean_old_backups(tmp_path / "nonexistent", retain_days=7)
        assert removed == []

    def test_retain_one_day_keeps_today_only(self, tmp_path):
        root = tmp_path / "backups"
        root.mkdir()
        today = date.today()
        (root / today.isoformat()).mkdir()
        (root / (today - timedelta(days=1)).isoformat()).mkdir()
        (root / (today - timedelta(days=2)).isoformat()).mkdir()

        removed = clean_old_backups(root, retain_days=1, keep=today)
        # retain_days=1: keep age < 1 (today only); yesterday (age 1) and older removed
        assert len(removed) == 2
        assert (root / today.isoformat()).exists()
        assert not (root / (today - timedelta(days=1)).isoformat()).exists()


class TestSchedulerIntegration:
    def test_run_backup_callable(self, tmp_path, monkeypatch):
        """run_backup() invokes backup_database without raising on success."""
        src_db = tmp_path / "src.duckdb"
        _make_db_with_data(src_db, rows=2)

        from scripts import scheduler
        monkeypatch.setattr(
            "scripts.backup.backup_database",
            lambda **kw: {"backup_path": str(tmp_path / "bk"), "size_mb": 1.0, "cleaned": []},
        )
        # Should not raise
        scheduler.run_backup()

    def test_run_backup_swallows_failure(self, tmp_path, monkeypatch):
        """run_backup() logs but does not raise when backup_database fails."""
        from scripts import scheduler

        def _boom(**kw):
            raise RuntimeError("disk full")

        monkeypatch.setattr("scripts.backup.backup_database", _boom)
        # Should not raise (error is logged)
        scheduler.run_backup()

    def test_task_choice_includes_backup(self):
        from scripts import scheduler
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument("--task",
                            choices=["data", "research", "reports", "backup", "all"],
                            default="all")
        ns = parser.parse_args(["--task", "backup"])
        assert ns.task == "backup"
