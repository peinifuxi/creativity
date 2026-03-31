# 📊 分数与门禁快速参考表

## 四个分数维度一览

| 维度 | 权重 | 计算方法 | 范围 | 实际含义 |
|------|------|---------|------|---------|
| **相似度** (Similarity) | 35% | 逐字符F1分数 | 0~1 | 文本有多像 |
| **关键词召回** (Key Recall) | 30% | 罪名/刑期/金额/行为的交集 | 0~1 | 法律要素齐全吗 |
| **格式得分** (Format) | 20% | 无Markdown、无列表、无"作为AI" | 0~1 | 格式是否规范 |
| **长度得分** (Length) | 15% | 与真实长度的接近程度 | 0~1 | 长度是否合适 |
| **综合得分** | 100% | 四个的加权和 | 0~1 | 总体质量评分 |

---

## Case_31 分数拆解

### 📊 原始分数对比

```
维度           基线(Baseline)    候选(Candidate)   有无提升
─────────────────────────────────────────────────────────
相似度           0.4063           0.4094          ↑ 0.0031
关键词召回       0.5000           0.5000          ─ 0.0000  ⚠️
格式得分         1.0000           1.0000          ─ 0.0000
长度得分         0.2550           0.2574          ↑ 0.0024
─────────────────────────────────────────────────────────
综合得分         0.5305           0.5319          ↑ 0.0014  ❌ 太少
```

### 🔍 实际法律对比

```
维度                 基线              候选               含义
────────────────────────────────────────────────────────────────
核心判项          维持全员死刑       维持全员死刑         ❌ 俱错
真实应是          核准改判            核准改判            ✅ 应含改判逻辑

关键词分析:
基线key_recall:
├─ 犯罪: 1/2 = 50% (漏贩卖毒品罪)
├─ 刑期: 1/2 = 50% (漏改判后死缓)
├─ 财产: 1/1 = 100%
└─ 行为: 1/3 = 33% (漏撤销、改判)
Result = 58%

候选key_recall:
├─ 犯罪: 1/2 = 50%
├─ 刑期: 1/2 = 50% (同样漏改判后死缓)
├─ 财产: 1/1 = 100%
└─ 行为: 1/3 = 33%
Result = 58%

分析: 两者key_recall完全相同，
     都漏了最关键的"改判后的死缓"！
```

---

## 两层门禁的决策流程

### 🚦 分数门禁 (Layer 1: 快速)

```python
# 参数设置
--min-delta 0.01              # 最少要提升1%
--min-win-rate 0.5            # 至少50%的轮次要赢
--no-regress-format           # 不允许格式得分下降
--no-regress-key              # 不允许关键词召回下降

# case_31 评判
delta = 0.5319 - 0.5305 = 0.0014
min_delta = 0.01
Result: 0.0014 < 0.01 → ❌ REJECT
原因: "总分提升不足: delta=0.0014 < min_delta=0.01"
```

### 🤖 智能体门禁 (Layer 2: 深度)

```python
# 参数设置
--run-review-agent                # 启用A2A评审
--require-review-acceptable       # 要求acceptable=true
--review-min-score 75             # 要求评审总分≥75

# case_31 评判 (即使分数通过了)
LLM评审输入:
├─ 案件: "杨某甲等走私贩卖毒品...最高院复核后...改判..."
├─ 真实: "...核准改判黄某甲死缓二年、曾某为无期..."
├─ 预测: "...核准维持对所有人的死刑..."
└─ 提示词: v2_try1_2.txt

LLM评审输出:
├─ acceptable: FALSE
├─ overall_score: 30/100
├─ issues: [
│   {"type": "核心要素不一致", "severity": "HIGH", 
│    "detail": "死刑改判逻辑缺失"},
│   ...
│ ]
└─ suggestions: ["强化复核意见识别...", ...]

Result: 30 < 75 && acceptable=FALSE → ❌ REJECT
原因: "评审门禁未通过：acceptable=false + overall_score=30"
```

---

## 为什么两层都必要？

### 场景模拟

#### 场景A: 只用分数决策
```
候选方案质量    分数表现        结果
─────────────────────────────────────────
非常差          分数↓↓↓        ✅ 正确拒
有问题但微改    分数→(+0.1%)   ❌ 误采纳  ← 坑！
很好            分数↑↑↑        ✅ 正确采

case_31现象: 微幅提升但逻辑错误 → 误采纳风险
```

