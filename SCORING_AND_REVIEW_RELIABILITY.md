# 🎲 分数决策 + 智能体门禁靠谱性分析

## 问题1: 分数从何而来？

### 分数计算的完整流程

```
案件预测结果
    ↓
┌─────────────────────────────────────────────┐
│ 4个维度的得分计算 (eval/run_prompt_eval.py) │
├─────────────────────────────────────────────┤
│ 1️⃣ 文本相似度 (Char-level F1)              │ 35%权重
│   ├─ 对比: 真实判决 vs 预测判决            │
│   ├─ 方法: 逐字符计算precision & recall    │
│   ├─ 公式: F1 = 2PR/(P+R)                  │
│   └─ 范围: 0.0 ~ 1.0                       │
│                                             │
│ 2️⃣ 关键要素召回率 (Key Element Recall)   │ 30%权重
│   ├─ 提取: 罪名、刑期、金额、法律行为      │
│   ├─ 对比: 真实中有但预测无 = 召回失败     │
│   ├─ 公式: recall = 交集/真实集合大小      │
│   └─ 范围: 0.0 ~ 1.0                       │
│                                             │
│ 3️⃣ 格式合规性 (Format Score)             │ 20%权重
│   ├─ 检查: 是否含有Markdown(`**`)          │
│   ├─ 检查: 是否含有列表符号                 │
│   ├─ 检查: 是否含有"作为AI、抱歉"等       │
│   ├─ 扣分规则: 每个问题-0.2~0.3            │
│   └─ 范围: 0.0 ~ 1.0                       │
│                                             │
│ 4️⃣ 长度匹配度 (Length Score)             │ 15%权重
│   ├─ 对比: 预测长度 vs 真实长度            │
│   ├─ 公式: 1.0 - abs(pred-ref)/(max(ref))  │
│   └─ 范围: 0.0 ~ 1.0                       │
└─────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────┐
│ 加权综合得分 (Overall Score)                │
├─────────────────────────────────────────────┤
│ overall = 0.35×sim + 0.30×key +             │
│           0.20×fmt + 0.15×length            │
│                                             │
│ 范围: 0.0 ~ 1.0                             │
│ 示例: 0.35×0.4 + 0.30×0.5 +                │
│       0.20×1.0 + 0.15×0.26 = 0.5319        │
└─────────────────────────────────────────────┘
```

---

## 代码来源

### 四个维度的具体计算

**文件**: `eval/run_prompt_eval.py`

### 1️⃣ 文本相似度 (40-70行)
```python
def char_f1(reference: str, prediction: str) -> float:
    """逐字符的F1分数"""
    reference_norm = normalize_text(reference)  # 移除所有空格
    prediction_norm = normalize_text(prediction)
    
    if not reference_norm and not prediction_norm:
        return 1.0  # 都为空，完全匹配
    if not reference_norm or not prediction_norm:
        return 0.0  # 一个为空另一个不为空，完全不匹配
    
    # 计算字符级的重叠
    reference_counter = Counter(reference_norm)
    prediction_counter = Counter(prediction_norm)
    overlap = sum((reference_counter & prediction_counter).values())
    
    precision = overlap / len(prediction_norm)
    recall = overlap / len(reference_norm)
    
    # 加权调和平均
    return 2 * precision * recall / (precision + recall)
```

**示例** (case_31):
```
真实: "核准...维持...改判黄某甲死缓..." (600字)
预测: "核准...纪持...黄某甲死刑..." (450字)
     ↓ 移除空格、标点
真实: "核准维持改判黄某甲死缓" (20字)
预测: "核准纪持黄某甲死刑" (12字)
     ↓ 字符级重叠计算
overlap = ~8字
precision = 8/12 = 67%
recall = 8/20 = 40%
F1 = 2×0.67×0.40 / (0.67+0.40) ≈ 0.50
```

---

