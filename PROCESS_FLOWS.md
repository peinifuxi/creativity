# 🔄 两大流程系统对比

## 1️⃣ **完整的生产预测流程** (Production Prediction Flow)

### 流程图
```
┌─────────────────────────────────────────────────────────────┐
│ 用户端 (Web)                                               │
│ ┌─ 管理页 (index.html)                                     │
│ ├─ 预测页 (predict.html) ← 主要入口                         │
│ ├─ 管理页 (manage.html)                                     │
│ └─ 统计页 (statistic.html)                                  │
└──────────────────┬──────────────────────────────────────────┘
                   │ HTTP POST /api/predict
                   ▼
┌─────────────────────────────────────────────────────────────┐
│ 后端 Flask 应用 (app/__init__.py)                           │
│ ┌──────────────────────────────────────────────────────┐   │
│ │ 路由: /api/predict (app/api.py)                     │   │
│ │  ├─ 接收: case_id, case_content (或 case_name)     │   │
│ │  └─ 参数: method='official_step' (硬编码)          │   │
│ └──────────────────────────────────────┬──────────────┘   │
│                                        │                   │
│ ┌──────────────────────────────────────▼──────────────┐   │
│ │ predict_judgement_with_api()                       │   │
│ │  ├─ case_id → 查询 Case 模型                       │   │
│ │  ├─ content ← case.content                         │   │
│ │  ├─ case_type ← infer_case_type(case)              │   │
│ │  └─ 确定方法: official_step 或其他                 │   │
│ └──────────────────────────────────────┬──────────────┘   │
│                                        │                   │
│ ┌──────────────────────────────────────▼──────────────┐   │
│ │ _predict_with_official_step()                      │   │
│ │  ├─ _build_prompt()                               │   │
│ │  │  ├─ 确定模板源:                                │   │
│ │  │  │  ├─ 文件模板 (eval/prompts/*.txt)            │   │
│ │  │  │  └─ 内置模板 (DEFAULT_PREDICT_PROMPT)      │   │
│ │  │  ├─ 截断内容: content[:3000]                  │   │
│ │  │  └─ 注入: prompt.format(case_content, type)    │   │
│ │  │                                                 │   │
│ │  ├─ OpenAI API 调用 (官方步骤)                     │   │
│ │  │  ├─ Model: deepseek-r1                         │   │
│ │  │  ├─ Temperature: 0.2                           │   │
│ │  │  ├─ Max_tokens: 900                            │   │
│ │  │  └─ Timeout: 300s                              │   │
│ │  │                                                 │   │
│ │  └─ 返回: {                                        │   │
│ │      "success": true,                             │   │
│ │      "prediction": "核准...维持...",              │   │
│ │      "method": "official_step",                   │   │
│ │      "duration": 45.23,                           │   │
│ │      "raw_response": {...}                        │   │
│ │    }                                              │   │
│ └──────────────────────────────────────┬──────────────┘   │
│                                        │                   │
│ ┌──────────────────────────────────────▼──────────────┐   │
│ │ 保存结果到 Case 模型 (可选)                         │   │
│ │  ├─ case.prediction ← result.prediction            │   │
│ │  ├─ case.predict_time ← now()                      │   │
│ │  ├─ case.predict_method ← 'official_step'          │   │
│ │  └─ db.session.commit()                            │   │
│ └──────────────────────────────────────┬──────────────┘   │
│                                        │                   │
│ ┌──────────────────────────────────────▼──────────────┐   │
│ │ JSON 响应                                          │   │
│ │  {                                                 │   │
│ │    "success": true,                                │   │
│ │    "case_id": 31,                                  │   │
│ │    "case_name": "杨某甲等走私贩卖毒品...",         │   │
│ │    "case_type": "刑事案件",                        │   │
│ │    "prediction": "核准...维持...",                │   │
│ │    "method": "official_step"                      │   │
│ │  }                                                 │   │
│ └──────────────────────────────────────┬──────────────┘   │
└──────────────────────────────────────────────────────────────┘
                   │ HTTP 200
                   ▼
┌─────────────────────────────────────────────────────────────┐
│ 前端显示                                                   │
│ ┌─────────────────────┐                                   │
│ │ 预测结果             │                                   │
│ │ "核准...维持..."    │                                   │
│ │ [复制] [对比] [评分]│                                   │
│ └─────────────────────┘                                   │
└─────────────────────────────────────────────────────────────┘
```

