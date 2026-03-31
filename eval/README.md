# 提示词离线评测（方案一）

这个目录用于把“提示词优化”变成可量化迭代。

## 0) 先查可用 case_id

在项目根目录执行：

```powershell
python list_cases.py --limit 20 --only-with-actual
```

可选：按名称关键词过滤（例如民事）：

```powershell
python list_cases.py --limit 20 --only-with-actual --keyword 民事
```

## 1) 评测目标

- 使用数据库中的真实案件（`cases`）作为评测数据
- 每次修改提示词后跑同一批样本
- 自动输出总分与分项分，记录到排行榜

## 2) 先决条件

- 已完成 `.env` 配置
- `python init_db.py` 已执行
- 数据库中已有真实案件，且 `actual_result` 有值

## 3) 快速开始（低 token 版）

默认用 20 条样本：

```powershell
python eval/run_prompt_eval.py --limit 20 --method official_step --prompt-version v1
```

## 4) 使用自定义提示词模板

先准备一个提示词文件（例如 `eval/prompts/v2.txt`），然后运行：

```powershell
python eval/run_prompt_eval.py --limit 20 --method official_step --prompt-file eval/prompts/v2.txt --prompt-version v2
```

## 5) 使用固定案件ID对比（更严格）

```powershell
python eval/run_prompt_eval.py --case-ids 12,19,25,31,38 --method official_step --prompt-version fixed_set_v1
```

## 6) 不调用模型、仅复用已有预测结果

```powershell
python eval/run_prompt_eval.py --limit 20 --use-existing-prediction --prompt-version replay_db
```

## 7) 中断与容错

- 默认行为：单条样本失败不会中断整批，会继续评测并记为0分错误样本。
- 若你手动 `Ctrl + C`，脚本会保存已完成样本的 `partial` 报告。
- 如果你希望“遇错即停”，加参数：

```powershell
python eval/run_prompt_eval.py --limit 20 --stop-on-error --prompt-version strict_v1
```

## 8) 输出文件

脚本会写入 `eval/results/`：

- `prompt_eval_<version>_<time>.json`：完整明细（含每个案件得分）
- `prompt_eval_<version>_<time>.md`：可读报告
- `leaderboard.csv`：历次版本汇总

## 9) 指标说明

- `avg_overall`：总分（加权）
- `avg_similarity`：字符级相似度
- `avg_key_recall`：关键要素召回（罪名/刑罚/金额/动作词）
- `avg_format`：格式合规分（是否出现“判决如下”、markdown列表等）
- `avg_length`：长度匹配分
- `success_rate`：模型成功返回比例

## 10) 建议迭代节奏

- 固定样本集（建议固定 20 条）
- 每次只改一个提示词变量
- 跑完观察 `leaderboard.csv`
- 连续 3 轮不退化再上线

---

## 11) 单案件贪心迭代（超低 token）

如果你想每次只用 1 个案件来判断“这次提示词改动要不要采纳”，可以用：

```powershell
python eval/run_greedy_eval.py --case-id 12 --candidate-prompt-file eval/prompts/v2.txt --method official_step
```

基线提示词可指定，不指定则使用系统默认提示词：

```powershell
python eval/run_greedy_eval.py --case-id 12 --baseline-prompt-file eval/prompts/v1_baseline.txt --candidate-prompt-file eval/prompts/v2.txt --method official_step --min-delta 0.01 --no-regress-format --no-regress-key
```

判定规则：

- `candidate_overall - baseline_overall >= min_delta` 才通过
- 可选开启：不允许格式分退化（`--no-regress-format`）
- 可选开启：不允许关键要素召回退化（`--no-regress-key`）

输出文件：

- `eval/results/greedy/greedy_case_<id>_<time>.json`

建议：

- 日常快速迭代可用单案件贪心
- 每通过 3~5 次后，用 5~20 条小样本做一次回归，避免过拟合到单案件