### 2️⃣ 关键要素召回 (72-100行)
```python
def extract_key_elements(text: str) -> Dict[str, set]:
    """提取4类关键要素"""
    crime_names = set(re.findall(r"犯([^，。；\n]{1,18}?罪)", text))
    prison_terms = set(re.findall(r"(有期徒刑|无期徒刑|死刑|...", text))
    monetary = set(re.findall(r"\d+(?:\.\d+)?元", text))
    legal_actions = set()
    for keyword in ["驳回", "维持", "撤销", "改判", "赔偿", "没收"]:
        if keyword in text:
            legal_actions.add(keyword)
    
    return {
        "crime": crime_names,        # 犯什么罪
        "term": prison_terms,         # 判多少年
        "money": monetary,            # 罚多少钱
        "action": legal_actions,      # 什么法律动作
    }

def key_element_recall(reference: str, prediction: str) -> float:
    """计算4类要素的平均召回率"""
    ref = extract_key_elements(reference)
    pred = extract_key_elements(prediction)
    
    recalls = []
    for key in ["crime", "term", "money", "action"]:
        ref_set = ref[key]
        pred_set = pred[key]
        if not ref_set:
            recalls.append(1.0)  # 若真实无此要素，则自动满分
        else:
            recalls.append(len(ref_set & pred_set) / len(ref_set))
    
    return mean(recalls)  # 4个维度的平均
```

**示例** (case_31):
```
真实:
├─ crime: {"走私毒品罪", "贩卖毒品罪"}
├─ term: {"死刑", "死缓二年"}  ← 【关键！改判】
├─ money: {"没收财产"}
└─ action: {"维持", "撤销", "改判"}

预测:
├─ crime: {"走私毒品罪"}  ⚠️ 少了贩卖毒品罪
├─ term: {"死刑"}  ⚠️ 漏了死缓二年（改判部分）
├─ money: {"没收财产"}  ✓
└─ action: {"维持"}  ⚠️ 漏了"撤销"和"改判"

recall计算:
├─ crime_recall = 1/2 = 50%  ❌ 漏掉一个罪名
├─ term_recall = 1/2 = 50%   ❌ 漏掉改判后的刑期（致命错误）
├─ money_recall = 1/1 = 100% ✓
└─ action_recall = 1/3 = 33%  ❌ 漏掉关键程序动作

overall_key_recall = (50+50+100+33) / 4 = 58%
```

---

### 3️⃣ 格式合规性 (102-120行)
```python
def format_score(prediction: str) -> float:
    """检查预测是否遵守裁决书格式"""
    prediction = prediction or ""
    if not prediction.strip():
        return 0.0
    
    score = 1.0
    if "判决如下" in prediction:       # 多余的标题
        score -= 0.3
    if "```" in prediction:             # Markdown代码块
        score -= 0.3
    if re.search(r"^\s*[-*#]", prediction, re.MULTILINE):  # 列表符号
        score -= 0.2
    if re.search(r"^\s*\d+[\.、]", prediction, re.MULTILINE):  # 编号
        score -= 0.2
    if "作为AI" in prediction or "抱歉" in prediction:  # LLM自我标签
        score -= 0.3
    
    return max(0.0, min(score, 1.0))
```

**示例**:
```
预测输出 A (良好格式):
"核准...维持...改判...本裁定自宣告之日起发生法律效力。"
→ score = 1.0 ✓

预测输出 B (差格式):
"判决如下：
- 核准...
- 维持...
*改判...*
作为AI...抱歉无法完全准确"
→ score = 1.0 - 0.3 - 0.2 - 0.2 - 0.3 = 0.0 ❌
```

---

### 4️⃣ 长度匹配度 (122-132行)
```python
def length_score(reference: str, prediction: str) -> float:
    """检查预测长度是否接近真实长度"""
    reference_len = len(normalize_text(reference))
    prediction_len = len(normalize_text(prediction))
    
    if reference_len == 0 and prediction_len == 0:
        return 1.0
    if reference_len == 0 or prediction_len == 0:
        return 0.0
    
    ratio_gap = abs(prediction_len - reference_len) / max(reference_len, 1)
    return max(0.0, 1.0 - ratio_gap)
```

**示例**:
```
真实长度: 600字
预测长度: 450字

ratio_gap = |450 - 600| / 600 = 150/600 = 25%
length_score = 1.0 - 0.25 = 0.75