---

### 核心特点
| 特征 | 说明 |
|------|------|
| **入口** | Web 预测页面 |
| **模板来源** | 基线提示词 (DEFAULT\_PREDICT\_PROMPT\_TEMPLATE 或文件) |
| **评测** | ❌ 无 (直接预测) |
| **评审** | ❌ 无 (直接返回) |
| **决策门禁** | ❌ 无 (无条件返回) |
| **主要文件** | app/api.py, app/templates/predict.html |
| **流程时间** | ~30-50 秒 (一次预测) |
| **用途** | 快速获取预测结果，UI展示 |

---

## 2️⃣ **迭代优化评测流程** (Evaluation & Iteration Flow)

### 流程图
```
┌─────────────────────────────────────────────────────────────┐
│ 开发者主动执行 (发起)                                       │
│                                                            │
│  python eval/run_greedy_eval.py \                         │
│    --case-id 31 \                                         │
│    --baseline-prompt-file eval/prompts/v1_baseline.txt \  │
│    --candidate-prompt-file eval/prompts/v2_try1_2.txt \   │
│    --method official_step \                              │
│    --repeats 3 \                                          │
│    --run-review-agent \                                  │
│    --require-review-acceptable \                         │
│    --review-min-score 75 \                               │
│    [--auto-adopt] [--dry-run]                            │
└─────────────────────┬──────────────────────────────────────┘
                      │
┌─────────────────────▼──────────────────────────────────────┐
│ 【第一层】参数解析与加载                                   │
│                                                            │
│  ├─ 加载 baseline 提示词文件                              │
│  │   eval/prompts/v1_baseline.txt                        │
│  │   ↓ (如果不存在，使用系统默认)                          │
│  │                                                        │
│  ├─ 加载 candidate 提示词文件                             │
│  │   eval/prompts/v2_try1_2.txt ← 【新版本】            │
│  │                                                        │
│  ├─ 查询数据库: Case.query.get(31)                        │
│  │   Case对象包含:                                       │
│  │   ├─ content: 完整案件描述                            │
│  │   ├─ actual_result: 真实判决【对照组】                │
│  │   └─ sort: 案件类型                                   │
│  │                                                        │
│  └─ 参数验证:                                            │
│      ├─ decision_mode=review 需要 --run-review-agent     │
│      ├─ repeats >= 1                                     │
│      └─ case_id 必须存在                                 │
└─────────────────────┬──────────────────────────────────────┘
                      │
┌─────────────────────▼──────────────────────────────────────┐
│ 【第二层】多轮评测 (repeats = 3)                           │
│                                                            │
│  for run in range(1, 4):  # 3轮                           │
│    │                                                      │
│    ├─ ⚙️ 评测 baseline (轮1)                              │
│    │    └─ score_one(case, 'v1_baseline', ...)           │
│    │       ├─ 调用: predict_judgement_with_api()         │
│    │       │   └─ OpenAI API → 预测结果                  │
│    │       └─ 计算4个维度:                               │
│    │           ├─ similarity (char F1)                   │
│    │           ├─ key_recall (关键词召回)                 │
│    │           ├─ fmt (格式分数)                          │
│    │           └─ length (长度分数)                       │
│    │           = overall = 0.5305                         │
│    │                                                      │
│    ├─ ⚙️ 评测 candidate (轮1)                             │
│    │    └─ score_one(case, 'v2_try1_2', ...)            │
│    │       └─ 同上，得到 overall = 0.5319                │
│    │                                                      │
│    ├─ ⚙️ 评测 baseline (轮2)                              │
│    │    └─ 重复 (可能因LLM随机性得到不同分数)             │
│    │                                                      │
│    └─ ⚙️ 评测 candidate (轮2)                             │
│         └─ 重复                                          │
│                                                           │
│  结果: baseline_runs = [score1, score2, score3]          │
│       candidate_runs = [score1, score2, score3]          │
└─────────────────────┬──────────────────────────────────────┘
                      │
┌─────────────────────▼──────────────────────────────────────┐
│ 【第三层】聚合与分数决策 (aggregate=median)                │
│                                                            │
│  ┌─ baseline_score = aggregate_scores(baseline_runs)      │
│  │   ├─ similarity = median([s1, s2, s3])                │
│  │   ├─ key_recall = median([k1, k2, k3])                │
│  │   ├─ fmt = median([f1, f2, f3])                       │
│  │   ├─ length = median([l1, l2, l3])                    │
│  │   └─ overall = median([o1, o2, o3]) = 0.5305         │
│  │                                                        │
│  ├─ candidate_score = aggregate_scores(candidate_runs)    │
│  │   └─ overall = median([...]) = 0.5319                 │
│  │                                                        │
│  ├─ 计算分数指标:                                         │
│  │   ├─ delta = 0.5319 - 0.5305 = +0.0014                │
│  │   ├─ win_rate = 1/1 = 1.0 (candidate每轮都赢)        │
│  │   └─ regress_fmt = No (格式分数未下降)                 │
│  │                                                        │
│  └─ 【分数判定】decide()                                  │
│      ├─ 检查: delta(0.0014) >= min_delta(0.01)? ❌       │
│      ├─ 检查: win_rate(1.0) >= min_win_rate(0.5)? ✅    │
│      ├─ 检查: fmt未退化? ✅                               │
│      ├─ 检查: key_recall未退化? ✅                        │
│      └─ 分数决策结果: ❌ REJECT (delta不足)              │
│         理由: "总分提升不足: delta=0.0014 < 0.01"        │
└─────────────────────┬──────────────────────────────────────┘
                      │
┌─────────────────────▼──────────────────────────────────────┐
│ 【第四层】生成评测报告 (JSON)                              │
│                                                            │
│  greedy_case_31_20260326_201047.json                      │
│  ├─ meta:                                                │
│  │   ├─ case_id: 31, case_name: "杨某甲等走私贩卖..."   │
│  │   ├─ method: official_step                            │
│  │   ├─ repeats: 3, aggregate: median                    │
│  │   ├─ baseline_prompt_file: v1_baseline.txt            │
│  │   └─ candidate_prompt_file: v2_try1_2.txt             │
│  │                                                        │
│  ├─ decision:                                            │
│  │   ├─ accepted: false                                  │
│  │   ├─ reason: "总分提升不足..."                        │
│  │   ├─ delta_overall: 0.0014                            │
│  │   └─ win_rate: 1.0                                    │
│  │                                                        │
│  ├─ baseline: {similarity, key_recall, fmt, length, ...} │
│  ├─ candidate: {...}                                     │
│  ├─ baseline_runs: [{run1}, {run2}, {run3}]              │
│  └─ candidate_runs: [{run1}, {run2}, {run3}]             │
└─────────────────────┬──────────────────────────────────────┘
                      │ (如果 --run-review-agent)
┌─────────────────────▼──────────────────────────────────────┐
│ 【第五层】评审智能体门禁 (A2A)                             │
│                                                            │
│  review_prediction_with_agent()                           │
│  ├─ 输入:                                                 │
│  │   ├─ case_id: 31                                      │
│  │   ├─ full_case_content: "杨某甲等因贩卖毒品..."      │
│  │   ├─ actual_result: "本院核准...改判黄某甲死缓..."   │
│  │   ├─ predicted_result: candidate.prediction           │
│  │   └─ predictor_prompt_template: v2_try1_2内容        │
│  │                                                        │
│  ├─ 调用 OpenAI (评审模型)                               │
│  │    "作为法律评审专家，判断该预测结果是否可采纳..."    │
│  │                                                        │
│  └─ 输出:                                                │
│      ├─ acceptable: false                                │
│      ├─ overall_score: 30/100                            │
│      ├─ issues: [                                        │
│      │    {                                              │
│      │      "type": "核心要素一致性",                    │
│      │      "severity": "high",                          │
│      │      "detail": "死刑改判逻辑缺失..."              │
│      │    },                                             │
│      │    {...}                                          │
│      │  ]                                                │
│      └─ prompt_optimization_suggestions: [               │
│           "强化复核意见识别...",                         │
│           "增加改判逻辑处理..."                          │
│         ]                                                │
│                                                           │
│  生成两个报告文件:                                        │
│  ├─ greedy_case_31_20260326_201047_review.json           │
│  └─ greedy_case_31_20260326_201047_review.md             │
└─────────────────────┬──────────────────────────────────────┘
                      │
┌─────────────────────▼──────────────────────────────────────┐
│ 【第六层】综合决策 (decision_mode=review)                  │
│                                                            │
│  mode = "review" → 仅看评审结果                           │
│  ├─ 检查: require_review_acceptable? 是                   │
│  │   └─ acceptable 必须 = true? ❌ 当前是 false          │
│  ├─ 检查: review_min_score >= 75? 当前是 30 ❌           │
│  └─ 【评审判定】❌ REJECT                                 │
│     理由: "评审门禁未通过: acceptable=false"              │
│                                                           │
│  决策优先级:                                              │
│  ├─ decision_mode=score  → 仅看分数决策结果              │
│  ├─ decision_mode=review → 仅看评审决策结果 (当前)      │
│  └─ decision_mode=hybrid → 分数AND评审都通过             │
└─────────────────────┬──────────────────────────────────────┘
                      │
┌─────────────────────▼──────────────────────────────────────┐
│ 【第七层】采纳决策 (--auto-adopt)                          │
│                                                            │
│  if accepted AND auto_adopt:                             │
│    ├─ 源文件: eval/prompts/v2_try1_2.txt                 │
│    ├─ 目标文件: eval/prompts/v1_baseline.txt             │
│    ├─ 操作: shutil.copyfile(source, target)              │
│    │        将候选提示词覆盖基线                         │
│    │                                                      │
│    └─ 写入采纳日志:                                      │
│        eval/results/greedy/adoption_log.jsonl            │
│        {                                                 │
│          "time": "2026-03-26T20:10:47",                 │
│          "report_file": "..._201047.json",              │
│          "source_prompt": ".../v2_try1_2.txt",          │
│          "adopted_to": ".../v1_baseline.txt"            │
│        }                                                 │
│                                                           │
│  else if --dry-run:                                      │
│    └─ 模拟运行，不写入任何文件                           │
│                                                           │
│  else:                                                   │
│    └─ accepted=false，不采纳                              │
└─────────────────────┬──────────────────────────────────────┘
                      │
┌─────────────────────▼──────────────────────────────────────┐
│ 【输出】完整报告包                                         │
│                                                            │
│  eval/results/greedy/                                     │
│  ├─ greedy_case_31_20260326_201047.json                   │
│  │  (完整评测数据: 4轮分数、决策理由、采纳状态)           │
│  │                                                        │
│  ├─ greedy_case_31_20260326_201047_review.json            │
│  │  (评审原始结构数据: 问题列表、建议、改写后的提示词)   │
│  │                                                        │
│  ├─ greedy_case_31_20260326_201047_review.md              │
│  │  (可读摘要: 主要问题、优化建议、最终结论)             │
│  │                                                        │
│  └─ adoption_log.jsonl                                    │
│     (采纳历史: 每行一条采纳记录)                          │
│                                                            │
│  控制台输出:                                              │
│  单案件贪心评测完成                                       │
│  case_id=31, repeats=3, aggregate=median                  │
│  decision: REJECT (评审门禁未通过: acceptable=false)     │
│  report: .../greedy_case_31_20260326_201047.json          │
│  review-agent: 评审结果已输出到 ..._review.json           │
│  review-agent: 可读摘要已输出到 ..._review.md             │
└──────────────────────────────────────────────────────────────┘
```

