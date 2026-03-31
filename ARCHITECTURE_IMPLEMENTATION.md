# 🏗️ A2A 架构 + Skill 封装实现清单

## 【A2A智能体架构】在哪里体现

### 1⃣ A2A 数据契约定义
**文件**: `app/reviewer_agent.py` (第1-20行)

```python
class A2AReviewPayload(TypedDict):
    """A2A风格的标准化输入契约"""
    case_id: int
    case_type: str
    full_case_content: str
    actual_result: str
    predicted_result: str
    predictor_prompt_template: str
    predictor_method: str
```

✅ **A2A体现**: 
- 定义了**标准化输入接口** (TypedDict)，任何模块都可以按这个契约调用
- 字段名清晰、类型强制、可文档化

---

### 2⃣ A2A 智能体函数
**文件**: `app/reviewer_agent.py` (第130-200行)

```python
def review_prediction_with_agent(payload: A2AReviewPayload) -> Dict[str, Any]:
    """
    【A2A智能体入口】
    
    输入: A2AReviewPayload (标准化数据格式)
    处理: OpenAI LLM评审
    输出: Dict[str, Any] (标准化结果格式)
    """
    # 构造system prompt
    system_prompt = (
        "你是法律判决预测评审智能体。"
        "严格输出JSON，不要输出任何额外说明。"
    )
    
    # 构造user prompt (包含case_id, case_type等payload字段)
    user_prompt = f"""
请从以下维度审查预测结果：
1) 事实一致性
2) 核心要素一致性
3) 格式合规性
4) 可采纳性

返回 JSON:
{{
  "acceptable": true/false,
  "overall_score": 0-100,
  "issues": [{{...}}],
  "prompt_optimization_suggestions": ["..."],
  "revised_prompt_template": "..."
}}

案件全文: {payload.get('full_case_content')}
真实判决: {payload.get('actual_result')}
预测判决: {payload.get('predicted_result')}
提示词: {payload.get('predictor_prompt_template')}
    """
    
    # 调用OpenAI
    response = client.chat.completions.create(
        model="deepseek-r1",
        messages=[system_prompt, user_prompt],
        temperature=0.1,
        max_tokens=1400
    )
    
    # 标准化输出
    return {
        "success": True,
        "acceptable": bool(parsed.get("acceptable")),
        "overall_score": int(parsed.get("overall_score")),
        "issues": parsed.get("issues"),
        "prompt_optimization_suggestions": [...],
        "revised_prompt_template": "..."
    }
```

✅ **A2A体现**:
- **单一职责**: 仅负责"接收payload → 调用LLM → 返回结果"
- **标准化接口**: 入参和出参都有明确的数据结构
- **可组合**: 任何其他模块都可以直接调用这个函数

---

### 3⃣ A2A 在评测流程中的调用
**文件**: `eval/run_greedy_eval.py` (第340-380行)

```python
def run_reviewer_if_needed(
    args: argparse.Namespace,
    case: Case,
    candidate: OneCaseScore,
    candidate_prompt: Optional[str],
    report_path: Path,
) -> tuple[Optional[Path], Optional[dict[str, Any]]]:
    """
    【A2A调用入口】
    
    在主流程中检查是否需要启动评审智能体
    """
    if not args.run_review_agent:
        return None, None  # 用户未指定 --run-review-agent，跳过

    if args.dry_run:
        return Path("DRY_RUN"), None  # dry-run模式，不实际调用

    # ✅ 构造标准化的A2A Payload（数据契约）
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
        }  # ← 这就是 A2AReviewPayload
    )

    # ✅ 接收标准化输出，写入报告
    review_path = report_path.with_name(f"{report_path.stem}_review.json")
    review_path.write_text(json.dumps(review_result, ensure_ascii=False, indent=2), encoding="utf-8")

    # ✅ 生成可读摘要
    summary_lines = [
        "# 评审智能体摘要",
        f"- 评审成功: {'是' if review_result.get('success') else '否'}",
        f"- 是否可采纳: {'是' if review_result.get('acceptable') else '否'}",
        f"- 评审总分: {int(review_result.get('overall_score', 0))}",
    ]
    
    issues = review_result.get("issues", []) or []
    for item in issues:
        summary_lines.append(f"- [{item.get('severity')}] {item.get('detail')}")
    
    # ... 更多逻辑
    return review_path, review_result
```

