# 🚀 项目启动指南

## 快速启动

### 1️⃣ **仅运行预测服务**（Web UI）

只需要启动Flask Web服务即可：

```bash
# Windows PowerShell
.\start.ps1

# 或者直接用Python
python run.py
```

访问：http://127.0.0.1:5000

这样启动就是**只跑预测**，不涉及提示词迭代流程。

**包含的功能**：
- 首页（/）
- 预测页面（/predict） - 输入case_id，直接调用模型预测
- 管理页面（/manage） - 查看和管理案件
- 标注页面（/annotate） - 标注预测结果
- 统计页面（/statistic） - 查看统计数据

---

### 2️⃣ **运行提示词迭代流程**（离线CLI）

这是独立的对话框流程，**不在Web服务中运行**：

```bash
# 快速评测（分数决策，不采纳）
python eval/run_greedy_eval.py \
  --case-id 31 \
  --candidate-prompt-file eval/prompts/v2_try1_2.txt \
  --method official_step \
  --repeats 3 \
  --aggregate median \
  --dry-run

# 完整流程（分数+智能体评审，不采纳）
python eval/run_greedy_eval.py \
  --case-id 31 \
  --baseline-prompt-file eval/prompts/v1_baseline.txt \
  --candidate-prompt-file eval/prompts/v2_try1_2.txt \
  --run-review-agent \
  --require-review-acceptable \
  --review-min-score 75 \
  --dry-run

# 真实采纳（通过所有门禁后自动覆盖baseline）
python eval/run_greedy_eval.py \
  --case-id 31 \
  --baseline-prompt-file eval/prompts/v1_baseline.txt \
  --candidate-prompt-file eval/prompts/v2.txt \
  --run-review-agent \
  --require-review-acceptable \
  --auto-adopt
```

---

## 关键配置

所有配置来自 `.env` 文件（见 [.env.example](.env.example)）：

| 配置项 | 用途 | 默认值 |
|--------|------|--------|
| `DB_HOST` | 数据库地址 | 127.0.0.1 |
| `DB_PORT` | 数据库端口 | 3306 |
| `DB_USER` | 数据库用户 | root |
| `DB_PASSWORD` | 数据库密码 | (空) |
| `SILICONFLOW_API_KEY` | 硅基流动API密钥 | (必填) |
| `SILICONFLOW_BASE_URL` | 硅基流动API地址 | https://api.siliconflow.cn/v1 |
| `SILICONFLOW_MODEL` | 使用的模型 | deepseek-ai/DeepSeek-V3.2 |

---

## 启动前准备

### 环境要求
- Python 3.10.11
- MySQL 数据库（已启动）
- 虚拟环境（可选但推荐）

### 1. 配置环境变量

复制 `.env.example` 为 `.env`，填入你的配置：

```bash
cp .env.example .env
```

必填项：
- `SILICONFLOW_API_KEY` - 从硅基流动获取
- `DB_PASSWORD` - MySQL密码

### 2. 安装依赖

```bash
pip install -r requirement.txt
```

### 3. 初始化数据库

```bash
python init_db.py
```

### 4. 启动MySQL

```bash
# Windows
net start MySQL80

# macOS
brew services start mysql

# Linux
sudo service mysql start
```

---

## 工作流对比

### 🟢 生产预测流程（Web服务）
```
用户Web界面 → 输入case_id 
    ↓
/predict 接口 
    ↓
predict_judgement_with_api() 
    ↓
OpenAI预测（1次）
    ↓
返回预测结果
    ↓
显示在网页上
```
**时间**: ~30秒  
**启动**: `python run.py`

---

### 🟡 迭代优化流程（CLI）
```
开发者 → 修改提示词
    ↓
eval/run_greedy_eval.py
    ↓
多轮评测 (repeats=3)
    ↓
分数决策 (分数门禁)
    ↓
智能体评审 (可选)
    ↓
生成报告
    ↓
自动采纳或人工决策
```
**时间**: ~60-120秒  
**启动**: `python eval/run_greedy_eval.py --case-id ...`

---

## 常见场景

### 场景1: 线上演示（只要预测）
```bash
.\start.ps1
# 客户在网页上输入case_id查看预测结果
```

### 场景2: 开发测试（要改提示词）
```bash
# Terminal 1: 启动数据库和Web服务
.\start.ps1

# Terminal 2: 测试新提示词
python eval/run_greedy_eval.py --case-id 31 --candidate-prompt-file eval/prompts/v2.txt --dry-run
```

### 场景3: 生产采纳（确定新提示词要上线）
```bash
python eval/run_greedy_eval.py \
  --case-id 31 \
  --baseline-prompt-file eval/prompts/v1_baseline.txt \
  --candidate-prompt-file eval/prompts/v2.txt \
  --run-review-agent \
  --require-review-acceptable \
  --auto-adopt
# 通过所有门禁后自动覆盖baseline
```

---

## 故障排查

| 问题 | 解决 |
|------|------|
| 端口5000被占用 | start.ps1会自动关闭占用进程 |
| MySQL连接失败 | 检查`.env`中的DB_*配置，确保MySQL已启动 |
| API调用失败 | 检查`SILICONFLOW_API_KEY`是否填正确 |
| 提示词文件不存在 | 确保`--candidate-prompt-file`路径正确 |

---

## 更多信息

- [流程详解](PROCESS_FLOWS.md) - 两大流程的完整对比
- [架构设计](ARCHITECTURE_IMPLEMENTATION.md) - A2A + Skill 的实现
- [评分可靠性](SCORING_AND_REVIEW_RELIABILITY.md) - 为什么要双门禁
- [快速参考](SCORING_QUICK_REFERENCE.md) - 参数矩阵与配置表

---

**一句话总结**：
- 只要预测 → `.\start.ps1`（就这么简单）
- 要迭代优化 → `python eval/run_greedy_eval.py ...`（CLI单独跑）