---

### 核心特点
| 特征 | 说明 |
|------|------|
| **入口** | CLI 脚本执行 (`eval/run_greedy_eval.py`) |
| **模板来源** | 基线 + 候选对比 |
| **评测** | ✅ 多轮(repeats) + 聚合(median/mean) |
| **评审** | ✅ 评审智能体(A2A) 判断可采纳性 |
| **决策门禁** | ✅ 分数门禁 + 评审门禁 (双层) |
| **主要文件** | eval/run_greedy_eval.py, app/reviewer_agent.py |
| **流程时间** | ~60-120 秒 (repeats=3+评审) |
| **用途** | 开发阶段迭代优化、质量评审、数据驱动决策 |

---

## 📊 两大流程的关键区别

| 维度 | 生产预测流程 | 迭代优化流程 |
|------|-----------|-----------|
| **启动方式** | Web UI点击 | CLI命令执行 |
| **用户** | 业务/管理员 | 开发/算法 |
| **速度** | 快 (1次预测~30s) | 慢 (3轮+评审~120s) |
| **可靠性** | 单次，随机性高 | 多轮+评审，可靠性高 |
| **反馈** | 简单返回结果 | 详细分析报告 |
| **决策依据** | 无 (直接返回) | 分数+评审双层 |
| **可审计** | ❌ 无记录 | ✅ 完整日志 |
| **采纳机制** | ❌ 无 | ✅ auto-adopt自动/manual手动 |
| **目标** | 快速获取预测 | 持续改进基线 |

