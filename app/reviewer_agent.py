from __future__ import annotations

import json
import re
from typing import Any, Dict, TypedDict

from openai import OpenAI

from settings import settings


class A2AReviewPayload(TypedDict):
    case_id: int
    case_type: str
    full_case_content: str
    actual_result: str
    predicted_result: str
    predictor_prompt_template: str
    predictor_method: str


def _build_client() -> OpenAI:
    return OpenAI(
        api_key=settings.SILICONFLOW_API_KEY,
        base_url=settings.SILICONFLOW_BASE_URL,
    )


def _extract_json_candidates(text: str) -> list[str]:
    candidates: list[str] = []
    raw = (text or "").strip()
    if not raw:
        return candidates

    candidates.append(raw)

    fenced_blocks = re.findall(r"```(?:json)?\s*(.*?)```", raw, flags=re.S | re.I)
    for block in fenced_blocks:
        block_text = block.strip()
        if block_text:
            candidates.append(block_text)

    start = raw.find("{")
    if start != -1:
        depth = 0
        in_string = False
        escape = False
        for idx in range(start, len(raw)):
            ch = raw[idx]
            if in_string:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_string = False
                continue

            if ch == '"':
                in_string = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    snippet = raw[start : idx + 1].strip()
                    if snippet:
                        candidates.append(snippet)
                    break

    unique: list[str] = []
    seen = set()
    for item in candidates:
        normalized = item.strip()
        if not normalized or normalized in seen:
            continue
        unique.append(normalized)
        seen.add(normalized)
    return unique


def _parse_review_json(raw_text: str) -> Dict[str, Any]:
    candidates = _extract_json_candidates(raw_text)
    errors: list[str] = []

    for candidate in candidates:
        normalized_candidate = (
            candidate
            .replace("```json", "")
            .replace("```JSON", "")
            .replace("```", "")
            .strip()
        )

        try:
            return json.loads(normalized_candidate)
        except Exception as exc:
            errors.append(str(exc))

        try:
            return json.loads(normalized_candidate, strict=False)
        except Exception as exc:
            errors.append(str(exc))

        key = '"revised_prompt_template"'
        key_index = normalized_candidate.find(key)
        if key_index != -1:
            fallback_candidate = normalized_candidate[:key_index] + '"revised_prompt_template": ""\n}'
            try:
                return json.loads(fallback_candidate, strict=False)
            except Exception as exc:
                errors.append(str(exc))

    raise ValueError(
        "无法解析评审JSON；候选数量="
        f"{len(candidates)}；最后错误="
        f"{errors[-1] if errors else 'unknown'}"
    )


def review_prediction_with_agent(payload: A2AReviewPayload) -> Dict[str, Any]:
    """A2A风格评审智能体：评估预测可用性并给出提示词迭代建议。"""
    if not settings.SILICONFLOW_API_KEY:
        return {
            "success": False,
            "message": "评审智能体未执行：SILICONFLOW_API_KEY 未配置",
            "acceptable": False,
            "overall_score": 0,
            "issues": [],
            "prompt_optimization_suggestions": [],
            "revised_prompt_template": "",
        }

    system_prompt = (
        "你是法律判决预测评审智能体。"
        "你将收到案件全文、真实判决、预测判决和预测提示词。"
        "请严格输出JSON，不要输出任何额外说明。"
    )

    user_prompt = f"""
请从以下维度审查预测结果是否可用：
1) 事实一致性（是否引入案情外事实）
2) 核心要素一致性（罪名/金额/刑期/责任/程序动作）
3) 格式合规性（是否为规范主文）
4) 可采纳性（是否可用于提示词迭代）

返回 JSON（严格按键名）：
{{
  "acceptable": true/false,
  "overall_score": 0-100,
  "issues": [{{"type":"...","severity":"high|medium|low","detail":"..."}}],
  "prompt_optimization_suggestions": ["..."],
  "revised_prompt_template": "..."
}}

输入数据：
- case_id: {payload.get('case_id')}
- case_type: {payload.get('case_type')}
- predictor_method: {payload.get('predictor_method')}

[案件全文]
{payload.get('full_case_content', '')[:10000]}

[真实判决结果]
{payload.get('actual_result', '')[:4000]}

[预测判决结果]
{payload.get('predicted_result', '')[:4000]}

[预测提示词模板]
{payload.get('predictor_prompt_template', '')[:8000]}
""".strip()

    try:
        client = _build_client()
        response = client.chat.completions.create(
            model=settings.SILICONFLOW_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
            max_tokens=1400,
            timeout=settings.SILICONFLOW_TIMEOUT,
        )

        raw_text = (response.choices[0].message.content or "").strip()
        parsed = _parse_review_json(raw_text)

        return {
            "success": True,
            "message": "ok",
            "acceptable": bool(parsed.get("acceptable", False)),
            "overall_score": int(parsed.get("overall_score", 0) or 0),
            "issues": parsed.get("issues", []) or [],
            "prompt_optimization_suggestions": parsed.get("prompt_optimization_suggestions", []) or [],
            "revised_prompt_template": parsed.get("revised_prompt_template", "") or "",
            "raw": parsed,
            "raw_text": raw_text,
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"评审智能体执行失败: {e}",
            "acceptable": False,
            "overall_score": 0,
            "issues": [],
            "prompt_optimization_suggestions": [],
            "revised_prompt_template": "",
            "raw_text": (locals().get("raw_text") or "")[:2000],
        }
