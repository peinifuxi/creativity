from __future__ import annotations

import re
from typing import Any, Dict, List, TypedDict

from langgraph.graph import END, START, StateGraph
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from settings import settings


class WorkflowState(TypedDict, total=False):
    original_content: str
    processed_content: str
    case_type_input: str
    case_type_detected: str
    prompt_template_override: str
    selected_prompt_template: str
    final_prompt: str
    prediction: str
    validation_errors: List[str]
    retry_count: int
    max_retries: int
    route_name: str


CRIMINAL_PROMPT = """
你是刑事审判主文生成助手。请基于给定案情生成裁判主文，并严格满足：
1) 仅输出主文，不要解释；
2) 不输出“判决如下”字样；
3) 罪名、刑期、附加刑、并罚规则、刑期折抵必须明确；
4) 不得引入案情外事实。

【案件类型】
{case_type}

【待预测案情（不含最终判决主文）】
{content}

请直接输出最终判决主文。
""".strip()


CIVIL_PROMPT = """
你是民事审判主文生成助手。请基于给定案情生成裁判主文，并严格满足：
1) 仅输出主文，不要解释；
2) 不输出“判决如下”字样；
3) 明确给付义务、金额、期限、责任承担方式；
4) 明确诉讼费用负担；
5) 不得引入案情外事实。

【案件类型】
{case_type}

【待预测案情（不含最终判决主文）】
{content}

请直接输出最终判决主文。
""".strip()


ADMIN_PROMPT = """
你是行政审判主文生成助手。请基于给定案情生成裁判主文，并严格满足：
1) 仅输出主文，不要解释；
2) 不输出“判决如下”字样；
3) 明确被诉行政行为处理（维持/撤销/确认违法/责令履行等）；
4) 明确诉讼费用负担；
5) 不得引入案情外事实。

【案件类型】
{case_type}

【待预测案情（不含最终判决主文）】
{content}

请直接输出最终判决主文。
""".strip()


GENERAL_PROMPT = """
你是司法裁判主文生成助手。请基于给定案情生成规范主文，并严格满足：
1) 仅输出主文，不要解释；
2) 不输出“判决如下”字样；
3) 结构清晰、用语正式；
4) 不得引入案情外事实。

【案件类型】
{case_type}

【待预测案情（不含最终判决主文）】
{content}

请直接输出最终判决主文。
""".strip()


def _strip_judgement_section(content: str) -> str:
    text = (content or "").strip()
    if not text:
        return ""

    split_patterns = [
        r"判决如下[:：]",
        r"裁定如下[:：]",
        r"主文[:：]",
        r"判决结果[:：]",
    ]

    for pattern in split_patterns:
        match = re.search(pattern, text)
        if match:
            return text[: match.start()].strip()

    return text


def _detect_case_type(text: str, case_type_input: str) -> str:
    if case_type_input in {"刑事案件", "民事案件", "行政案件"}:
        return case_type_input

    source = f"{case_type_input}\n{text}"
    if any(token in source for token in ["公诉机关", "被告人", "有期徒刑", "罪"]):
        return "刑事案件"
    if any(token in source for token in ["原告", "被告", "合同", "侵权", "赔偿"]):
        return "民事案件"
    if any(token in source for token in ["行政机关", "行政行为", "行政处罚", "确认违法"]):
        return "行政案件"
    return "其他"


def _build_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=settings.SILICONFLOW_MODEL,
        api_key=settings.SILICONFLOW_API_KEY,
        base_url=settings.SILICONFLOW_BASE_URL,
        temperature=0.2,
        timeout=settings.SILICONFLOW_TIMEOUT,
    )


def _preprocess_node(state: WorkflowState) -> WorkflowState:
    processed = _strip_judgement_section(state.get("original_content", ""))
    if len(processed) < 20:
        processed = (state.get("original_content") or "")[:3000]
    return {"processed_content": processed[:3000]}


def _classify_node(state: WorkflowState) -> WorkflowState:
    detected = _detect_case_type(
        text=state.get("processed_content", ""),
        case_type_input=state.get("case_type_input", "其他"),
    )
    return {"case_type_detected": detected}


def _route_case_type(state: WorkflowState) -> str:
    case_type = state.get("case_type_detected", "其他")
    if case_type == "刑事案件":
        return "criminal"
    if case_type == "民事案件":
        return "civil"
    if case_type == "行政案件":
        return "admin"
    return "general"


def _prepare_criminal_prompt(state: WorkflowState) -> WorkflowState:
    return {
        "selected_prompt_template": state.get("prompt_template_override") or CRIMINAL_PROMPT,
        "route_name": "criminal",
    }


def _prepare_civil_prompt(state: WorkflowState) -> WorkflowState:
    return {
        "selected_prompt_template": state.get("prompt_template_override") or CIVIL_PROMPT,
        "route_name": "civil",
    }


def _prepare_admin_prompt(state: WorkflowState) -> WorkflowState:
    return {
        "selected_prompt_template": state.get("prompt_template_override") or ADMIN_PROMPT,
        "route_name": "admin",
    }


