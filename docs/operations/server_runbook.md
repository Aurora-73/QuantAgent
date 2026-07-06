# 服务器运行手册

> 版本: 1.0 | 更新日期: 2026-07-06 | 适用场景: 服务器端 P1 闭环验证

---

## 一、项目定位

**QuantAgent** 是一个 MCP Server 模式的量化交易研究系统。

- **核心定位**: 提供研究闭环（数据→因子→回测→风控→预测验证）
- **不做什么**: 不直接连接交易所，不做实时交易
- **LLM 边界**: LLM 调用由外部 Agent 通过 MCP 工具完成，本系统不内置 LLM

---

## 二、环境要求

### 2.1 硬件要求

| 指标 | 最低配置 | 推荐配置 |
|------|----------|----------|
| CPU | 4核 | 8核以上 |
| 内存 | 8GB | 16GB以上 |
| 磁盘 | 10GB | 50GB以上（数据库增长） |

### 2.2 软件要求

| 软件 | 版本 | 安装命令 |
|------|------|----------|
| Python | 3.11+ | `python --version` |
| Git | 任意 | `git --version` |
| DuckDB | 内置 | 无需单独安装 |

### 2.3 网络配置

**关键规则**：
- ✅ **国内数据源（AKShare、baostock）必须直连，不走代理**
- ✅ **国外数据/下载才使用代理**

```bash
# 清除代理（国内直连）
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY

# 设置代理（仅国外访问时）
# export http_proxy=http://127.0.0.1:7892
# export https_proxy=http://127.0.0.1:7892
```

---

## 三、项目结构

```
quant-system/
├── data/                  # DuckDB 数据库文件
├── scripts/               # 运行脚本（核心入口）
│   ├── daily_research.py  # 每日研究流程（主流程）
│   ├── run_p1.sh          # P1 完整运行脚本（Linux/Mac）
│   ├── run_p1.bat         # P1 完整运行脚本（Windows）
│   ├── test_p1.py         # P1 组件验证测试
│   ├── update_data.py     # 数据更新
│   ├── compute_factors.py # 因子计算
│   ├── evaluate_factors.py # 因子评估
│   ├── run_stress_test.py # 压力测试
│   ├── run_attribution.py # Brinson 归因
│   ├── health_check.py    # 健康检查
│   └── db_stats.py        # 数据库统计
├── data/                  # 数据层
├── research/              # 研究层
├── risk/                  # 风控层
├── monitoring/            # 监控层
├── knowledge/             # 知识库层
├── mcp_server/            # MCP Server
└── configs/               # 配置文件
```

---

## 四、核心脚本说明

### 4.1 run_p1.sh — P1 完整运行脚本

**用途**: 一键运行完整的 P1 闭环验证流程

**用法**:
```bash
# 运行全部任务（推荐）
bash scripts/run_p1.sh

# 仅更新数据
bash scripts/run_p1.sh --update-only

# 指定日期运行
bash scripts/run_p1.sh --date 2026-07-06
```

**执行流程**:
```
[1/6] 数据更新 (国内直连)
[2/6] 因子批量计算
[3/6] 因子评估 + 衰减检测
[4/6] 压力测试
[5/6] Brinson 归因
[6/6] Daily Research（完整流程）
[验证] 数据库统计
```

### 4.2 daily_research.py — 每日研究主流程

**用途**: 系统核心工作流，包含完整的5步流程

**用法**:
```bash
python -m scripts.daily_research
python -m scripts.daily_research --date 2026-07-06
```

**流程说明**:
| 步骤 | 内容 | 耗时 |
|------|------|------|
| Step 1/5 | 更新行情数据（沪深300成分股） | ~15 min |
| Step 2/5 | 因子计算（33个因子） | ~7 min |
| Step 2.2/5 | 因子评估 + 衰减检测 | ~2 min |
| Step 2.3/5 | 因子中性化 | ~1 min |
| Step 2.4/5 | 压力测试 + Brinson归因 | ~1 min |
| Step 2.5/5 | 市场状态 + 多源融合 | ~1 min |
| Step 3/5 | 新闻采集 + 结构化事件入库 | ~2 min |
| Step 4/5 | 生成日报 | ~30s |
| Step 4.5/5 | 预测追踪 + 决策记忆 | ~1 min |
| Step 5/5 | 统计汇总 | ~30s |

