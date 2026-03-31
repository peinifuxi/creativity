# 🎯 A2A + Skill 核心代码地图

## 【快速定位】一张图看明白

```
┌─ 用户运行 Skill 推荐命令 ────────────────────────────┐
│                                                    │
│  python eval/run_greedy_eval.py \                 │
│    --case-id 31 \                                 │
│    --run-review-agent \            ←─ Skill标记   │
│    --require-review-acceptable \   ←─ 评审门禁    │
│    --auto-adopt                    ←─ 自动采纳    │
│                                                    │
└────────────────────┬─────────────────────────────┘
                     │
        ┌────────────▼──────────────┐
        │ eval/run_greedy_eval.py   │
        │ (主流程编排)              │
        │                           │
        │ ① parse_args()            │ ← Skill命令→参数
        │    args.run_review_agent = True
        │    args.require_review_acceptable = True
        │                           │
        │ ② score_one() × 3轮       │ ← 多轮评测
        │    baseline vs candidate  │
        │                           │
        │ ③ decide()                │ ← 分数判定
        │    REJECT? 总分不足       │
        │                           │
        │ ④ run_reviewer_if_needed()│ ← ★ A2A调用点
        │    if args.run_review_agent:
        │      review_result = review_prediction_with_agent({
        │        "case_id": 31,
        │        "predicted_result": "核准....",
        │        "actual_result": "...改判...",
        │        ...
        │      })  ← ★ 构造A2AReviewPayload
        │                           │
        │ ⑤ evaluate_review_gate()  │ ← 评审判定
        │    if review_result.get('acceptable'):
        │      "评审通过"
        │    else:
        │      "评审失败: issues=[...]"
        │                           │
        │ ⑥ auto_adopt_if_needed()  │ ← 采纳
        │    shutil.copyfile(candidate → baseline)
        │    adoption_log.jsonl.append({...})
        │                           │
        └────┬─────────────────────┘
            │
            │  (④中调用)
            │
        ┌───▼──────────────────────────────────┐
        │ app/reviewer_agent.py                │
        │ (A2A智能体)                          │
        │                                      │
        │ ① A2AReviewPayload           ← 数据契约
        │    class A2AReviewPayload(TypedDict):
        │      case_id: int
        │      full_case_content: str
        │      predicted_result: str
        │      actual_result: str
        │      ...
        │                                      │
        │ ② review_prediction_with_agent()    │ ← A2A入口
        │    def review_prediction_with_agent(
        │      payload: A2AReviewPayload
        │    ) -> Dict[str, Any]:
        │      # OpenAI 调用，JSON解析
        │      return {
        │        "acceptable": False,        ← 核心输出
        │        "overall_score": 30,
        │        "issues": [{
        │          "type": "核心要素不一致",
        │          "severity": "high",
        │          "detail": "死刑改判逻辑缺失"
        │        }],
        │        "prompt_optimization_suggestions": [
        │          "强化复核意见识别...",
        │          ...
        │        ]
        │      }
        │                                      │
        └──────────────────────────────────────┘
```

---

## 【三大代码亮点】

### 🔵 亮点1: A2A 数据契约 (app/reviewer_agent.py)

```python
# ===== 第13-20行 =====
class A2AReviewPayload(TypedDict):
    """【标准化输入契约】"""
    case_id: int
    case_type: str
    full_case_content: str         # ← 案件全文
    actual_result: str             # ← 真实判决
    predicted_result: str          # ← 模型预测
    predictor_prompt_template: str # ← 使用的提示词
    predictor_method: str          # ← 预测方法
```

**为什么是A2A**:
- ✅ 定义清晰的数据结构，任何模块都知道输入什么
- ✅ TypedDict 强制类型检查，IDE可自动完成
- ✅ 可以在多个地方复用这个契约

---

### 🟢 亮点2: A2A 智能体 (app/reviewer_agent.py)