def _prepare_general_prompt(state: WorkflowState) -> WorkflowState:
    return {
        "selected_prompt_template": state.get("prompt_template_override") or GENERAL_PROMPT,
        "route_name": "general",
    }


def _draft_node(state: WorkflowState) -> WorkflowState:
    template = state.get("selected_prompt_template") or GENERAL_PROMPT
    case_type = state.get("case_type_detected") or "其他"
    content = state.get("processed_content") or ""

    final_prompt = template.format(case_type=case_type, content=content)

    llm = _build_llm()
    response = llm.invoke(
        [
            SystemMessage(content="你是专业法律助手，输出准确、结构化、可读的中文判决预测分析结果。"),
            HumanMessage(content=final_prompt),
        ]
    )

    prediction = (response.content or "").strip()
    return {
        "final_prompt": final_prompt,
        "prediction": prediction,
    }


def _validate_node(state: WorkflowState) -> WorkflowState:
    prediction = (state.get("prediction") or "").strip()
    errors: List[str] = []

    if not prediction:
        errors.append("模型未返回预测文本")
    if "判决如下" in prediction:
        errors.append("包含禁用短语：判决如下")
    if re.search(r"^\s*[-*#]", prediction, re.MULTILINE):
        errors.append("输出包含Markdown列表，不符合主文格式")

    case_type = state.get("case_type_detected", "其他")
    if case_type == "刑事案件" and not any(token in prediction for token in ["有期徒刑", "拘役", "管制", "无期徒刑", "死刑"]):
        errors.append("刑事主文缺少量刑信息")
    if case_type == "民事案件" and not any(token in prediction for token in ["赔偿", "给付", "支付"]):
        errors.append("民事主文缺少给付类判项")
    if case_type == "行政案件" and not any(token in prediction for token in ["撤销", "维持", "确认违法", "责令"]):
        errors.append("行政主文缺少行政行为处理结论")

    return {"validation_errors": errors}


def _need_repair_route(state: WorkflowState) -> str:
    errors = state.get("validation_errors") or []
    retry_count = state.get("retry_count", 0)
    max_retries = state.get("max_retries", 2)

    if errors and retry_count < max_retries:
        return "repair"
    return "finish"


def _repair_node(state: WorkflowState) -> WorkflowState:
    prediction = state.get("prediction", "")
    errors = state.get("validation_errors") or []
    retry_count = state.get("retry_count", 0) + 1

    repair_hint = "\n".join(f"- {item}" for item in errors)
    revised_template = (
        (state.get("selected_prompt_template") or GENERAL_PROMPT)
        + "\n\n【上轮输出存在以下问题，必须修复】\n"
        + repair_hint
        + "\n请输出修复后的最终主文。"
    )

    return {
        "selected_prompt_template": revised_template,
        "retry_count": retry_count,
        "prediction": prediction,
    }


def _build_graph() -> Any:
    graph = StateGraph(WorkflowState)

    graph.add_node("preprocess", _preprocess_node)
    graph.add_node("classify", _classify_node)
    graph.add_node("prepare_criminal", _prepare_criminal_prompt)
    graph.add_node("prepare_civil", _prepare_civil_prompt)
    graph.add_node("prepare_admin", _prepare_admin_prompt)
    graph.add_node("prepare_general", _prepare_general_prompt)
    graph.add_node("draft", _draft_node)
    graph.add_node("validate", _validate_node)
    graph.add_node("repair", _repair_node)

    graph.add_edge(START, "preprocess")
    graph.add_edge("preprocess", "classify")

    graph.add_conditional_edges(
        "classify",
        _route_case_type,
        {
            "criminal": "prepare_criminal",
            "civil": "prepare_civil",
            "admin": "prepare_admin",
            "general": "prepare_general",
        },
    )

    graph.add_edge("prepare_criminal", "draft")
    graph.add_edge("prepare_civil", "draft")
    graph.add_edge("prepare_admin", "draft")
    graph.add_edge("prepare_general", "draft")

    graph.add_edge("draft", "validate")
    graph.add_conditional_edges(
        "validate",
        _need_repair_route,
        {
            "repair": "repair",
            "finish": END,
        },
    )
    graph.add_edge("repair", "draft")

    return graph.compile()


def run_langgraph_prediction(content: str, case_type: str = "其他", prompt_template: str | None = None) -> Dict[str, Any]:
    app = _build_graph()
    final_state = app.invoke(
        {
            "original_content": content,
            "processed_content": "",
            "case_type_input": case_type or "其他",
            "case_type_detected": "",
            "prompt_template_override": prompt_template or "",
            "selected_prompt_template": "",
            "final_prompt": "",
            "prediction": "",
            "validation_errors": [],
            "retry_count": 0,
            "max_retries": 2,
            "route_name": "",
        }
    )

    prediction = (final_state.get("prediction") or "").strip()
    selected_template = final_state.get("selected_prompt_template") or prompt_template or GENERAL_PROMPT

    return {
        "prediction": prediction or "模型未返回预测内容。",
        "used_prompt_template": selected_template,
        "route_name": final_state.get("route_name", "general"),
        "detected_case_type": final_state.get("case_type_detected", case_type or "其他"),
        "validation_errors": final_state.get("validation_errors", []),
        "success": bool(prediction),
    }