✅ **A2A体现**:
- **明确的调用点**: `evaluation flow` 在需要时主动调用 `reviewer_agent`
- **数据契约遵守**: 构造的payload完全符合A2AReviewPayload定义
- **结果处理**: 接收返回值后进行后续处理（报告写入、决策等）

---

## 【Skill 封装】在哪里体现

### 1⃣ Skill 的本质：知识与流程封装
**文件**: `.github/skills/judgement-prompt-iteration/SKILL.md`

```yaml
---
name: judgement-prompt-iteration
description: "判决预测提示词迭代、单案件贪心评测、评审智能体门禁、候选提示词采纳决策、回归验证"
---
```

✅ **Skill体现**:
- **一级标题**: 明确场景 ("判决预测提示词迭代")
- **推荐命令**: 标准化的使用方式 (A/B/C三个场景)
- **输出说明**: 告诉用户报告位置和含义
- **迭代规则**: 编码了多轮改善的最佳实践

---

### 2⃣ Skill 的推荐命令映射到代码
**Skill.md 第12-35行**:

```markdown
## 推荐命令

### A. 快速评测（不采纳）
python eval/run_greedy_eval.py \
  --case-id 12 \
  --candidate-prompt-file eval/prompts/v2.txt \
  --method official_step \
  --repeats 3 \
  --aggregate median \
  --min-win-rate 0.5 \
  --min-delta 0.0 \
  --no-regress-format \
  --no-regress-key \
  --dry-run

### B. 评测 + 评审智能体门禁
python eval/run_greedy_eval.py \
  --case-id 12 \
  --candidate-prompt-file eval/prompts/v2.txt \
  --method official_step \
  --run-review-agent \
  --require-review-acceptable \
  --review-min-score 75 \
  --dry-run

### C. 通过后自动采纳
python eval/run_greedy_eval.py \
  --case-id 12 \
  --baseline-prompt-file eval/prompts/v1_baseline.txt \
  --candidate-prompt-file eval/prompts/v2.txt \
  --method official_step \
  --run-review-agent \
  --require-review-acceptable \
  --review-min-score 75 \
  --auto-adopt
```

✅ **Skill 对应代码实现**:

| Skill命令 | 代码实现 | 对应参数 |
|---------|--------|--------|
| 快速评测 | `eval/run_greedy_eval.py` `parse_args()` | `--repeats`, `--aggregate`, `--dry-run` |
| 评测+评审 | `run_reviewer_if_needed()` + `evaluate_review_gate()` | `--run-review-agent`, `--require-review-acceptable` |
| 自动采纳 | `auto_adopt_if_needed()` | `--auto-adopt` |

---

### 3⃣ Skill 的最佳实践规则
**Skill.md 第47-53行**:

```markdown
## 迭代规则
- 每次只改一个提示词变量
  → 代码体现: `--candidate-prompt-file` 一次只能改一个
  
- 优先看失败原因标签而不是只看总分
  → 代码体现: `review_result.get("issues")` 返回详细问题标签
  
- 连续 3 轮不过门禁时，回退到上一个稳定版本
  → 代码体现: `adoption_log.jsonl` 记录采纳历史，可查询追踪
  
- 候选通过单案后，必须做小样本回归（5~20条）
  → 代码体现: 用户可修改 `--case-id` 跑多个案件验证
```

---

## 【三者的关系图】