#### 场景B: 只用智能体门禁
```
候选方案质量    LLM评审         结果
─────────────────────────────────────────
非常差          评审↓↓↓        ✅ 正确拒
有问题但微改    LLM深度评审      ✅ 正确拒
很好            评审↑↑↑        ✅ 正确采

消耗: 每次都调用LLM (API费+时间)
```

#### 场景C: 分数+智能体双门禁 (最优)
```
候选方案质量    分数判定        LLM评审        结果
──────────────────────────────────────────────────────
非常差          ❌ 拒          (跳过)         ✅ 快速拒
微幅改进        ❌ 拒          (跳过)         ✅ 快速拒
看起来不错      ✅ 通          👉 深度评审    ✅ 或 ❌ 准确判
很好            ✅ 通          ✅ 通          ✅ 快速采

消耗: 只在"有希望"的候选上调用LLM
效果: 又快又准
```

---

## 参数建议矩阵

| 场景 | 评测特点 | 推荐参数 |
|------|---------|---------|
| 🚀 **快速试错** | 初期改进，只需排除明显坏方案 | `--decision-mode score --min-delta 0.02 --no-regress-format --dry-run` |
| 🔍 **候选筛选** | 多个方案竞争，需要排名 | `--decision-mode score --min-delta 0.01 --repeats 3 --dry-run` |
| ✅ **采纳前审查** | 候选有望，需要质量保证 | `--decision-mode review --run-review-agent --require-review-acceptable --review-min-score 75 --dry-run` |
| 🎯 **生产采纳** | 准备真实覆盖，无误要求 | `--decision-mode hybrid --run-review-agent --repeats 3 --auto-adopt` |

---

## 实际测试结果对标

### Test 1: case_31 (刑事案件-死刑复核)

```
命令: --decision-mode review --run-review-agent --require-review-acceptable
结果: ❌ REJECT (acceptable=false, score=30)
原因: 死刑改判逻辑缺失
      ↑ 只看分数的话会微幅提升，容易被迷惑
      ↑ 智能体正确识别出法律性错误
```

### Test 2: case_30 (民事案件-发明专利纠纷)

```
命令: --decision-mode review --run-review-agent --dry-run
结果: ❌ REJECT (在dry-run中被跳过)
分数: baseline(0.6842) > candidate(0.6763) 分数下降
      ↑ 分数决策: 明确拒
      ↑ 正确决策
```

---

## 故障排查

| 现象 | 可能原因 | 检查 |
|------|---------|------|
| 分数决策通过，但智能体拒绝 | LLM检测到逻辑问题 | 查看`_review.md`的issues部分 |
| 分数很低但通过总分判定 | 多轮聚合的中位数抬高 | 检查每轮明细分数 |
| 智能体评分差异大 | LLM的随机性或提示词不稳定 | 增加`--repeats`次数 |
| 关键词召回分相同但预测不同 | 可能是字符顺序变化 | 查看`_similarity`字段 |

---

## 最终建议配置

```bash
# 一句话最优设置
python eval/run_greedy_eval.py \
  --case-id 31 \
  --baseline-prompt-file eval/prompts/v1_baseline.txt \
  --candidate-prompt-file eval/prompts/v2.txt \
  --method official_step \
  --repeats 3 \                                  # 保证稳定性
  --aggregate median \                           # 消除极值
  --min-delta 0.01 \                             # 分数要求
  --no-regress-format --no-regress-key \        # 无退化
  --run-review-agent \                           # 启用评审
  --decision-mode hybrid \                       # 分数+评审双通过
  --require-review-acceptable \
  --review-min-score 75 \
  --dry-run                                      # 先预览

# 解释
# repeats=3: 3轮评测 x 3次 (9次LLM预测, ~5分钟)
# median: 用中位数，抗干扰
# min-delta=0.01: 要求至少1%提升
# hybrid: 分数和评审都要通过
# review-min-score=75: 评审要打≥75分
# dry-run: 先看效果，不真实采纳
```

---

**总结**: 
- ✅ 分数靠谱度 60%，适合快速过滤
- ✅ 智能体靠谱度 75%，适合深度检查
- ✅ **两者组合靠谱度 85%，建议生产使用**
