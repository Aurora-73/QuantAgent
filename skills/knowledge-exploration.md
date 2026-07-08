# 知识探索工作流

---
name: knowledge-exploration
description: 探索知识库中的事件、决策、假设和文档，全面了解投资相关信息
requires_mcp: [search_events, get_recent_events, search_hypotheses, wiki_search, get_social_sentiment, get_recent_decisions, get_decision_accuracy, get_prediction_accuracy, get_knowledge_stats, get_db_stats, run_health_check]
workflow:
  - step: 1
    name: 搜索金融事件
    mcp: search_events
    next: 获取最近事件(get_recent_events)
  - step: 2
    name: 获取最近事件
    mcp: get_recent_events
    next: 搜索投资假设(search_hypotheses)
  - step: 3
    name: 搜索投资假设
    mcp: search_hypotheses
    next: 搜索交易方法论(wiki_search)
  - step: 4
    name: 获取社交情绪
    mcp: get_social_sentiment
    next: 查看决策记录(get_recent_decisions)
  - step: 5
    name: 查询决策准确率
    mcp: get_decision_accuracy
    next: 获取预测准确率(get_prediction_accuracy)
  - step: 6
    name: 查看知识库统计
    mcp: get_knowledge_stats
    next: 完成
---

## 🔄 工作流总览

```
search_events → get_recent_events → search_hypotheses → wiki_search
    (步骤1)         (步骤2)            (步骤3)           (步骤4)
        ↓
get_social_sentiment → get_recent_decisions → get_decision_accuracy
        (步骤5)            (步骤6)               (步骤7)
        ↓
get_prediction_accuracy → get_knowledge_stats
        (步骤8)                 (步骤9)
```

---

## 📋 步骤 1：搜索金融事件

**目的**：查找与特定股票或主题相关的结构化金融事件

**MCP 工具**：`search_events(query)`

**示例调用**：
```
search_events("茅台")
```

**输出解读**：
- 事件列表，包含事件类型、时间、关联股票、摘要等信息

**下一步指引**：
- ✅ 获取到事件：继续步骤2 → 调用 `get_recent_events(count=10)`
- ❌ 无结果：继续步骤2，查看近期所有事件

---

## 📅 步骤 2：获取最近事件

**目的**：了解近期市场动态，发现潜在投资机会

**MCP 工具**：`get_recent_events(count=10)`

**示例调用**：
```
get_recent_events(count=20)
```

**输出解读**：
- 按时间倒序排列的近期事件
- 关注 `event_type` 和 `ticker` 字段

**下一步指引**：
- ✅ 获取到事件：继续步骤3 → 调用 `search_hypotheses(关键词)`

---

## 🧠 步骤 3：搜索投资假设

**目的**：查找已有的投资假设，验证或扩展投资逻辑

**MCP 工具**：`search_hypotheses(query)`

**示例调用**：
```
search_hypotheses("半导体 增长")
```

**输出解读**：
- 相关的投资假设，包含假设描述、验证状态、置信度等

**下一步指引**：
- ✅ 获取到假设：继续步骤4 → 调用 `wiki_search(相关方法论)`

---

## 📚 步骤 4：搜索交易方法论

**目的**：查找相关的方法论文档，完善投资策略

**MCP 工具**：`wiki_search(query)`

**示例调用**：
```
wiki_search("动量策略")
```

**输出解读**：
- 相关的方法论文档，包含策略描述、参数设置、回测结果等

**下一步指引**：
- ✅ 获取到文档：继续步骤5 → 调用 `get_social_sentiment(ticker)`

---

## 💬 步骤 5：获取社交情绪

**目的**：了解市场情绪，辅助投资决策

**MCP 工具**：`get_social_sentiment(ticker)`

**示例调用**：
```
get_social_sentiment("600519")
```

**输出解读**：
- 情绪分数、热度、正面/负面比例等

**下一步指引**：
- ✅ 获取到情绪：继续步骤6 → 调用 `get_recent_decisions(count=10)`
- ❌ 无数据：该股票可能没有足够的社交媒体讨论，跳过此步骤

---

## 📊 步骤 6：查看决策记录

**目的**：了解历史决策，评估决策质量

**MCP 工具**：`get_recent_decisions(count=10)`

**示例调用**：
```
get_recent_decisions(count=10)
```

**输出解读**：
- 决策时间、决策内容、决策结果等

**下一步指引**：
- ✅ 获取到决策：继续步骤7 → 调用 `get_decision_accuracy()`

---

## 🎯 步骤 7：查询决策准确率

**目的**：评估决策记忆的准确率，判断决策质量

**MCP 工具**：`get_decision_accuracy()`

**示例调用**：
```
get_decision_accuracy()
```

**输出解读**：
- 总决策数、正确决策数、准确率等

**下一步指引**：
- ✅ 获取到准确率：继续步骤8 → 调用 `get_prediction_accuracy()`

---

## 🔮 步骤 8：获取预测准确率

**目的**：评估预测准确率，判断预测质量

**MCP 工具**：`get_prediction_accuracy()`

**示例调用**：
```
get_prediction_accuracy()
```

**输出解读**：
- 预测总数、正确预测数、准确率等

**下一步指引**：
- ✅ 获取到准确率：继续步骤9 → 调用 `get_knowledge_stats()`

---

## 📈 步骤 9：查看知识库统计

**目的**：了解知识库整体情况，评估数据覆盖度

**MCP 工具**：`get_knowledge_stats()`

**示例调用**：
```
get_knowledge_stats()
```

**输出解读**：
- 文档数量、事件数量、决策数量等

**下一步指引**：
- ✅ 完成：知识探索流程结束，综合所有信息制定投资决策

---

## 📊 完整工作流示例

```
# 分析某只股票的完整信息
search_events("茅台")
# → 返回: 茅台相关事件列表

get_recent_events(count=10)
# → 返回: 近期事件列表

search_hypotheses("茅台 消费")
# → 返回: 相关投资假设

wiki_search("消费股投资")
# → 返回: 消费股投资方法论

get_social_sentiment("600519")
# → 返回: 社交情绪分析

get_recent_decisions(count=5)
# → 返回: 相关决策记录

get_decision_accuracy()
# → 返回: 决策准确率

# 输出：综合分析报告
```

---

## ❓ 常见问题

**Q**: search_events 返回空怎么办？
**A**: 尝试简化关键词，或使用 `get_recent_events()` 查看近期所有事件

**Q**: wiki_search 返回结果太多怎么办？
**A**: 使用更精确的关键词，如 `"动量策略 参数"`

**Q**: 如何评估决策质量？
**A**: 结合 `get_decision_accuracy()` 和 `get_prediction_accuracy()` 综合评估

**Q**: 社交情绪数据缺失怎么办？
**A**: 该股票可能没有足够的社交媒体讨论，可跳过此步骤
