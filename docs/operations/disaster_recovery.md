# 灾难恢复

> Quant System 灾难恢复与数据备份说明。

---

## 备份策略

### 数据备份

| 数据类型 | 备份频率 | 保留期限 | 备份方式 |
|----------|---------|---------|---------|
| **数据库** | 每日 | 30天 | 完整备份 |
| **知识库** | 每日 | 90天 | 增量备份 |
| **配置文件** | 每次修改 | 永久 | 版本控制 |
| **回测结果** | 每日 | 30天 | 完整备份 |

### 备份脚本

```bash
#!/bin/bash
# backup.sh - 每日备份脚本

DATE=$(date +%Y%m%d)
BACKUP_DIR="/backup/quant-system"

# 创建备份目录
mkdir -p $BACKUP_DIR/$DATE

# 备份数据库
cp data/quant.duckdb $BACKUP_DIR/$DATE/quant_$DATE.duckdb

# 备份知识库
tar -czf $BACKUP_DIR/$DATE/knowledge_$DATE.tar.gz knowledge/

# 备份配置文件
cp configs/.env $BACKUP_DIR/$DATE/env_$DATE.backup
cp configs/app.yaml $BACKUP_DIR/$DATE/app_$DATE.yaml

# 删除30天前的备份
find $BACKUP_DIR -type d -mtime +30 -exec rm -rf {} \;

echo "备份完成: $BACKUP_DIR/$DATE"
```

---

## 恢复流程

### 数据库恢复

```bash
# 停止所有使用数据库的进程
pkill -f "python.*scripts"

# 恢复数据库
cp /backup/quant-system/20260702/quant_20260702.duckdb data/quant.duckdb

# 验证数据库
python -m scripts health_check
```

### 知识库恢复

```bash
# 恢复知识库
tar -xzf /backup/quant-system/20260702/knowledge_20260702.tar.gz -C ./

# 验证知识库
python -m scripts show-knowledge --type stats
```

### 配置文件恢复

```bash
# 恢复配置文件
cp /backup/quant-system/20260702/env_20260702.backup configs/.env
cp /backup/quant-system/20260702/app_20260702.yaml configs/app.yaml

# 验证配置
python -c "from configs.settings import settings; print('配置加载成功')"
```

---

## 故障演练

### 演练计划

| 演练类型 | 频率 | 参与人员 |
|----------|------|---------|
| **数据库恢复** | 每月 | 运维人员 |
| **知识库恢复** | 每季度 | 研究人员 |
| **配置恢复** | 每季度 | 开发人员 |
| **全系统恢复** | 每年 | 全体人员 |

### 演练步骤

```bash
# 1. 模拟故障
mv data/quant.duckdb data/quant.duckdb.corrupted

# 2. 执行恢复
cp /backup/quant-system/$(date +%Y%m%d -d "-1 day")/quant_*.duckdb data/quant.duckdb

# 3. 验证恢复
python -m scripts health_check

# 4. 记录恢复时间
echo "恢复耗时: $(date -d 'now' -d '2026-07-02 16:00:00' +%s) 秒"

# 5. 恢复原始文件
mv data/quant.duckdb.corrupted data/quant.duckdb
```

### 演练报告

```json
{
  "drill_date": "2026-07-02",
  "drill_type": "database_recovery",
  "start_time": "16:00:00",
  "end_time": "16:05:32",
  "duration": "5m32s",
  "success": true,
  "issues": [],
  "improvements": ["考虑使用增量备份减少恢复时间"]
}
```

---

## 灾难场景

### 场景1：数据库损坏

**现象**：
```log
RuntimeError: Invalid Input Error: IO Error: Could not read from file "quant.duckdb"
```

**恢复步骤**：
1. 停止所有进程
2. 删除损坏的数据库文件
3. 从备份恢复
4. 验证数据完整性

### 场景2：数据过时

**现象**：
```log
WARNING | data.storage: Data is stale (last updated 2026-06-30)
```

**恢复步骤**：
1. 运行数据更新
2. 验证数据新鲜度
3. 检查数据更新任务状态

### 场景3：配置丢失

**现象**：
```log
Error: configs/.env not found
```

**恢复步骤**：
1. 从备份恢复配置文件
2. 验证配置加载
3. 检查版本控制

### 场景4：系统崩溃

**现象**：服务器无法启动

**恢复步骤**：
1. 检查系统状态
2. 重启服务
3. 验证所有模块
4. 检查最近一次任务执行状态

---

## 恢复时间目标

| 场景 | RTO (恢复时间目标) | RPO (恢复点目标) |
|------|------------------|------------------|
| 数据库损坏 | 15分钟 | 1天 |
| 数据过时 | 30分钟 | 1天 |
| 配置丢失 | 5分钟 | 上次修改 |
| 系统崩溃 | 30分钟 | 1天 |

---

## 最佳实践

### 1. 定期备份

每天自动执行备份，确保数据不丢失。

### 2. 验证备份

定期验证备份文件的完整性，避免备份损坏。

### 3. 演练恢复

定期进行故障演练，确保恢复流程有效。

### 4. 异地备份

将备份文件存储在不同位置，避免单点故障。

### 5. 版本控制

配置文件和代码使用版本控制，便于追溯和恢复。

---

## 参考

- [备份脚本](file:///E:/Code/量化交易/quant-system/scripts/backup.py)
- [健康检查](file:///E:/Code/量化交易/quant-system/scripts/health_check.py)