**预计总耗时**: 25-35 分钟

### 4.3 test_p1.py — 组件验证测试

**用途**: 验证所有 P1 组件是否正常工作

**用法**:
```bash
python -m scripts.test_p1
```

**测试内容**:
| 测试项 | 验证目标 |
|--------|----------|
| 数据提供器 | CSI300 成分股数量 >= 280 |
| 数据存储 | 核心表存在且有数据 |
| 因子引擎 | 注册因子数 >= 29 |
| 因子评估器 | 评估器初始化成功 |
| 衰减检测器 | 衰减检测逻辑正常 |
| 市场状态检测器 | 市场状态识别正常 |
| 压力测试引擎 | 4个历史危机场景 |
| Brinson 归因 | 超额收益分解正常 |
| 告警管理器 | 三级告警正常触发 |
| 通知推送器 | 配置检查通过 |

**通过标准**: 10/10 全部通过

### 4.4 health_check.py — 健康检查

**用途**: 快速检查系统状态

**用法**:
```bash
python -m scripts.health_check
```

**检查项**:
- 数据库连接
- 数据时效
- 数据完整性
- 因子覆盖
- 数据源连接
- 回测持久化
- 磁盘空间
- 依赖检查

### 4.5 db_stats.py — 数据库统计

**用途**: 获取数据库各表行数统计

**用法**:
```bash
python -m scripts.db_stats
```

---

## 五、运行步骤

### 5.1 首次部署

```bash
# 1. 克隆项目
git clone git@github.com:Aurora-73/QuantAgent.git
cd QuantAgent/quant-system

# 2. 创建虚拟环境
python -m venv .venv

# 3. 激活虚拟环境
source .venv/bin/activate

# 4. 安装依赖
pip install -r requirements.txt

# 5. 验证环境
python -m scripts.test_p1
```

### 5.2 日常运行

**方式一：使用 run_p1.sh（推荐）**
```bash
source .venv/bin/activate
bash scripts/run_p1.sh
```

**方式二：分步运行**
```bash
source .venv/bin/activate

# 步骤1：数据更新（国内直连）
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY
python -m scripts.update_data --all

# 步骤2：因子计算
python -m scripts.compute_factors --universe csi300

# 步骤3：因子评估
python -m scripts.evaluate_factors --all

# 步骤4：压力测试
python -m scripts.run_stress_test --scenarios all

# 步骤5：Brinson归因
python -m scripts.run_attribution

# 步骤6：每日研究
python -m scripts.daily_research

# 验证
python -m scripts.db_stats
```

### 5.3 后台运行

```bash
# 后台运行，输出到日志文件
nohup bash scripts/run_p1.sh > /tmp/quantagent_p1.log 2>&1 &

# 查看日志
tail -f /tmp/quantagent_p1.log

# 查看进程
ps aux | grep "run_p1.sh"
```

---

## 六、关键配置

### 6.1 SendChan 通知（可选）

用于推送风控告警和任务完成通知。

**配置位置**: `configs/settings.py`

```python
# Server酱配置
sendchan_sendkey_me = "你的SendKey"
sendchan_api_url = "https://sct.ftqq.com/{}.send"
sendchan_status_url = "https://sct.ftqq.com/push"
```

**获取 SendKey**:
1. 访问 https://sct.ftqq.com/
2. 登录后获取 SendKey
3. 在 settings.py 中配置

### 6.2 风控参数

**配置位置**: `configs/settings.py`

```python
# 风控配置
max_single_position = 0.10        # 单票最大仓位 10%
max_sector_exposure = 0.30        # 行业最大暴露 30%
max_total_exposure = 1.0          # 总暴露上限
max_daily_turnover = 0.20         # 日换手率限制 20%
max_drawdown_stop = -0.05         # 最大回撤熔断 5%
daily_loss_limit = -0.02          # 日亏损限额 2%
min_daily_volume = 1000000        # 最小日成交量
volatility_cap = 0.03             # 波动率上限
```

---

## 七、预期结果

