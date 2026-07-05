# 待解决问题

> 已修复的问题请查看 changelog.md

---

## 环境问题

### ⚠️ Windows GBK 编码
- YAML 文件、JSONL 文件读取默认使用 GBK，需显式指定 utf-8
- 修复：open(file, encoding="utf-8")

### ⚠️ 终端乱码
- Windows 终端 GBK 编码无法显示中文日志，文件内容正确
- 修复：Summary 中使用 ASCII 标记 [OK]/[!] 替代 emoji

### ⚠️ 依赖缺失
- AKShare 未安装：venv 中无 akshare，端到端测试无实际数据但流程正常
- vectorbt 未安装：不影响核心功能，回测模块需要

---

## 待观察

---

## 已归档问题

所有已修复的问题已归档到 `changelog.md`