### 自动采纳（可选）

如果你希望“评测通过就自动覆盖基线提示词”，可使用：

```powershell
python eval/run_greedy_eval.py --case-id 12 --baseline-prompt-file eval/prompts/v1_baseline.txt --candidate-prompt-file eval/prompts/v2.txt --method official_step --min-delta 0.01 --no-regress-format --no-regress-key --auto-adopt
```

说明：

- 仅当判定为 `ACCEPT` 才会执行覆盖。
- 默认覆盖目标是 `--baseline-prompt-file`。
- 也可通过 `--adopt-to <path>` 指定覆盖路径。
- 采纳审计会写入：`eval/results/greedy/adoption_log.jsonl`。

如果你想先观察判定结果，不进行任何覆盖写入：

```powershell
python eval/run_greedy_eval.py --case-id 12 --baseline-prompt-file eval/prompts/v1_baseline.txt --candidate-prompt-file eval/prompts/v2.txt --method official_step --min-delta 0.01 --no-regress-format --no-regress-key --auto-adopt --dry-run
```

为降低模型随机波动导致的误判，建议加重复评测：

```powershell
python eval/run_greedy_eval.py --case-id 12 --candidate-prompt-file eval/prompts/v2.txt --method official_step --repeats 3 --min-delta 0.01 --no-regress-format --no-regress-key --dry-run
```

说明：

- `--repeats 3` 表示同一提示词在同一案件上各跑3次。
- 判定使用3次平均分，报告内会保留每次运行明细（`baseline_runs` / `candidate_runs`）。

若希望更抗偶发波动，可改用中位数聚合，并要求候选至少一半回合获胜：

```powershell
python eval/run_greedy_eval.py --case-id 12 --candidate-prompt-file eval/prompts/v2.txt --method official_step --repeats 5 --aggregate median --min-win-rate 0.5 --min-delta 0.0 --no-regress-format --no-regress-key --dry-run
```

### 可选：调用评审智能体（A2A风格输入）

在完成候选评测后，可附加调用评审智能体，综合“案件全文 + 真实判决 + 预测结果 + 提示词”产出优化建议：

```powershell
python eval/run_greedy_eval.py --case-id 12 --candidate-prompt-file eval/prompts/v2.txt --method official_step --run-review-agent
```

输出文件：

- `eval/results/greedy/greedy_case_<id>_<time>_review.json`
- `eval/results/greedy/greedy_case_<id>_<time>_review.md`（人类可读摘要）

并且主报告 `greedy_case_<id>_<time>.json` 的 `decision` 字段会同步写入评审摘要关键信息（如 `review_top_issues`、`review_top_suggestions`、评审文件路径）。

若希望把评审作为“采纳门禁”（业务流程推荐）：

```powershell
python eval/run_greedy_eval.py --case-id 12 --candidate-prompt-file eval/prompts/v2.txt --method official_step --run-review-agent --require-review-acceptable --review-min-score 75 --dry-run
```

说明：

- `--require-review-acceptable`：要求评审结果 `acceptable=true`
- `--review-min-score`：要求评审分达到阈值（0~100）
- 若门禁未通过，即使分数提升也会标记为 `REJECT`

### 决策模式（推荐）

`run_greedy_eval.py` 默认使用 `--decision-mode review`，即：

- 分数继续计算并写入报告（用于参考）
- 最终 `ACCEPT/REJECT` 由评审智能体门禁决定（更直观）

若你希望回到旧逻辑，可显式指定：

```powershell
python eval/run_greedy_eval.py --case-id 12 --candidate-prompt-file eval/prompts/v2.txt --method official_step --decision-mode score --dry-run
```

若你希望“分数+评审都要通过”：

```powershell
python eval/run_greedy_eval.py --case-id 12 --candidate-prompt-file eval/prompts/v2.txt --method official_step --run-review-agent --decision-mode hybrid --dry-run
```