### 7.1 数据库增长预期

| 指标 | P0前 | P0后 | P1后预期 |
|------|------|------|----------|
| 股票日线 | 237,907 | 452,146 | ~500,000 |
| 因子行数 | 881,085 | 11,345,102 | ~12,000,000 |
| 事件数 | 56 | 86 | ~100+ |
| 预测数 | 1 | 3 | ~5+ |
| 决策记忆 | 3 | 8 | ~10+ |
| 日报数 | 29 | 30 | ~31+ |
| 因子评估 | 不存在 | 33条 | ~60+ |

### 7.2 运行成功标志

```
✅ 每日研究流程完成
✅ 压力测试完成: 4 个场景
✅ Brinson 归因完成
✅ 告警系统初始化成功
```

### 7.3 健康检查通过标准

```
健康检查完成: 7通过, 1警告, 0失败
警告内容: 数据时效滞后（正常，非交易日）
```

---

## 八、常见问题与排查

### 8.1 数据更新失败

**现象**: AKShare 数据获取超时

**原因**: 代理配置问题

**解决**:
```bash
# 确保国内数据源直连
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY
python -m scripts.update_data --all
```

### 8.2 数据库被占用

**现象**: `IO Error: Cannot open file "data/quant.duckdb"`

**原因**: 有其他进程正在访问数据库

**解决**:
```bash
# 查找并关闭占用进程
lsof | grep "quant.duckdb"
kill -9 <PID>
```

### 8.3 因子评估 IC=N/A

**现象**: 因子评估结果全部为 N/A

**原因**: 样本量不足（评估脚本基于单日截面，需要至少30只股票的连续数据）

**解决**:
- 确保运行完整的沪深300（300只股票）
- 确保数据有足够的历史长度（至少60个交易日）

### 8.4 内存不足

**现象**: 运行过程中 OOM

**解决**:
- 增加服务器内存
- 分批处理股票（修改 daily_research.py 中的批次大小）
- 使用更高效的数据库查询

### 8.5 依赖冲突

**现象**: `RequestsDependencyWarning: urllib3 doesn't match a supported version`

**解决**:
```bash
# 这是警告，不影响运行
# 如果需要消除警告，执行：
pip install --upgrade requests urllib3
```

---

## 九、日志说明

### 9.1 日志级别

| 级别 | 含义 | 示例 |
|------|------|------|
| INFO | 正常信息 | 步骤开始/完成 |
| SUCCESS | 成功完成 | 数据保存成功 |
| WARNING | 警告 | 数据获取失败（继续执行） |
| ERROR | 错误 | 关键步骤失败 |
| DEBUG | 调试 | 详细的执行过程 |

### 9.2 日志文件

默认输出到控制台。如需持久化日志：

```bash
python -m scripts.daily_research > logs/daily_research_$(date +%Y%m%d).log 2>&1
```

---

## 十、任务验收标准

### P1 验收清单

- [ ] 数据更新完成（国内直连）
- [ ] 因子计算完成（300只股票 × 33个因子）
- [ ] 因子评估完成（IC/ICIR 有值）
- [ ] 压力测试完成（4个场景）
- [ ] Brinson 归因完成（超额收益分解）
- [ ] 日报生成完成
- [ ] 预测验证回填完成
- [ ] 数据库统计验证通过
- [ ] health_check 7通过
- [ ] test_p1 10/10 通过

---

## 十一、后续任务

### P2 任务（下一阶段）

| 任务 | 描述 | 优先级 |
|------|------|--------|
| 回测持久化增强 | `--compare` 和 `--output json` | 高 |
| Walk-Forward CLI | 接入 backtest CLI | 高 |
| 数据质量监控 | 因子覆盖率/新鲜度检测 | 中 |
| 策略回测验证 | 4个策略样本外回测 | 中 |
| MCP 写操作工具 | 回测触发、策略配置变更 | 低 |

---

## 十二、联系信息

- **项目地址**: https://github.com/Aurora-73/QuantAgent
- **主流程**: `scripts/daily_research.py`
- **配置文件**: `configs/settings.py`
- **运行脚本**: `scripts/run_p1.sh`

---

*文档结束*
