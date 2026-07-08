# Issue-001: DuckDB 索引删除失败错误

> ⚠️ 本文档已归档（2026-07-07），内容仅作历史参考。

## 问题描述

在执行 `python -m scripts.update_data --universe csi300` 更新指数数据时，DuckDB 抛出以下错误：

```
Invalid Input Error: Failed to delete all rows from index. Only deleted 0 out of 647 rows.
```

随后导致数据库失效：

```
FATAL Error: Failed: database has been invalidated because of a previous fatal error.
```

## 发现位置

- 文件: `scripts/update_data.py`
- 触发位置: 更新指数数据步骤 ([第60-67行](file:///home/edalab/Desktop/cme_code/quant-system/QuantAgent/scripts/update_data.py#L60-L67))
- 调用方法: `storage.save_index_daily()`

## 初步判断原因

1. **数据库文件损坏**：DuckDB 文件可能在之前的异常终止中损坏
2. **WAL 文件问题**：`quant.duckdb.wal` 文件可能与主数据库不一致
3. **索引状态异常**：主键索引在批量删除时出现状态不一致

## 临时处理方式

1. 删除 WAL 文件强制重建
2. 重新运行数据更新
3. 如果问题持续，考虑备份后重建数据库

## 当前状态

- 股票池：292/300 (缺少8只)
- 指数数据：沪深300和中证500更新失败
- 个股数据：正在更新中，可能部分完成

## 后续处理

1. 修复数据库后重新运行更新
2. 监控是否再次出现此问题
3. 如果反复出现，考虑更换 DuckDB 版本或调整写入策略
