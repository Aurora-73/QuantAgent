# Good First Issues

> 适合新手贡献者的入门任务列表
>
> 难度：⭐ 简单 | ⭐⭐ 中等 | ⭐⭐⭐ 较难

---

## 📊 数据层

### 1. 添加新数据源适配器
**难度**：⭐⭐

参考 `data/provider.py`，添加新的数据源适配器（如 Tushare、JoinQuant）。

- 创建 `data/adapters/tushare_adapter.py`
- 实现 `get_stock_daily()`、`get_financials()` 等方法
- 在 `DataProvider` 中注册新适配器

**参考文件**：[provider.py](file:///home/edalab/Desktop/cme_code/quant-system/QuantAgent/data/provider.py)

---

### 2. 完善数据清洗规则
**难度**：⭐

参考 `data/cleaner.py`，添加更多数据清洗规则：
- 处理停牌数据
- 添加涨跌停限制检查
- 完善复权处理逻辑

**参考文件**：[cleaner.py](file:///home/edalab/Desktop/cme_code/quant-system/QuantAgent/data/cleaner.py)

---

## 📈 策略层

### 3. 实现反转策略
**难度**：⭐⭐

参考 `strategies/momentum/strategy.py`，实现反转策略：
- 基于 `reversal_5d` / `reversal_20d` 因子
- 策略逻辑：买入近期下跌的股票，卖出近期上涨的股票

**参考文件**：[momentum/strategy.py](file:///home/edalab/Desktop/cme_code/quant-system/QuantAgent/strategies/momentum/strategy.py)

---

### 4. 实现均值回归策略
**难度**：⭐⭐

基于布林带指标实现均值回归策略：
- 当价格接近下轨时买入
- 当价格接近上轨时卖出
- 使用 `bollinger_position` 因子

**参考文件**：[factors.py](file:///home/edalab/Desktop/cme_code/quant-system/QuantAgent/research/factors.py)

---

## 🔧 MCP 工具层

### 5. 添加新 MCP 工具
**难度**：⭐

参考 `mcp_server/tools_data.py`，添加新的 MCP 工具：
- `get_dividend_history` - 获取分红历史
- `get_stock_financial_ratios` - 获取财务比率
- `get_top_gainers` - 获取涨幅榜

**参考文件**：[tools_data.py](file:///home/edalab/Desktop/cme_code/quant-system/QuantAgent/mcp_server/tools_data.py)

---

### 6. 完善 MCP 工具文档
**难度**：⭐

为现有 MCP 工具添加更详细的文档：
- 完善参数说明
- 添加输入输出示例
- 补充异常处理说明

**参考文件**：[tools_data.py](file:///home/edalab/Desktop/cme_code/quant-system/QuantAgent/mcp_server/tools_data.py)、[tools_risk.py](file:///home/edalab/Desktop/cme_code/quant-system/QuantAgent/mcp_server/tools_risk.py)、[tools_knowledge.py](file:///home/edalab/Desktop/cme_code/quant-system/QuantAgent/mcp_server/tools_knowledge.py)

---

## 🧪 测试层

### 7. 添加单元测试
**难度**：⭐

为以下模块添加单元测试：
- `data/sectors.py` - 板块数据模块
- `knowledge/wiki_retriever.py` - 维基检索模块
- `research/evaluator.py` - 因子评估模块

**参考文件**：[tests/](file:///home/edalab/Desktop/cme_code/quant-system/QuantAgent/tests)

---

### 8. 添加 MCP 工具集成测试
**难度**：⭐⭐

创建端到端测试脚本，验证 MCP 工具链：
- 测试 `update_data` → `run_daily_research` → `get_daily_report` 流程
- 测试 `get_sector_stocks` → `get_sector_index` → `get_history` 流程

**参考文件**：[todo/mcp-protocol-testing.md](file:///home/edalab/Desktop/cme_code/quant-system/todo/mcp-protocol-testing.md)

---

## 📖 文档

### 9. 完善 Skill 工作流文档
**难度**：⭐

为每个 Skill 文档添加更多示例：
- 添加实际运行示例输出
- 补充边界情况处理说明
- 添加常见错误及解决方案

**参考文件**：[skills/](file:///home/edalab/Desktop/cme_code/quant-system/QuantAgent/skills)

---

### 10. 添加策略开发教程
**难度**：⭐⭐

创建详细的策略开发教程文档：
- 策略开发完整流程
- 因子选择与组合策略
- 回测与验证方法
- 常见陷阱与避坑指南

**参考文件**：[development/strategy_development.md](file:///home/edalab/Desktop/cme_code/quant-system/QuantAgent/docs/development/strategy_development.md)

---

## 🚀 快速上手指南

### 如何开始贡献

1. **Fork 项目** → 创建功能分支
2. **选择任务** → 从上面列表中选择一个你感兴趣的任务
3. **阅读参考文件** → 了解现有代码结构
4. **实现功能** → 遵循项目代码风格
5. **运行测试** → `pytest` 确保没有破坏现有功能
6. **提交 PR** → 描述你的改动和测试结果

### 代码风格

- 代码格式：Black + Ruff
- 测试框架：pytest
- 提交信息：Conventional Commits 格式

### 提问与交流

- 在 GitHub Discussions 中讨论策略和使用问题
- 遇到困难可以在 Issue 中提问，我们会尽力帮助！