---

## 🔄 使用场景示例

### 场景A: 用户查看某个案件的预测结果
```
用户行为:
1. 打开 http://localhost:5000/predict
2. 输入 case_id=31
3. 点击 "预测"
4. 等待 30s
5. 看到预测结果

使用流程: 【生产预测流程】
→ app/api.py:predict_judgement_with_api()
→ 基线提示词 (DEFAULT or 默认文件)
→ 返回结果显示
```

### 场景B: 优化提示词，测试新版本
```
开发者行为:
1. 修改 eval/prompts/v3_improved.txt
2. 执行命令:
   python eval/run_greedy_eval.py \
     --case-id 31 \
     --baseline-prompt-file eval/prompts/v1_baseline.txt \
     --candidate-prompt-file eval/prompts/v3_improved.txt \
     --repeats 3 \
     --run-review-agent \
     --require-review-acceptable \
     --review-min-score 75 \
     --dry-run  (先预览, 不采纳)
3. 查看 report 和 review 报告
4. 根据评审意见修改提示词
5. 去掉 --dry-run, 加 --auto-adopt, 再跑一遍
6. 若通过门禁, 自动采纳到 v1_baseline.txt

使用流程: 【迭代优化流程】
→ eval/run_greedy_eval.py
→ 三层决策 (分数+评审+采纳)
→ 生成报告和审计日志
```

### 场景C: 回滚坏的采纳
```
问题: 某个采纳的提示词质量差

解决:
1. 查看 adoption_log.jsonl, 找到这次采纳
2. 从备份或git恢复之前的v1_baseline.txt
3. 重新运行评测验证

使用流程: 【迭代优化流程】
→ 利用采纳日志追踪历史
→ 回滚+重新评测
```

---

## 🎯 总结

**生产预测流程** = 快速单次预测，用于业务 UI 展示
```
User Input → API → Predict → Return Result
      (30s, 无评审)
```

**迭代优化流程** = 系统化的质量改进，用于开发阶段
```
Prompt Candidate 
    → Evaluate (3轮)
    → Score Decision  
    → Review Agent
    → Auto-Adopt or Reject
    → Audit Log
      (120s, 完整评审)
```

两个流程是 **相互独立但互补** 的：
- 生产流程每天运行100次+ (快速、无等待)
- 迭代流程每周运行5-10次 (深度分析、确保质量)
- 迭代流程优化好的提示词 → 供生产流程使用
