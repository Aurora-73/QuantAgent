# 安全文档

> 生成日期：2026-07-06 | 最后更新：2026-07-07 | 适用场景：安全与合规说明

---

## 安全架构

### 安全层次

```
网络层 → 应用层 → 数据层 → 用户层
   ↓         ↓         ↓         ↓
 防火墙    认证授权    加密存储    访问控制
```

---

## API Key 管理

### 配置方式

**正确方式**：使用环境变量或配置文件

```bash
# .env 文件（不提交到版本控制）
SENDCHAN_SENDKEY=xxx
```

**错误方式**：硬编码在代码中

```python
# ❌ 错误示例
api_key = "sk-xxx"  # 永远不要这样做！
```

### 安全措施

| 措施 | 说明 |
|------|------|
| **文件权限** | `.env` 文件权限设置为 600（仅所有者可读） |
| **版本控制** | `.env` 加入 `.gitignore` |
| **密钥轮换** | 定期更换 API Key |
| **最小权限** | 使用最小权限的 API Key |

---

## 数据安全

### 数据加密

| 数据类型 | 加密方式 |
|----------|---------|
| **数据库** | DuckDB 加密（可选） |
| **API Key** | 环境变量存储 |
| **日志** | 敏感信息脱敏 |

### 数据脱敏

```python
def mask_api_key(key: str) -> str:
    """脱敏 API Key"""
    if len(key) <= 8:
        return "***"
    return key[:4] + "***" + key[-4:]

# 使用
logger.info(f"API Key: {mask_api_key(api_key)}")
```

### 数据访问控制

| 角色 | 权限 |
|------|------|
| **管理员** | 全部权限 |
| **研究员** | 数据读取、回测 |
| **交易员** | 策略执行、风控查看 |
| **只读用户** | 报告查看 |

---

## 网络安全

### 代理配置

```bash
# 国内访问（AKShare / baostock）
# 不需要代理

# 海外访问（如需拉取外部资源）
export http_proxy="http://127.0.0.1:7890"
export https_proxy="http://127.0.0.1:7890"
```

### 防火墙规则

| 规则 | 说明 |
|------|------|
| 允许出站 | AKShare、baostock |
| 允许入站 | MCP 服务端口 |
| 禁止入站 | 数据库端口 |

---

## 日志安全

### 日志脱敏

```python
import logging

class SensitiveDataFilter(logging.Filter):
    """过滤敏感信息"""
    def filter(self, record):
        message = record.getMessage()
        message = message.replace("sk-", "sk-***")
        message = message.replace("SENDKEY", "***")
        record.msg = message
        return True

# 使用
logger.addFilter(SensitiveDataFilter())
```

### 日志保留

| 日志类型 | 保留期限 |
|----------|---------|
| 应用日志 | 30天 |
| 错误日志 | 90天 |
| 安全日志 | 180天 |

---

## 合规注意事项

### 数据合规

| 数据类型 | 合规要求 |
|----------|---------|
| **行情数据** | 合法获取，不得转发 |
| **基本面数据** | 公开数据，合规使用 |
| **新闻数据** | 版权合规，合理使用 |
| **用户数据** | 隐私保护，加密存储 |

### 交易合规

| 规则 | 说明 |
|------|------|
| **反洗钱** | 监控大额交易 |
| **内幕交易** | 禁止使用内幕信息 |
| **市场操纵** | 禁止操纵市场 |
| **交易时间** | 遵守交易时间规定 |

### 监管要求

| 地区 | 监管机构 | 要求 |
|------|---------|------|
| **中国** | 证监会 | 量化交易备案 |
| **美国** | SEC | 注册投资顾问 |
| **欧盟** | ESMA | MiFID II 合规 |

---

## 安全检查清单

- [ ] API Key 是否硬编码？
- [ ] `.env` 文件是否加入 `.gitignore`？
- [ ] 日志中是否包含敏感信息？
- [ ] 数据库文件权限是否正确？
- [ ] 是否有数据备份策略？
- [ ] 是否有访问控制机制？
- [ ] 是否定期更换 API Key？
- [ ] 是否有安全审计日志？

---

## 最佳实践

### 1. 最小权限原则

只授予必要的权限，避免过度授权。

### 2. 定期审计

定期检查安全配置，发现潜在风险。

### 3. 数据加密

敏感数据加密存储，传输使用 HTTPS。

### 4. 密钥轮换

定期更换 API Key 和密码。

### 5. 安全培训

团队成员了解安全最佳实践。

---

## 参考

- [配置文档](file:///home/edalab/Desktop/cme_code/quant-system/QuantAgent/docs/reference/configuration.md)
- [灾难恢复](file:///home/edalab/Desktop/cme_code/quant-system/QuantAgent/docs/operations/disaster_recovery.md)
