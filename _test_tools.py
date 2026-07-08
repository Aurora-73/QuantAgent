"""MCP 工具批量测试脚本"""
import asyncio
import json
import sys
sys.path.insert(0, '.')
from mcp_server.server import mcp


def fmt(text, max_len=1500):
    """Format output for display"""
    if isinstance(text, str):
        try:
            parsed = json.loads(text)
            return json.dumps(parsed, ensure_ascii=False, indent=2)[:max_len]
        except:
            return text[:max_len]
    return str(text)[:max_len]


async def call(name, args={}):
    """Call a tool and return the result text"""
    try:
        content, meta = await mcp.call_tool(name, args)
        # content is a list of TextContent, get the text from first
        raw = content[0].text if hasattr(content[0], 'text') else str(content[0])
        return raw, None
    except Exception as e:
        return None, str(e)


async def test_all():
    results = {}

    # ============ 1. 大盘概况 ============
    print("\n" + "="*60)
    print("📊 1. get_market_overview - 大盘概况")
    print("="*60)
    data, err = await call('get_market_overview', {})
    if err: print(f"  ❌ ERROR: {err}")
    else: print(f"  ✅ {fmt(data)}")

    # ============ 2. 个股行情 ============
    print("\n" + "="*60)
    print("🔍 2. get_quote - 贵州茅台行情")
    print("="*60)
    data, err = await call('get_quote', {'ticker': '600519'})
    if err: print(f"  ❌ ERROR: {err}")
    else: print(f"  ✅ {fmt(data)}")

    # ============ 3. 历史数据 ============
    print("\n" + "="*60)
    print("📈 3. get_history - 平安银行历史数据")
    print("="*60)
    data, err = await call('get_history', {
        'ticker': '000001',
        'start_date': '2026-06-01',
        'end_date': '2026-07-06'
    })
    if err: print(f"  ❌ ERROR: {err}")
    else: print(f"  ✅ 返回 {len(data.split(chr(10)))} 行数据")

    # ============ 4. 指数数据 ============
    print("\n" + "="*60)
    print("📊 4. get_index_data - 沪深300")
    print("="*60)
    data, err = await call('get_index_data', {'index_code': '000300', 'start_date': '2026-06-01', 'end_date': '2026-07-06'})
    if err: print(f"  ❌ ERROR: {err}")
    else: print(f"  ✅ {fmt(data)}")

    # ============ 5. 板块列表 - 新增 ============
    print("\n" + "="*60)
    print("🧩 5. get_sector_list - 板块列表 (新功能)")
    print("="*60)
    data, err = await call('get_sector_list', {'sector_type': 'concept'})
    if err: print(f"  ❌ ERROR: {err}")
    else: print(f"  ✅ {fmt(data)}")

    # ============ 6. 板块成分股 - 新增 ============
    print("\n" + "="*60)
    print("🧩 6. get_sector_stocks - 半导体板块成分股 (新功能)")
    print("="*60)
    data, err = await call('get_sector_stocks', {'sector_name': '半导体'})
    if err: print(f"  ❌ ERROR: {err}")
    else: print(f"  ✅ {fmt(data)}")

    # ============ 7. 板块指数 - 新增 ============
    print("\n" + "="*60)
    print("🧩 7. get_sector_index - 半导体板块指数 (新功能)")
    print("="*60)
    data, err = await call('get_sector_index', {'sector_name': '半导体', 'start_date': '2026-06-01', 'end_date': '2026-07-06'})
    if err: print(f"  ❌ ERROR: {err}")
    else: print(f"  ✅ {fmt(data)}")

    # ============ 8. 健康检查 ============
    print("\n" + "="*60)
    print("🩺 8. run_health_check - 健康检查")
    print("="*60)
    data, err = await call('run_health_check', {})
    if err: print(f"  ❌ ERROR: {err}")
    else: print(f"  ✅ {fmt(data)}")

    # ============ 9. 市场状态 ============
    print("\n" + "="*60)
    print("🌡️  9. get_market_regime - 市场状态")
    print("="*60)
    data, err = await call('get_market_regime', {})
    if err: print(f"  ❌ ERROR: {err}")
    else: print(f"  ✅ {fmt(data)}")

    # ============ 10. 因子评估 ============
    print("\n" + "="*60)
    print("📐 10. run_factor_evaluation - 因子评估")
    print("="*60)
    data, err = await call('run_factor_evaluation', {'start_date': '2026-01-01', 'end_date': '2026-07-06'})
    if err: print(f"  ❌ ERROR: {err}")
    else: print(f"  ✅ {fmt(data)}")

    # ============ 11. 策略列表 ============
    print("\n" + "="*60)
    print("📋 11. list_strategies - 策略列表")
    print("="*60)
    data, err = await call('list_strategies', {})
    if err: print(f"  ❌ ERROR: {err}")
    else: print(f"  ✅ {fmt(data)}")

    # ============ 12. 风险报告 ============
    print("\n" + "="*60)
    print("⚠️  12. get_risk_report - 综合风险报告")
    print("="*60)
    data, err = await call('get_risk_report', {})
    if err: print(f"  ❌ ERROR: {err}")
    else: print(f"  ✅ {fmt(data)}")

    # ============ 13. 搜索股票 ============
    print("\n" + "="*60)
    print("🔎 13. search_tickers - 搜索股票")
    print("="*60)
    data, err = await call('search_tickers', {'keyword': '茅台'})
    if err: print(f"  ❌ ERROR: {err}")
    else: print(f"  ✅ {fmt(data)}")

    # ============ 14. 知识库统计 ============
    print("\n" + "="*60)
    print("📚 14. get_knowledge_stats - 知识库统计")
    print("="*60)
    data, err = await call('get_knowledge_stats', {})
    if err: print(f"  ❌ ERROR: {err}")
    else: print(f"  ✅ {fmt(data)}")

    # ============ 15. 事件搜索 ============
    print("\n" + "="*60)
    print("📰 15. search_events - 搜索事件")
    print("="*60)
    data, err = await call('search_events', {'keyword': '半导体', 'limit': 5})
    if err: print(f"  ❌ ERROR: {err}")
    else: print(f"  ✅ {fmt(data)}")

    # ============ 16. 交易日历 ============
    print("\n" + "="*60)
    print("📅 16. get_calendar - 交易日历")
    print("="*60)
    data, err = await call('get_calendar', {'start_date': '2026-07-01', 'end_date': '2026-07-31'})
    if err: print(f"  ❌ ERROR: {err}")
    else: print(f"  ✅ {fmt(data)}")

    # ============ 17. 数据库统计 ============
    print("\n" + "="*60)
    print("🗄️  17. get_db_stats - 数据库统计")
    print("="*60)
    data, err = await call('get_db_stats', {})
    if err: print(f"  ❌ ERROR: {err}")
    else: print(f"  ✅ {fmt(data)}")

    # ============ 18. 假设搜索 ============
    print("\n" + "="*60)
    print("💡 18. search_hypotheses - 搜索投资假设")
    print("="*60)
    data, err = await call('search_hypotheses', {'keyword': '消费', 'limit': 5})
    if err: print(f"  ❌ ERROR: {err}")
    else: print(f"  ✅ {fmt(data)}")

    print("\n" + "="*60)
    print("🏁 测试完成！")
    print("="*60)


if __name__ == '__main__':
    asyncio.run(test_all())
