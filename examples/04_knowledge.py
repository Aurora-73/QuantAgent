"""
示例4：使用知识库

用法：python examples/04_knowledge.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from knowledge.knowledge_base import KnowledgeBase

print("=" * 50)
print("  示例4：使用知识库")
print("=" * 50)
print()

kb = KnowledgeBase()

# 1. 保存日报
print("[1] 保存日报...")
kb.save_report("daily", """
# 每日研究日报 - 2026-06-03

## 市场概况
- 沪深300: 3856.78 (+0.82%)
- 成交额: 12,345亿
- 北向资金: +56.7亿

## 今日热点
1. AI算力板块持续走强
2. 机器人概念活跃
3. 新能源板块回调

## 持仓表现
- 贵州茅台: +1.2%
- 宁德时代: +2.8%
- 立讯精密: +1.5%

## 明日关注
- 中报预告窗口
- 美联储议息会议
""")
print("    ✅ 日报已保存")

# 2. 保存事件
print("\n[2] 保存事件...")
events = [
    {
        "event_type": "业绩预增",
        "ticker": "600519",
        "company": "贵州茅台",
        "detail": "2025Q1 营收增长15%，超市场预期",
        "sentiment": "positive",
    },
    {
        "event_type": "政策利好",
        "ticker": "",
        "company": "",
        "detail": "工信部发布新能源汽车补贴延续政策",
        "sentiment": "positive",
    },
    {
        "event_type": "行业事件",
        "ticker": "",
        "company": "AI板块",
        "detail": "英伟达发布新一代AI芯片，算力需求持续增长",
        "sentiment": "positive",
    },
]
for event in events:
    kb.save_event(event)
print(f"    ✅ 保存了 {len(events)} 个事件")

# 3. 保存假设
print("\n[3] 保存假设...")
kb.save_hypothesis({
    "description": "动量因子在A股短期有效",
    "metrics": ["IC > 0.03", "ICIR > 0.5"],
    "status": "pending",
})
kb.save_hypothesis({
    "description": "北向资金流入>50亿时，次日上涨概率>60%",
    "metrics": ["胜率 > 60%"],
    "status": "pending",
})
print("    ✅ 保存了 2 个假设")

# 4. 保存教训
print("\n[4] 保存教训...")
kb.save_failure({
    "category": "追高",
    "lesson": "连续3天涨停后追入，第4天回调亏损8%",
    "evidence": ["2025-02-15", "2025-03-01"],
})
kb.save_failure({
    "category": "仓位过重",
    "lesson": "单票仓位超过20%，遇到黑天鹅亏损严重",
    "evidence": ["2025-04-10"],
})
print("    ✅ 保存了 2 条教训")

# 5. 查询知识库
print("\n[5] 知识库统计：")
stats = kb.get_stats()
for k, v in stats.items():
    print(f"    {k}: {v}")

# 6. 查询事件
print("\n[6] 查询事件：")
events = kb.load_events()
for e in events:
    print(f"    [{e['event_type']}] {e['company']}: {e['detail'][:40]}")

# 7. 查询假设
print("\n[7] 查询假设：")
hypotheses = kb.load_hypotheses()
for h in hypotheses:
    status_icon = "⏳" if h['status'] == 'pending' else "✅"
    print(f"    {status_icon} {h['description'][:40]}")

# 8. 查询教训
print("\n[8] 查询教训：")
failures = kb.load_failures()
for f in failures:
    print(f"    [{f['category']}] {f['lesson'][:40]}")

print("\n" + "=" * 50)
print("  完成！")
print("=" * 50)