```
┌──────────────────────────────────────────────────────────┐
│ Skill: judgement-prompt-iteration                        │
│ (封装了整个迭代流程的最佳实践)                            │
│                                                          │
│  Recommend Commands:                                     │
│  A. 快速评测 (--dry-run)                                 │
│  B. 评测+评审 (--run-review-agent)                       │
│  C. 自动采纳 (--auto-adopt)                              │
└──────────────────────────────────────┬───────────────────┘
                                       │
                   ┌─────────────────────┴──────────────────┐
                   │                                        │
        ┌──────────▼─────────────┐         ┌───────────────▼────────┐
        │ eval/run_greedy_eval.py│         │ app/reviewer_agent.py  │
        │ (主流程编排)           │         │ (A2A智能体)            │
        │                        │         │                        │
        │ parse_args()           │         │ A2AReviewPayload       │
        │  ↓                     │         │  (数据契约)            │
        │ load_prompt()          │         │                        │
        │  ↓                     │         │ review_prediction_...  │
        │ score_one() x repeats  │         │  (智能体函数)          │
        │  ↓                     │         │                        │
        │ aggregate_scores()     │         │ 输出: {acceptable,     │
        │  ↓                     │         │        overall_score,  │
        │ decide() ◄─────────────┼─────────┤        issues,         │
        │ (分数决策)             │         │        suggestions}    │
        │                        │         │                        │
        │ run_reviewer_if_needed()├────────►(调用A2A)              │
        │ (可选评审)             │         │                        │
        │  ↓                     │         └────────────────────────┘
        │ evaluate_review_gate() │
        │ (评审决策)             │
        │  ↓                     │
        │ finalize_decision()    │
        │ (综合决策)             │
        │  ↓                     │
        │ auto_adopt_if_needed() │
        │ (采纳逻辑)             │
        │  ↓                     │
        │ save_report()          │
        │ adoption_log.jsonl     │
        └────────────────────────┘
```

---

## 【具体代码位置速查表】

### 🔵 A2A 架构相关代码

| 组件 | 文件 | 行号 | 说明 |
|------|------|------|------|
| **数据契约定义** | app/reviewer_agent.py | 13-20 | `class A2AReviewPayload(TypedDict)` |
| **A2A入口函数** | app/reviewer_agent.py | 134-200 | `def review_prediction_with_agent()` |
| **A2A调用点** | eval/run_greedy_eval.py | 340-365 | `run_reviewer_if_needed()` 中构造payload |
| **决策门禁** | eval/run_greedy_eval.py | 430-460 | `evaluate_review_gate()` |
| **综合决策** | eval/run_greedy_eval.py | 462-480 | `finalize_decision()` 中使用review结果 |

### 🟢 Skill 封装相关代码

| 组件 | 文件 | 说明 |
|------|------|------|
| **Skill定义** | .github/skills/judgement-prompt-iteration/SKILL.md | 整个skill文件 |
| **推荐命令A映射** | eval/run_greedy_eval.py | `parse_args()` 的参数定义 |
| **推荐命令B映射** | eval/run_greedy_eval.py | `--run-review-agent`, `--require-review-acceptable` |
| **推荐命令C映射** | eval/run_greedy_eval.py | `auto_adopt_if_needed()` + `--auto-adopt` |
| **迭代规则体现** | eval/results/greedy/adoption_log.jsonl | 采纳历史日志 |

---

## 【流程前后对比】

### ❌ 之前 (没有A2A + Skill)
```
开发者 → 手工运行case → 看分数 → 手动判断 → 手动复制提示词
(低效、容易出错、无审计)
```

### ✅ 现在 (A2A + Skill)
```
Skill推荐命令 → run_greedy_eval
                ├─ 分数决策 ✓
                ├─ A2A评审 ✓ (review_prediction_with_agent)
                └─ 自动采纳 ✓ (adoption_log.jsonl)
(高效、标准化、完全审计)
```

---

## 【总结】

### 🔵 A2A 架构
```
✓ 数据契约: A2AReviewPayload
✓ 智能体: review_prediction_with_agent()
✓ 调用点: eval/run_greedy_eval.py
✓ 标准化I/O: 任何模块都能对接
```

### 🟢 Skill 封装
```
✓ 场景文档: .github/skills/judgement-prompt-iteration/SKILL.md
✓ 推荐命令: A/B/C三个标准用法
✓ 代码对应: 每个命令都有明确的参数映射
✓ 最佳实践: 规则化的迭代方法
```

### 🟡 整合效果
```
用户只需 → 选择 Skill 推荐场景 (A/B/C)
         → 输入 case_id 和提示词文件
         → 系统自动 → 多轮评测
                    → A2A评审
                    → 生成报告
                    → 可选采纳
         ✓ 让专业工作流变成标准操作
```
