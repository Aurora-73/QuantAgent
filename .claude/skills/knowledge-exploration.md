# 知识探索工作流

---
name: knowledge-exploration
description: 探索知识库中的事件、决策、假设和文档，全面了解投资相关信息
requires_mcp: [search_events, get_recent_events, search_hypotheses, wiki_search, get_social_sentiment, get_recent_decisions, get_decision_accuracy, get_prediction_accuracy, get_knowledge_stats, get_db_stats, run_health_check]
---

## 步骤 1：搜索金融事件

调用 `search_events(query)` 搜索与特定股票或主题相关的结构化金融事件。

**示例**：
```
search_events("茅台")
```

**输出解读**：返回事件列表，包含事件类型、时间、关联股票、摘要等信息。

---

## 步骤 2：获取最近事件

调用 `get_recent_events(count=10)` 获取最近发生的事件列表。

**示例**：
```
get_recent_events(count=20)
```

**输出解读**：按时间倒序排列的近期事件，关注 `event_type` 和 `ticker` 字段。

---

## 步骤 3：搜索投资假设

调用 `search_hypotheses(query)` 搜索投资假设库。

**示例**：
```
search_hypotheses("半导体 增长")
```

**输出解读**：返回相关的投资假设，包含假设描述、验证状态、置信度等。

---

## 步骤 4：搜索交易方法论

调用 `wiki_search(query)` 搜索交易方法论文档。

**示例**：
```
wiki_search("动量策略")
```

**输出解读**：返回相关的方法论文档，包含策略描述、参数设置、回测结果等。

---

## 步骤 5：获取社交情绪

调用 `get_social_sentiment(ticker)` 获取指定股票的社交情绪分析结果。

**示例**：
```
get_social_sentiment("600519")
```

**输出解读**：包含情绪分数、热度、正面/负面比例等。

---

## 步骤 6：查看决策记录

调用 `get_recent_decisions(count=10)` 获取最近的决策记录。

**示例**：
```
get_recent_decisions(count=10)
```

**输出解读**：包含决策时间、决策内容、决策结果等。

---

## 步骤 7：查询决策准确率

调用 `get_decision_accuracy()` 查询决策记忆的准确率统计。

**示例**：
```
get_decision_accuracy()
```

**输出解读**：包含总决策数、正确决策数、准确率等。

---

## 步骤 8：获取预测准确率

调用 `get_prediction_accuracy()` 获取预测准确率统计。

**示例**：
```
get_prediction_accuracy()
```

**输出解读**：包含预测总数、正确预测数、准确率等。

---

## 步骤 9：查看知识库统计

调用 `get_knowledge_stats()` 获取知识库的整体统计信息。

**示例**：
```
get_knowledge_stats()
```

**输出解读**：包含文档数量、事件数量、决策数量等。

---

## 步骤 10：查看数据库统计

调用 `get_db_stats()` 获取数据库各表的行数统计。

**示例**：
```
get_db_stats()
```

**输出解读**：包含各数据表的行数，用于评估数据覆盖度。

---

## 完整工作流示例

```
# 分析某只股票的完整信息
1. search_events("茅台") → 搜索茅台相关事件
2. get_recent_events(count=10) → 查看近期事件
3. search_hypotheses("茅台 消费") → 搜索相关投资假设
4. wiki_search("消费股投资") → 搜索消费股投资方法论
5. get_social_sentiment("600519") → 获取社交情绪
6. get_recent_decisions(count=5) → 查看相关决策记录
7. get_decision_accuracy() → 评估决策质量
```

---

## 常见问题

**Q**: search_events 返回空怎么办？
**A**: 尝试简化关键词，或使用 `get_recent_events()` 查看近期所有事件

**Q**: wiki_search 返回结果太多怎么办？
**A**: 使用更精确的关键词，如 `"动量策略 参数"`

**Q**: 如何评估决策质量？
**A**: 结合 `get_decision_accuracy()` 和 `get_prediction_accuracy()` 综合评估

**Q**: 社交情绪数据缺失怎么办？
**A**: 该股票可能没有足够的社交媒体讨论，可跳过此步骤
