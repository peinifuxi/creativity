---
name: judgement-prompt-iteration
description: "Use when: 判决预测提示词迭代、单案件贪心评测、评审智能体门禁、候选提示词采纳决策、回归验证"
---

# 判决预测提示词迭代技能

## 目标
将“提示词修改 -> 预测评测 -> 评审质检 -> 采纳/拒绝”流程标准化，降低随机试错和误采纳。

## 适用场景
- 需要评估某版候选提示词是否优于当前基线
- 希望在分数之外加入“可用性评审”门禁
- 需要形成可审计的迭代证据（报告和日志）

## 标准流程（最小成本）
1. 选择一个 `case_id`，确保该案件存在 `actual_result`
2. 运行单案件贪心评测（建议 repeats >= 3）
3. 可选启用评审智能体，生成可用性结论与改写建议
4. 满足门禁后再采纳；否则拒绝并进入下一轮改词

## 推荐命令

### A. 快速评测（不采纳）
`python eval/run_greedy_eval.py --case-id 12 --candidate-prompt-file eval/prompts/v2.txt --method official_step --repeats 3 --aggregate median --min-win-rate 0.5 --min-delta 0.0 --no-regress-format --no-regress-key --dry-run`

### B. 评测 + 评审智能体门禁
`python eval/run_greedy_eval.py --case-id 12 --candidate-prompt-file eval/prompts/v2.txt --method official_step --run-review-agent --require-review-acceptable --review-min-score 75 --dry-run`

### C. 通过后自动采纳
`python eval/run_greedy_eval.py --case-id 12 --baseline-prompt-file eval/prompts/v1_baseline.txt --candidate-prompt-file eval/prompts/v2.txt --method official_step --run-review-agent --require-review-acceptable --review-min-score 75 --auto-adopt`

## 输出与审计
- 贪心报告：`eval/results/greedy/greedy_case_<id>_<time>.json`
- 评审报告：`eval/results/greedy/greedy_case_<id>_<time>_review.json`
- 采纳日志：`eval/results/greedy/adoption_log.jsonl`

## 迭代规则
- 每次只改一个提示词变量
- 优先看失败原因标签而不是只看总分
- 连续 3 轮不过门禁时，回退到上一个稳定版本
- 候选通过单案后，必须做小样本回归（5~20条）