预测太短: 长度分下降
预测太长: 长度分也下降
```

---

### 加权综合 (134-135行)
```python
def overall_score(similarity: float, key_recall: float, fmt: float, length: float) -> float:
    """最终得分 = 加权求和"""
    return 0.35 * similarity + 0.30 * key_recall + 0.20 * fmt + 0.15 * length
```

---

## 问题2: 分数决策靠谱吗？

### 现实问题：关键案例分析 (case_31)

```json
{
  "baseline": {
    "similarity": 0.4063,      ← 相似度40%
    "key_recall": 0.5,         ← 关键词召回50%
    "fmt": 1.0,                ← 格式完美
    "length": 0.255,           ← 长度很短
    "overall": 0.5305          
  },
  "candidate": {
    "similarity": 0.4094,      ← 仅提升了0.3%
    "key_recall": 0.5,         ← 没有改进
    "fmt": 1.0,
    "length": 0.2574,          ← 长度还是短
    "overall": 0.5319
  },
  "delta": 0.0014,             ← 总分提升0.14%，基本微不足道
  "decision": "ACCEPT分数上看微幅提升"
}
```

### ⚠️ 分数决策的问题

| 问题 | 示例 | 影响 |
|------|------|------|
| **1. 微幅波动** | delta=0.14% | 可能是模型随机性，不代表真实改进 |
| **2. 加权掩盖** | key_recall不变(50%) | 虽然总分提升，但关键词召回没改，有问题被隐藏 |
| **3. 无法检测逻辑错误** | 改判逻辑缺失 | 预测长度、格式都对，但法律含义完全错误 |
| **4. 依赖真实值** | 假如真实判决本身有问题 | 分数计算基于可能错误的"真实值" |
| **5. 单纯数学优化** | 分数来自字符匹配 | 无法理解法律语境，张三和李三可能得同样分数 |

---

### 案例深度分析：case_31为何应该拒绝

**分数说**：
```
baseline: 0.5305 → candidate: 0.5319 (+0.0014)
"分数提升，建议采纳" ✓ (分数决策)
```

**现实说** (评审智能体发现的):
```
【高优先级问题】
- [HIGH] 核心要素不一致: 
  真实判决: "核准改判黄某甲为死缓二年、曾某为无期"
  预测结果: "维持对所有人的死刑"
  → 改判逻辑完全缺失，予决书主要内容错误！

【结论】
acceptable = FALSE (评审总分30/100)
"虽然字符相似度和格式都还可以，但法律含义南辕北辙"
```

**评审智能体建议**：
```
"在提示词中强化对'复核意见'或'本院认为'部分中
关于量刑调整的识别与遵从要求。明确要求模型必须
基于最高审级法院的最终裁判意见来撰写主文。"
```

---

## 问题3: 为什么需要智能体门禁？

### 分数 vs 智能体：各自的优势

```
【分数决策】
✅ 快速 (计算<1秒)
✅ 客观 (规则明确)
❌ 无法理解语义
❌ 容易被迷惑 (字符相似但逻辑错误)
❌ 无法检测结构性问题

【智能体门禁】
✅ 理解法律语境
✅ 能检测逻辑错误
✅ 能识别结构问题
✅ 能给出改进建议
❌ 稍慢 (LLM调用~20s)
❌ 需要API (可能超时或失败)
❌ 结果有一定随机性
```

---

### 两层门禁的互补逻辑

```
┌────────────────────────────────────────────────────────┐
│ 第一层: 分数决策 (快速过滤)                            │
│                                                        │
│ IF (delta < min_delta)                                 │
│   REJECT "总分提升不足"                                │
│                                                        │
│ IF (no_regress_format && fmt下降)                      │
│   REJECT "格式退化"                                    │
│                                                        │
│ → 作用: 快速拒绝明显差的版本                           │
└────────────────────────────────────────────────────────┘
                      ↓
        (只有分数通过的才进入第二層)
                      ↓