```python
# ===== 第134-200行 =====
def review_prediction_with_agent(
    payload: A2AReviewPayload
) -> Dict[str, Any]:
    """【单一职责】
    输入: payload (A2A标准数据)
    处理: 调用OpenAI, 解析JSON
    输出: 结构化评审结果
    """
    
    # 构建prompt
    user_prompt = f"""
请从以下维度审查：
1) 事实一致性
2) 核心要素一致性
3) 格式合规性

[案件] {payload['full_case_content'][:10000]}
[真实判决] {payload['actual_result'][:4000]}
[预测结果] {payload['predicted_result'][:4000]}
[提示词] {payload['predictor_prompt_template'][:8000]}

返回JSON:
{
  "acceptable": true/false,
  "overall_score": 0-100,
  "issues": [...],
  "prompt_optimization_suggestions": [...]
}
    """
    
    # 调用OpenAI
    response = client.chat.completions.create(
        model="deepseek-r1",
        messages=[
            {"role": "system", "content": "..."},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.1
    )
    
    # 返回标准化结果
    return {
        "success": True,
        "acceptable": parsed.get("acceptable"),
        "overall_score": parsed.get("overall_score"),
        "issues": parsed.get("issues"),
        "prompt_optimization_suggestions": [...]
    }
```

**为什么是A2A**:
- ✅ 接收标准化类型 (A2AReviewPayload)
- ✅ 返回标准化结果 (Dict[str, Any])
- ✅ 单一职责，无副作用，可重复调用

---

### 🟡 亮点3: 在主流程中调用 A2A (eval/run_greedy_eval.py)

```python
# ===== 第340-365行 =====
def run_reviewer_if_needed(...) -> tuple[Optional[Path], Optional[dict]]:
    
    if not args.run_review_agent:  # ← Skill参数检查
        return None, None
    
    if args.dry_run:               # ← Skill参数检查
        return Path("DRY_RUN"), None
    
    # ✅ 构造标准化 A2A Payload
    from app.reviewer_agent import review_prediction_with_agent
    
    review_result: dict[str, Any] = review_prediction_with_agent(
        {
            "case_id": case.id,
            "case_type": infer_case_type(case),
            "full_case_content": case.content or "",
            "actual_result": case.get_actual_result() or "",
            "predicted_result": candidate.prediction or "",
            "predictor_prompt_template": candidate_prompt or "",
            "predictor_method": args.method,
        }
    )  # ← 这就是 A2AReviewPayload 形式的调用!
    
    # ✅ 标准化处理输出
    review_path = report_path.with_name(f"{...}_review.json")
    review_path.write_text(
        json.dumps(review_result, ensure_ascii=False, indent=2)
    )
    
    return review_path, review_result
```

**为什么是A2A**:
- ✅ 明确的调用点，数据清晰
- ✅ 与 A2AReviewPayload 的数据结构一一对应
- ✅ 返回值可直接处理，无需转换

---

## 【Skill 如何体现】

### .github/skills/judgement-prompt-iteration/SKILL.md

```yaml
---
name: judgement-prompt-iteration
description: "判决预测提示词迭代、单案件贪心评测、评审智能体门禁、候选提示词采纳决策"
---

## 推荐命令 A: 快速评测
python eval/run_greedy_eval.py \
  --case-id 31 \
  --candidate-prompt-file eval/prompts/v2_try1_2.txt \
  --repeats 3 --aggregate median \
  --dry-run
```

**Skill映射到代码**:

| Skill命令 | 代码中对应 | 文件 | 作用 |
|---------|----------|------|------|
| `--case-id 31` | `args.case_id` | run_greedy_eval.py:60 | 案件选择 |
| `--candidate-prompt-file ...` | `args.candidate_prompt_file` | run_greedy_eval.py:63 | 加载提示词 |
| `--repeats 3` | `for run in range(1, args.repeats+1)` | run_greedy_eval.py:497 | 多轮评测 |
| `--aggregate median` | `aggregate_scores(..., "median")` | run_greedy_eval.py:510 | 分数聚合 |
| `--dry-run` | `if args.dry_run: return Path("DRY_RUN")` | run_greedy_eval.py:356 | 模拟模式 |

