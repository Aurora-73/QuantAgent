#!/usr/bin/env python
"""MCP 协议功能测试 — 通过 JSON-RPC (stdin/stdout) 测试全部 MCP 工具。

用法:
    python -m scripts.mcp_protocol_test            # 测试全部工具
    python -m scripts.mcp_protocol_test --json      # 输出 JSON 结果
    python -m scripts.mcp_protocol_test --only get_quote,get_history  # 只测指定工具

退出码: 0=全部通过, 1=有失败, 2=协议错误（无法连接 server）
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

# ---------- 测试参数：每个工具的安全默认参数 ----------
# 写操作一律 dry_run=True，避免污染数据库
TEST_PARAMS: dict[str, dict] = {
    # ===== tools_data.py (20) =====
    "get_quote": {"ticker": "600519"},
    "get_history": {"ticker": "600519", "days": 5},
    "get_factors": {"ticker": "600519", "factor_name": "momentum_20d"},
    "get_index_data": {"index_code": "000300", "days": 5},
    "get_universe": {},
    "get_market_overview": {},
    "search_tickers": {"query": "茅台"},
    "get_calendar": {"year": 0},
    "run_factor_evaluation": {"ticker": "600519", "factor_name": "momentum_20d"},
    "update_data": {"universe": "csi300", "dry_run": True},
    "get_sector_list": {"sector_type": "concept"},
    "get_sector_stocks": {"sector_name": "半导体", "sector_type": "concept"},
    "get_sector_index": {"sector_name": "半导体", "sector_type": "concept", "days": 5},
    "run_daily_research": {"dry_run": True},
    "get_financials": {"ticker": "600519", "report_type": "balance"},
    "get_latest_financials": {"ticker": "600519"},
    "update_financials": {"ticker": "600519", "dry_run": True},
    "check_data_freshness": {},
    "update_data_incremental": {"tickers": "600519", "dry_run": True},
    "get_factor_collinearity": {"tickers": "600519", "days": 30},
    # ===== tools_risk.py (10) =====
    "run_stress_test": {"ticker": "600519"},
    "run_brinson_attribution": {
        "portfolio_weights": '{"白酒":0.4}',
        "benchmark_weights": '{"白酒":0.3}',
        "portfolio_returns": '{"白酒":0.02}',
        "benchmark_returns": '{"白酒":0.01}',
    },
    "run_decay_detection": {"ticker": "600519"},
    "get_risk_report": {"ticker": "600519"},
    "list_strategies": {},
    "get_strategy_config": {"strategy_name": "momentum"},
    "run_backtest": {"strategy": "momentum", "ticker": "600519", "dry_run": True},
    "compare_backtest_runs": {"limit": 3},
    "run_health_check": {},
    "get_market_regime": {"days": 30},
    # ===== tools_knowledge.py (13) =====
    "get_daily_report": {},
    "search_events": {"ticker": "600519", "days": 7},
    "wiki_search": {"query": "动量", "top_k": 1},
    "get_knowledge_stats": {},
    "get_recent_events": {"limit": 5},
    "get_decision_accuracy": {"days": 30},
    "get_recent_decisions": {"limit": 5},
    "get_prediction_accuracy": {"days": 30},
    "get_db_stats": {},
    "get_social_sentiment": {"days": 1},
    "search_hypotheses": {"limit": 5},
    "get_higher_order_report": {"report_type": "weekly"},
    "generate_higher_order_report": {"report_type": "weekly", "dry_run": True},
    # ===== tools_committee.py (5) =====
    "review_data_quality": {"ticker": "600519"},
    "review_strategy_signals": {"ticker": "600519", "signals_json": '{"600519": 0.3}'},
    "review_risk_exposure": {
        "ticker": "600519",
        "signals_json": '{"600519": 0.3}',
        "portfolio_json": '{"max_drawdown": -0.03, "total_value": 1000000}',
    },
    "review_decision_history": {"ticker": "600519", "days": 30},
    "compute_committee_consensus": {
        "votes_json": '[{"agent":"DataAgent","action":"bullish","confidence":0.9,"reason":"test","risk_flags":[]}]'
    },
}

TOOL_TIMEOUT = 90  # 单工具超时秒数

# 这些工具返回 "error" 键但属于"数据缺失"而非工具故障，不算失败
NO_DATA_OK = {
    "get_daily_report",       # 当天未生成日报
    "get_sector_stocks",      # 板块数据源不可用
    "get_sector_index",       # 依赖板块成分股
    "get_financials",         # 可能无财务数据
    "search_events",          # 可能无事件
    "search_hypotheses",      # 可能无假设
    "get_decision_accuracy",  # 可能无决策记录
    "get_prediction_accuracy", # 可能无预测记录
}


class MCPProtocolClient:
    """通过 stdin/stdout 与 MCP server 通信的简易客户端。"""

    def __init__(self, project_root: Path, python_bin: str):
        self._id = 0
        env = os.environ.copy()
        env["PYTHONPATH"] = str(project_root)
        env["MCP_LOG_LEVEL"] = "ERROR"
        self.proc = subprocess.Popen(
            [python_bin, "-m", "mcp_server.server"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            cwd=str(project_root),
            env=env,
        )

    def _next_id(self) -> int:
        self._id += 1
        return self._id

    def _send(self, method: str, params: dict | None = None, *, notification: bool = False):
        msg: dict = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            msg["params"] = params
        if not notification:
            msg["id"] = self._next_id()
        line = json.dumps(msg, ensure_ascii=False)
        self.proc.stdin.write(line + "\n")
        self.proc.stdin.flush()
        if notification:
            return None
        return self._read_response()

    def _read_response(self, timeout: float = TOOL_TIMEOUT):
        deadline = time.time() + timeout
        while True:
            remaining = deadline - time.time()
            if remaining <= 0:
                raise TimeoutError(f"读取响应超时 ({timeout}s)")
            line = self.proc.stdout.readline()
            if not line:
                # 进程可能已退出
                err = ""
                if self.proc.poll() is not None:
                    err = self.proc.stderr.read() or ""
                raise ConnectionError(f"server 已关闭 stdout。stderr: {err[:500]}")
            line = line.strip()
            if not line:
                continue
            # 跳过非 JSON 行（日志等）
            if not line.startswith("{"):
                continue
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue

    def initialize(self):
        return self._send(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "mcp-protocol-test", "version": "1.0"},
            },
        )

    def notify_initialized(self):
        return self._send("notifications/initialized", notification=True)

    def list_tools(self):
        return self._send("tools/list", {})

    def call_tool(self, name: str, arguments: dict):
        return self._send("tools/call", {"name": name, "arguments": arguments})

    def close(self):
        try:
            self.proc.terminate()
            self.proc.wait(timeout=5)
        except Exception:
            self.proc.kill()


def run_tests(only: list[str] | None = None, output_json: bool = False):
    project_root = Path(__file__).resolve().parent.parent
    python_bin = str(project_root / ".venv" / "bin" / "python")

    client = MCPProtocolClient(project_root, python_bin)
    results: list[dict] = []

    try:
        # 1. initialize
        init_resp = client.initialize()
        if "error" in init_resp:
            print(f"❌ initialize 失败: {init_resp['error']}", file=sys.stderr)
            return 2
        client.notify_initialized()

        # 2. tools/list — 获取 server 实际注册的工具
        list_resp = client.list_tools()
        if "error" in list_resp:
            print(f"❌ tools/list 失败: {list_resp['error']}", file=sys.stderr)
            return 2
        server_tools = {t["name"] for t in list_resp.get("result", {}).get("tools", [])}

        # 3. 确定测试集
        if only:
            test_set = [t for t in only if t in TEST_PARAMS]
        else:
            test_set = list(TEST_PARAMS.keys())

        # 4. 逐个调用工具
        for i, name in enumerate(test_set, 1):
            args = TEST_PARAMS[name]
            result_entry = {"tool": name, "args": args, "status": "pending",
                            "latency_ms": 0, "error": "", "snippet": ""}
            t0 = time.time()
            try:
                resp = client.call_tool(name, args)
                elapsed = (time.time() - t0) * 1000
                result_entry["latency_ms"] = round(elapsed)

                if "error" in resp:
                    result_entry["status"] = "rpc_error"
                    result_entry["error"] = str(resp["error"])[:200]
                else:
                    content = resp.get("result", {}).get("content", [])
                    is_error = resp.get("result", {}).get("isError", False)
                    text = ""
                    if content and isinstance(content, list):
                        text = content[0].get("text", "") if content else ""
                    # 判断成功：响应文本中不含 "error" 键，或 is_error=False
                    has_error = is_error
                    if not has_error and text:
                        try:
                            parsed = json.loads(text)
                            if isinstance(parsed, dict) and "error" in parsed:
                                has_error = True
                        except (json.JSONDecodeError, TypeError):
                            pass
                    # 数据缺失不算工具失败（工具本身工作正常）
                    if has_error and name in NO_DATA_OK:
                        has_error = False
                        result_entry["status"] = "pass_no_data"
                    else:
                        result_entry["status"] = "fail" if has_error else "pass"
                    result_entry["snippet"] = text[:120].replace("\n", " ")
                    if has_error:
                        result_entry["error"] = text[:200]
            except TimeoutError as e:
                result_entry["status"] = "timeout"
                result_entry["error"] = str(e)
            except Exception as e:
                result_entry["status"] = "error"
                result_entry["error"] = f"{type(e).__name__}: {e}"[:200]

            results.append(result_entry)
            status_icon = {"pass": "✅", "pass_no_data": "⚪", "fail": "❌", "timeout": "⏱️",
                           "error": "💥", "rpc_error": "💥"}.get(result_entry["status"], "?")
            if not output_json:
                print(f"  [{i:2d}/{len(test_set)}] {status_icon} {name:<32s} "
                      f"{result_entry['latency_ms']:>7.0f}ms  {result_entry['snippet'][:60]}")

    finally:
        client.close()

    # 5. 汇总
    passed = sum(1 for r in results if r["status"] == "pass")
    no_data = sum(1 for r in results if r["status"] == "pass_no_data")
    failed = sum(1 for r in results if r["status"] == "fail")
    errors = sum(1 for r in results if r["status"] in ("error", "rpc_error", "timeout"))
    untested = server_tools - set(TEST_PARAMS.keys())

    if output_json:
        print(json.dumps({
            "total": len(results), "passed": passed, "pass_no_data": no_data,
            "failed": failed, "errors": errors, "server_tool_count": len(server_tools),
            "untested": sorted(untested), "results": results,
        }, ensure_ascii=False, indent=2))
    else:
        print(f"\n{'='*70}")
        print(f"总计 {len(results)} 个工具：✅ {passed} 通过  ⚪ {no_data} 无数据  ❌ {failed} 失败  💥 {errors} 错误")
        if untested:
            print(f"⚠️  server 有 {len(untested)} 个工具未在测试脚本中覆盖: {sorted(untested)}")
        if failed or errors:
            print(f"\n失败/错误详情:")
            for r in results:
                if r["status"] not in ("pass", "pass_no_data"):
                    print(f"  {r['tool']}: [{r['status']}] {r['error'][:150]}")
        print(f"{'='*70}")

    return 0 if (passed + no_data == len(results) and not untested) else 1


def main():
    only = None
    output_json = False
    args = sys.argv[1:]
    if "--json" in args:
        output_json = True
        args.remove("--json")
    if "--only" in args:
        idx = args.index("--only")
        only = args[idx + 1].split(",")
        args = args[:idx] + args[idx + 2:]
    sys.exit(run_tests(only=only, output_json=output_json))


if __name__ == "__main__":
    main()