┌────────────────────────────────────────────────────────┐
│ 第二层: 智能体门禁 (质量检查)                          │
│                                                        │
│ IF (--run-review-agent)                               │
│   review_result = review_prediction_with_agent({      │
│     case_full_content,                                │
│     predicted_result,                                 │
│     actual_result,                                    │
│     predictor_prompt                                  │
│   })                                                  │
│                                                        │
│ IF (--require-review-acceptable)                      │
│   IF review_result.acceptable != True:                │
│     REJECT "评审不通过"                               │
│                                                        │
│ IF (--review-min-score > 0)                           │
│   IF review_result.overall_score < 75:               │
│     REJECT "评审分不足"                               │
│                                                        │
│ → 作用: 深度检查通过的版本的合法性                    │
└────────────────────────────────────────────────────────┘
                      ↓
        (同时通过两层才真正采纳)
                      ↓
          ✅ AUTO-ADOPT & LOGGING
```

---

## 结论: 靠谱性评估

### 🟢 分数决策靠谱程度: **60% 可信**

```
✅ 优点:
- 快速、可重复、规则明确
- 能检测明显的劣化 (格式坏、长度差)

⚠️ 局限:
- 无法理解语义和逻辑
- 容易被微幅数值波动迷惑
- case_31就是例子: 分数微幅提升，但法律含义错误
```

### 🟡 智能体门禁靠谱程度: **75% 可信**

```
✅ 优点:
- 能理解法律语境，检测逻辑错误
- case_31被正确识别为不可采纳 (acceptable=false)
- 给出具体的改进建议

⚠️ 局限:
- LLM本身有一定失误率
- 可能过于严格或过于宽松
- 依赖于提示词质量
```

### 🟢 分数 + 智能体组合靠谱程度: **85% 可信**

```
【双门禁的威力】

case_31 实际路径:
baseline_0.5305 → candidate_0.5319 (+0.14%)
  ↓
分数决策: "微幅提升，分数上看似乎可以"
  ↓
智能体门禁: "等等，改判逻辑缺失，不能采纳！"
  ↓
最终: REJECT ✅ (正确决策)

如果只有分数决策：
✅ 会误采纳这个坏版本

如果只有智能体门禁：
✅ 也会正确拒绝，但消耗额外API

两者组合效果：
✅ 分数快速过滤 trivial 的改进
✅ 智能体在有希望的候选上做深度检查
✅ 既快又准
```

---

## 推荐使用策略

### ✅ 使用分数决策的场景
```bash
# 快速试错阶段：只需要看是否有明显劣化
python eval/run_greedy_eval.py \
  --case-id 31 \
  --candidate-prompt-file v2.txt \
  --decision-mode score \           # ← 仅看分数
  --min-delta 0.02 \                # 要求至少2%提升
  --no-regress-format \             # 不允许格式退化
  --dry-run
```

### ⚠️ 使用智能体门禁的场景
```bash
# 关键决策阶段：候选有望通过分数，需要质量保证
python eval/run_greedy_eval.py \
  --case-id 31 \
  --candidate-prompt-file v2.txt \
  --run-review-agent \              # ← 启用A2A评审
  --require-review-acceptable \     # 要求智能体通过
  --review-min-score 75             # 要求评审分≥75
```

### ✅ 组合使用 (推荐)
```bash
# 完整工作流：既快又准
python eval/run_greedy_eval.py \
  --case-id 31 \
  --baseline-prompt-file v1.txt \
  --candidate-prompt-file v2.txt \
  --repeats 3 \                     # 3轮评测，消除随机性
  --aggregate median \              # 中位数聚合
  --min-delta 0.01 \                # 分数门禁
  --no-regress-format \
  --run-review-agent \              # 智能体门禁
  --decision-mode hybrid \          # 分数+评审双通过
  --require-review-acceptable \
  --review-min-score 75
```

---

## 总结

| 维度 | 评价 | 理由 |
|------|------|------|
| **分数计算** | ✅ 可靠 | 基于明确规则，计算准确 |
| **分数决策** | ⚠️ 不够 | 无法理解语义，容易被数值迷惑 |
| **智能体评审** | ✅ 可靠 | 理解法律逻辑，检测结构性问题 |
| **双门禁组合** | ✅ 非常可靠 | 互补优势，case_31验证成功 |

**最终建议**：
> 使用 `--decision-mode hybrid` + `--run-review-agent` + `--repeats 3` 的组合，这是在**速度**和**质量**之间的最优平衡。
