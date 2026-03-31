# 法律文书标注与判决预测系统

一个基于 Flask 的法律文书处理系统，支持：
- 文书提交与案件管理
- 大模型自动提取标题 / 摘要 / 关键词
- 判决结果预测（多通道）

---

## 1. 当前技术基线（以代码为准）

- Web 框架：Flask 3.x
- ORM：Flask-SQLAlchemy
- 数据库：MySQL（`settings.py` 读取 `.env`）
- 运行入口：`run.py`
- 数据初始化入口：`init_db.py`
- 依赖清单：`requirement.txt`

> 注意：本 README 已按当前仓库代码更新，不再使用早期 `app.py + SQLite` 方案。

---

## 2. 目录结构（简化）

```text
creativity/
├── run.py
├── init_db.py
├── settings.py
├── requirement.txt
├── start.ps1
├── stop.ps1
├── .env.example
└── app/
    ├── __init__.py
    ├── database.py
    ├── index.py
    ├── annotate.py
    ├── statistic.py
    ├── predict.py
    ├── manage.py
    ├── api.py
    └── templates/
```

---

## 3. 环境要求

- Python **3.10.11**（建议使用虚拟环境）
- MySQL 5.7+ / 8.x
- Windows PowerShell（仓库内提供 `start.ps1` / `stop.ps1`）

---

## 4. 首次启动（推荐）

### 4.1 创建并激活虚拟环境（Python 3.10.11）

```powershell
py -3.10 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 4.2 安装依赖

```powershell
pip install -r requirement.txt
```

### 4.3 配置环境变量

```powershell
Copy-Item .env.example .env
```

编辑 `.env`，至少配置：

- 数据库
  - `DB_HOST`
  - `DB_PORT`
  - `DB_USER`
  - `DB_PASSWORD`
  - `DB_NAME`
- Flask
  - `SECRET_KEY`
- 模型（可按你使用的通道配置）
  - `DEEPSEEK_API_KEY`（案件分析）
  - `SILICONFLOW_API_KEY`（官方模型预测通道）

### 4.4 初始化数据库（建库 + 建表 + 历史字段补齐）

```powershell
python init_db.py
```

### 4.5 启动应用

```powershell
python run.py
```

或：

```powershell
.\start.ps1
```

访问：<http://127.0.0.1:5000>

---

## 5. 业务主流程

1. 首页提交文书（`/` -> `/casesubmit`）
2. 后端写入 `cases` 表
3. 调用分析接口：提取标题、类型、摘要、关键词
4. 调用预测接口：写入 `predict_result`
5. 跳转标注页查看结果（`/annotate?case_id=...`）

核心代码位置：
- 提交流程：`app/index.py`
- 分析与预测：`app/api.py`
- 数据模型：`app/database.py`

---

## 6. 判决预测通道

在 `app/api.py` 中统一分发：

- `official_step`：官方现成大模型（硅基流动）
- `self_hosted_lawgpt`：自部署模型（预留）
- `coze_workflow`：Coze 工作流
- `langgraph_workflow`：LangGraph 多步工作流（案件类型路由 + 校验回路）

默认通道来自：`PREDICT_METHOD_DEFAULT`。

---

## 7. 常见问题

### 7.1 端口 5000 被占用

```powershell
.\stop.ps1
```

再启动：

```powershell
.\start.ps1
```

### 7.2 数据库连接失败

检查：
- MySQL 服务已启动
- `.env` 的 `DB_*` 配置正确
- 账号有创建数据库/建表权限

### 7.3 提交后没有预测结果

检查：
- 对应 API Key 已配置
- 文书内容不要过短（建议 > 50 字）
- 观察控制台输出错误信息

---

## 8. 开发建议

- 每次改数据模型后，先运行 `python init_db.py` 再启动。
- 变更配置字段时同步更新 `.env.example`。
- 优先通过 `start.ps1` / `stop.ps1` 统一本地启动流程。

---

## 9. 提示词评测（方案一）

- 已提供离线评测脚本与说明文档：`eval/README.md`
- 可直接执行（20条低token版）：`python eval/run_prompt_eval.py --limit 20 --method official_step --prompt-version v1`