---

## 【完整数据流】

```
Skill推荐命令输入
│
├─ --case-id 31
├─ --candidate-prompt-file eval/prompts/v2_try1_2.txt
├─ --run-review-agent ◄─ 【Skill决定是否启用A2A】
├─ --require-review-acceptable ◄─ 【Skill决定门禁策略】
└─ --dry-run ◄─ 【Skill决定是否真实写入】
│
▼
run_greedy_eval.main()
│
├─ for i in range(repeats=3):
│  ├─ baseline_score = score_one(baseline_template)
│  └─ candidate_score = score_one(candidate_template)
│
├─ baseline_agg = aggregate_scores(baseline_runs, median)
├─ candidate_agg = aggregate_scores(candidate_runs, median)
│
├─ score_ok, score_reason = decide(
│     baseline, candidate, min_delta, ...
│   )  ← 第一层决策: 分数
│
├─ if args.run_review_agent:  ◄─ 【Skill参数检查】
│     review_result = review_prediction_with_agent({
│         "case_id": 31,
│         "predicted_result": candidate.prediction,
│         "actual_result": case.actual_result,
│         "predictor_prompt_template": candidate_prompt,
│         ...
│     })  ◄─ 【调用A2A智能体】
│     
│     # A2A内部
│     ├─ 构建prompt (case+预测+实际)
│     ├─ 调用OpenAI
│     ├─ 解析JSON
│     └─ return {acceptable, overall_score, issues, suggestions}
│
├─ review_ok, review_reason = evaluate_review_gate(review_result)
│   ← 第二层决策: 评审  ◄─ 【Skill决定接受标准】
│
├─ final_accepted, final_reason = finalize_decision(
│     score_ok, score_reason, review_ok, review_reason
│   )  ← 第三层决策: 综合
│
├─ if final_accepted and args.auto_adopt:  ◄─ 【Skill参数】
│     shutil.copyfile(candidate_file, baseline_file)
│     adoption_log.append({...})
│
└─ save_report(
     greedy_case_31_20260326_201047.json,
     greedy_case_31_20260326_201047_review.json,
     greedy_case_31_20260326_201047_review.md
   )
```

---

## 【快速查找】

如果你想找...

| 需求 | 查看 |
|------|------|
| A2A 数据类型定义 | app/reviewer_agent.py:13-20 |
| A2A 入口函数 | app/reviewer_agent.py:134-200 |
| A2A 被谁调用 | eval/run_greedy_eval.py:340-365 |
| Skill 推荐命令 | .github/skills/judgement-prompt-iteration/SKILL.md:12-35 |
| Skill 命令→代码映射 | eval/run_greedy_eval.py:60-75 (参数定义) |
| 完整流程图 | PROCESS_FLOWS.md |
| 架构详解 | ARCHITECTURE_IMPLEMENTATION.md |

---

## 【最后验证】

实际测试中看到这些A2A+Skill的体现：

```
TEST Output:
case_id=31
decision_mode=review  ◄─ Skill参数: --decision-mode review
baseline overall=0.5305
candidate overall=0.5319
decision: REJECT (评审门禁未通过：acceptable=false)

review-agent: 评审结果已输出到 greedy_case_31_20260326_201047_review.json
review-agent: 可读摘要已输出到 greedy_case_31_20260326_201047_review.md
  ▲
  │
  └─ 这就是 A2A 评审智能体执行的证据!
    └─ 调用了 app/reviewer_agent.py:review_prediction_with_agent()
    └─ 返回了标准化结果
    └─ Skill 指定了 --run-review-agent 和 --require-review-acceptable
```

✅ **A2A架构 + Skill 封装完全体现在代码中！**
