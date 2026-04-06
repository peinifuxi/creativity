from flask import Blueprint, render_template, session, request, redirect, url_for, flash
from .database import db, Case
import re

predict_bp = Blueprint('predict', __name__)

PREDICT_METHOD_OPTIONS = [
    ('official_step', '方案1：DeepSeek 官方直连'),
    ('self_hosted_lawgpt', '方案2：自部署微调模型（LawGPT）'),
    ('coze_workflow', '方案3：Coze 工作流'),
    ('langgraph_workflow', '方案4：LangGraph 多步工作流'),
]

PREDICT_METHOD_LABELS = dict(PREDICT_METHOD_OPTIONS)

TERM_PATTERNS = [
    ('有期徒刑', r'决定执行有期徒刑(?:([零〇一二两三四五六七八九十百千\d]+)年)?(?:([零〇一二两三四五六七八九十百千\d]+)个?月)?'),
    ('有期徒刑', r'判处有期徒刑(?:([零〇一二两三四五六七八九十百千\d]+)年)?(?:([零〇一二两三四五六七八九十百千\d]+)个?月)?'),
    ('有期徒刑', r'有期徒刑(?:([零〇一二两三四五六七八九十百千\d]+)年)?(?:([零〇一二两三四五六七八九十百千\d]+)个?月)?'),
    ('拘役', r'拘役(?:([零〇一二两三四五六七八九十百千\d]+)年)?(?:([零〇一二两三四五六七八九十百千\d]+)个?月)?'),
    ('管制', r'管制(?:([零〇一二两三四五六七八九十百千\d]+)年)?(?:([零〇一二两三四五六七八九十百千\d]+)个?月)?'),
]

TERM_KEYWORDS = ('判处', '决定执行', '死刑', '无期徒刑', '有期徒刑', '拘役', '管制')


def _extract_charges(text: str):
    """提取罪名集合，用于按法律判决预测常用的罪名 F1 衡量。"""
    if not text:
        return []
    charges = set()
    ignored = {'数罪', '本罪', '该罪', '此罪'}
    patterns = [
        r'犯([\u4e00-\u9fa5、]{1,30}?罪)',
        r'以([\u4e00-\u9fa5、]{1,30}?罪)(?:判处|量刑|定罪)',
        r'所犯([\u4e00-\u9fa5、]{1,30}?罪)',
    ]
    for pattern in patterns:
        for charge in re.findall(pattern, text):
            cleaned = charge.strip().strip('，,；;。')
            if cleaned and cleaned not in ignored:
                charges.add(cleaned)
    return sorted(charges)


def _extract_sentence_months(text: str):
    """提取主刑期限，死刑/无期返回特殊值，普通刑期统一折算为月。"""
    return _extract_sentence_info(text).get('months')


def _term_accuracy_score(actual_months, predicted_months):
    """单案明细场景下采用更严格的月数绝对误差评分。"""
    actual_info = _normalize_sentence_info(actual_months)
    predicted_info = _normalize_sentence_info(predicted_months)

    actual_value = actual_info.get('months')
    predicted_value = predicted_info.get('months')
    if actual_value is None or predicted_value is None:
        return None
    if actual_value < 0 or predicted_value < 0:
        if actual_info.get('compare_key', '').startswith('death_reprieve:') and predicted_info.get('compare_key') == 'death':
            return 60.0
        return 100.0 if actual_info.get('compare_key') == predicted_info.get('compare_key') else 0.0

    month_gap = abs(predicted_value - actual_value)
    if month_gap == 0:
        return 100.0
    if month_gap <= 1:
        return 90.0
    if month_gap <= 3:
        return 75.0
    if month_gap <= 6:
        return 55.0
    if month_gap <= 12:
        return 30.0
    return 0.0


def _extract_punishment_severity_level(text: str):
    """
    处罚程度采用序位严重性分级，参考量刑轻重的序数分类思路：
    死刑 > 无期徒刑 > 有期徒刑 > 拘役 > 管制 > 罚金/缓刑/免刑。
    """
    if not text:
        return None
    if '死刑' in text:
        return 5
    if '无期徒刑' in text:
        return 4
    if '有期徒刑' in text:
        return 3
    if '拘役' in text:
        return 2
    if '管制' in text:
        return 1
    if any(keyword in text for keyword in ['罚金', '缓刑', '免予刑事处罚', '免予处罚']):
        return 0
    return None


def _format_sentence_months(months):
    if months is None:
        return '未识别'
    if months == -2:
        return '死刑'
    if months == -1:
        return '无期徒刑'
    years = months // 12
    remain_months = months % 12
    if years and remain_months:
        return f'{years}年{remain_months}个月'
    if years:
        return f'{years}年'
    return f'{remain_months}个月'


def _severity_label(level):
    mapping = {
        5: '死刑',
        4: '无期徒刑',
        3: '有期徒刑',
        2: '拘役',
        1: '管制',
        0: '罚金/缓刑/免罚'
    }
    if level is None:
        return '未识别'
    return mapping.get(level, '未识别')


def _normalize_sentence_info(value):
    if isinstance(value, dict):
        return value
    if value is None:
        return {"months": None, "compare_key": None, "display": "未识别", "sentence_type": "未识别"}
    if value == -1:
        return {"months": -1, "compare_key": "life", "display": "无期徒刑", "sentence_type": "无期徒刑"}
    if value == -2:
        return {"months": -2, "compare_key": "death", "display": "死刑", "sentence_type": "死刑"}
    return {
        "months": value,
        "compare_key": f"term:{value}",
        "display": _format_sentence_months(value),
        "sentence_type": "有期徒刑"
    }


def _parse_legal_number(value):
    if value is None:
        return 0
    text = str(value).strip()
    if not text:
        return 0
    if text.isdigit():
        return int(text)

    mapping = {'零': 0, '〇': 0, '一': 1, '二': 2, '两': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9}
    unit_mapping = {'十': 10, '百': 100, '千': 1000}
    total = 0
    current = 0

    for char in text:
        if char in mapping:
            current = mapping[char]
        elif char in unit_mapping:
            unit = unit_mapping[char]
            if current == 0:
                current = 1
            total += current * unit
            current = 0
    total += current
    return total


def _extract_sentence_info(text: str):
    if not text:
        return {"months": None, "compare_key": None, "display": "未识别", "sentence_type": "未识别"}

    reprieve_match = re.search(r'死刑[,，]?\s*缓期([零〇一二两三四五六七八九十百千\d]+)年执行', text)
    if reprieve_match:
        years = _parse_legal_number(reprieve_match.group(1))
        return {
            "months": -2,
            "compare_key": f"death_reprieve:{years}",
            "display": f"死刑，缓期{years}年执行",
            "sentence_type": "死缓"
        }
    if '死刑' in text:
        return {"months": -2, "compare_key": "death", "display": "死刑", "sentence_type": "死刑"}
    if '无期徒刑' in text:
        return {"months": -1, "compare_key": "life", "display": "无期徒刑", "sentence_type": "无期徒刑"}

    for current_type, pattern in TERM_PATTERNS:
        match = re.search(pattern, text)
        if not match:
            continue
        years = _parse_legal_number(match.group(1))
        months = _parse_legal_number(match.group(2))
        total_months = years * 12 + months
        return {
            "months": total_months,
            "compare_key": f"{current_type}:{total_months}",
            "display": _format_sentence_months(total_months),
            "sentence_type": current_type
        }
    return {"months": None, "compare_key": None, "display": "未识别", "sentence_type": "未识别"}


def _extract_person_name(text: str):
    if not text:
        return None
    patterns = [
        r'被告人[：:\s]*([\u4e00-\u9fa5A-Za-z0-9·]{2,12}?)(?=死刑|无期徒刑|有期徒刑|拘役|管制|，|。|；|;|（|\(|以|犯|的|$)',
        r'对被告人([\u4e00-\u9fa5A-Za-z0-9·]{2,12}?)(?=死刑|无期徒刑|有期徒刑|拘役|管制|，|。|；|;|（|\(|以|犯|的|$)',
        r'上诉人[（(]原审被告人[）)]([\u4e00-\u9fa5A-Za-z0-9·]{2,12}?)(?=死刑|无期徒刑|有期徒刑|拘役|管制|，|。|；|;|（|\(|以|犯|的|$)',
        r'原审被告人([\u4e00-\u9fa5A-Za-z0-9·]{2,12}?)(?=死刑|无期徒刑|有期徒刑|拘役|管制|，|。|；|;|（|\(|以|犯|的|$)',
        r'被执行人([\u4e00-\u9fa5A-Za-z0-9·]{2,12}?)(?=死刑|无期徒刑|有期徒刑|拘役|管制|，|。|；|;|（|\(|以|犯|的|$)',
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1)
    return None


def _extract_charge_from_text(text: str):
    patterns = [
        r'以([\u4e00-\u9fa5、]{1,30}?罪)(?:判处|量刑)',
        r'犯([\u4e00-\u9fa5、]{1,30}?罪)',
        r'所犯([\u4e00-\u9fa5、]{1,30}?罪)',
    ]
    for pattern in patterns:
        matches = re.findall(pattern, text)
        if matches:
            return matches[-1]
    charges = _extract_charges(text)
    return charges[0] if charges else None


def _contains_term_keywords(text: str):
    return bool(text and any(keyword in text for keyword in TERM_KEYWORDS))


def _normalize_result_for_term_extraction(text: str):
    if not text:
        return ''
    normalized = re.sub(r'\s+', ' ', text).strip()
    for marker in ('判决如下：', '判决如下:', '裁定如下：', '裁定如下:', '决定如下：', '决定如下:'):
        if marker in normalized:
            normalized = normalized.split(marker, 1)[1].strip()
            break
    return normalized


def _trim_term_clause(clause: str):
    if not clause:
        return ''
    clause = re.sub(r'\s+', ' ', clause).strip(' ，,；;。！!？?\n\t')
    clause = re.sub(r'^[一二三四五六七八九十]+、', '', clause).strip()
    return clause


def _find_nearest_boundary(text: str, index: int, reverse: bool):
    boundaries = ['。', '；', ';', '\n']
    if reverse:
        positions = [text.rfind(marker, 0, index) for marker in boundaries]
        return max(positions)
    positions = [text.find(marker, index) for marker in boundaries if text.find(marker, index) != -1]
    return min(positions) if positions else -1


def _extract_context_person(text: str, match_start: int):
    local_prefix = text[max(0, match_start - 80):match_start]
    return _extract_person_name(local_prefix) or _extract_person_name(text[:match_start])


def _extract_context_charge(text: str, match_start: int):
    local_prefix = text[max(0, match_start - 80):match_start]
    charge_patterns = [
        r'(?:犯|以|所犯)([\u4e00-\u9fa5、]{1,30}?罪)',
    ]
    for target in (local_prefix, text[:match_start]):
        for pattern in charge_patterns:
            matches = re.findall(pattern, target)
            if matches:
                return matches[-1]
    return None


def _extract_probation_info(text: str):
    match = re.search(r'缓刑([零〇一二两三四五六七八九十百千\d]+)年(?:([零〇一二两三四五六七八九十百千\d]+)个?月)?', text)
    if not match:
        return None
    years = _parse_legal_number(match.group(1))
    months = _parse_legal_number(match.group(2))
    total_months = years * 12 + months
    if total_months <= 0:
        return None
    if years and months:
        display = f'缓刑{years}年{months}个月'
    elif years:
        display = f'缓刑{years}年'
    else:
        display = f'缓刑{months}个月'
    return {
        "months": total_months,
        "display": display,
    }


def _sentence_display_with_probation(sentence_info: dict, text: str):
    base_display = sentence_info.get('display', '未识别')
    probation = _extract_probation_info(text)
    if not probation:
        return base_display
    return f"{base_display}，{probation['display']}"


def _make_structured_term_item(person: str | None, charge: str | None, category: str, clause: str):
    sentence_info = _extract_sentence_info(clause)
    if sentence_info.get('compare_key') is None:
        return None

    probation = _extract_probation_info(clause)
    compare_key = sentence_info.get('compare_key')
    if probation and sentence_info.get('months') not in (-2, -1):
        compare_key = f"{compare_key}|probation:{probation['months']}"

    return {
        "person": person or '未识别',
        "charge": charge or '',
        "category": category,
        "category_label": '决定执行' if category == 'execution' else '单罪量刑',
        "months": sentence_info.get('months'),
        "display": _sentence_display_with_probation(sentence_info, clause),
        "sentence_type": sentence_info.get('sentence_type') or '未识别',
        "compare_key": compare_key,
        "probation_months": probation['months'] if probation else None,
        "text": _trim_term_clause(clause),
    }


def _split_person_sections(block: str):
    matches = list(re.finditer(
        r'(?:对被告人|被告人|原审被告人|上诉人[（(]原审被告人[）)])'
        r'([\u4e00-\u9fa5A-Za-z0-9·]{2,12}?)(?=死刑|无期徒刑|有期徒刑|拘役|管制|，|。|；|;|（|\(|以|犯|的|$)',
        block
    ))
    if not matches:
        return [(None, block)]

    sections = []
    for idx, match in enumerate(matches):
        start = 0 if idx == 0 else match.start()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(block)
        sections.append((match.group(1), block[start:end]))
    return sections


def _extract_structured_items_from_section(person: str | None, section_text: str):
    normalized_section = re.sub(
        r'(?=(?:以|犯|与其犯|与其所犯|所犯)[\u4e00-\u9fa5、]{1,30}?罪(?:，)?(?:判处|被判处|判处的))',
        '|||',
        section_text
    )
    normalized_section = re.sub(r'(?=决定执行)', '|||', normalized_section)
    clauses = [part.strip(' ，,；;。!\n\t') for part in re.split(r'\|\|\||[；;。]\s*', normalized_section) if part.strip()]
    items = []
    for clause in clauses:
        normalized_clause = _trim_term_clause(clause)
        if not normalized_clause:
            continue
        if any(keyword in normalized_clause for keyword in ('建议不核准', '不核准', '撤销', '发回重审')):
            continue
        if not _contains_term_keywords(normalized_clause):
            continue

        current_person = _extract_person_name(normalized_clause) or person
        current_charge = _extract_charge_from_text(normalized_clause)

        if normalized_clause.startswith('决定执行'):
            execution_item = _make_structured_term_item(current_person, '', 'execution', normalized_clause)
            if execution_item:
                items.append(execution_item)
            continue

        if current_charge:
            charge_item = _make_structured_term_item(current_person, current_charge, 'charge', normalized_clause)
            if charge_item:
                items.append(charge_item)
            continue

        # 兜底：仅当有明确被告人但未抽到罪名时，保留为未命名量刑项。
        fallback_item = _make_structured_term_item(current_person, '', 'charge', normalized_clause)
        if fallback_item:
            items.append(fallback_item)
    return items


def _dedupe_structured_items(items):
    deduped = {}
    for item in items:
        key = (
            item.get('person') or '',
            item.get('category') or '',
            item.get('charge') or '',
        )
        current = deduped.get(key)
        if current is None:
            deduped[key] = item
            continue

        current_score = 0
        item_score = 0
        if current.get('probation_months') is not None:
            current_score += 10
        if item.get('probation_months') is not None:
            item_score += 10
        if current.get('charge'):
            current_score += 5
        if item.get('charge'):
            item_score += 5
        if len(current.get('text') or '') < len(item.get('text') or ''):
            current_score += 1
        else:
            item_score += 1

        if item_score > current_score:
            deduped[key] = item

    result = list(deduped.values())
    result.sort(key=lambda item: (item.get('person') or '', item.get('category') or '', item.get('charge') or ''))
    return result


def _extract_term_items(text: str):
    normalized_text = _normalize_result_for_term_extraction(text)
    if not _contains_term_keywords(normalized_text):
        return []

    numbered_blocks = [block for block in re.split(r'(?=[一二三四五六七八九十]+、)', normalized_text) if block.strip()]
    items = []
    for block in numbered_blocks:
        normalized_block = _trim_term_clause(block)
        if not normalized_block or normalized_block.startswith('撤销'):
            continue
        for person, section_text in _split_person_sections(block):
            items.extend(_extract_structured_items_from_section(person, section_text))
    return _dedupe_structured_items(items)


def _compare_structured_term_item(actual_item, predicted_item):
    if not actual_item or not predicted_item:
        return {
            "actual": actual_item,
            "predicted": predicted_item,
            "score": 0.0,
            "month_gap": None,
            "slot_label": (actual_item or predicted_item or {}).get('category_label', '量刑项'),
        }

    actual_compare = {
        "months": actual_item.get('months'),
        "compare_key": actual_item.get('compare_key'),
        "display": actual_item.get('display'),
        "sentence_type": actual_item.get('sentence_type'),
    }
    predicted_compare = {
        "months": predicted_item.get('months'),
        "compare_key": predicted_item.get('compare_key'),
        "display": predicted_item.get('display'),
        "sentence_type": predicted_item.get('sentence_type'),
    }
    return {
        "actual": actual_item,
        "predicted": predicted_item,
        "score": _term_accuracy_score(actual_compare, predicted_compare),
        "month_gap": None if actual_item.get('months') is None or predicted_item.get('months') is None or actual_item.get('months') < 0 or predicted_item.get('months') < 0 else abs(predicted_item.get('months') - actual_item.get('months')),
        "slot_label": actual_item.get('category_label', '量刑项'),
    }


def _build_term_comparison(text_actual: str, text_predicted: str):
    actual_items = _extract_term_items(text_actual)
    predicted_items = _extract_term_items(text_predicted)

    actual_map = {
        (item.get('person') or '', item.get('category') or '', item.get('charge') or ''): item
        for item in actual_items
    }
    predicted_map = {
        (item.get('person') or '', item.get('category') or '', item.get('charge') or ''): item
        for item in predicted_items
    }

    ordered_keys = []
    for item in actual_items + predicted_items:
        key = (item.get('person') or '', item.get('category') or '', item.get('charge') or '')
        if key not in ordered_keys:
            ordered_keys.append(key)

    comparisons = [
        _compare_structured_term_item(actual_map.get(key), predicted_map.get(key))
        for key in ordered_keys
    ]
    valid_scores = [item['score'] for item in comparisons if item['score'] is not None]
    average_score = round(sum(valid_scores) / len(valid_scores), 1) if valid_scores else None
    return {
        "actual_events": actual_items,
        "predicted_events": predicted_items,
        "comparisons": comparisons,
        "average_score": average_score,
        "score_rule": '结构化量刑项比较：按“被告人 + 单罪量刑/决定执行 + 罪名”对齐；完全一致100，差1个月90，差3个月内75，差6个月内55，差12个月内30，其余0；真实为死缓但预测仅到死刑时按60分；缺失项按0分处理'
    }


def _build_prediction_detail(case: Case):
    actual_result = case.get_actual_result() or ''
    predicted_result = (case.predict_result or '').strip()
    if not actual_result or not predicted_result:
        return None

    actual_charges = _extract_charges(actual_result)
    predicted_charges = _extract_charges(predicted_result)
    term_comparison = _build_term_comparison(actual_result, predicted_result)
    actual_severity = _extract_punishment_severity_level(actual_result)
    predicted_severity = _extract_punishment_severity_level(predicted_result)

    return {
        "charge": {
            "actual": actual_charges,
            "predicted": predicted_charges,
            "matched": sorted(set(actual_charges) & set(predicted_charges)),
            "missing": sorted(set(actual_charges) - set(predicted_charges)),
            "extra": sorted(set(predicted_charges) - set(actual_charges))
        },
        "term": {
            "actual_months": None,
            "predicted_months": None,
            "actual_display": f"已解析 {len(term_comparison['actual_events'])} 个结构化量刑项",
            "predicted_display": f"已解析 {len(term_comparison['predicted_events'])} 个结构化量刑项",
            "month_gap": None,
            "score_rule": term_comparison['score_rule'],
            "actual_event_count": len(term_comparison['actual_events']),
            "predicted_event_count": len(term_comparison['predicted_events']),
            "comparison_rows": term_comparison['comparisons'],
            "average_score": term_comparison['average_score'],
        },
        "severity": {
            "actual_level": actual_severity,
            "predicted_level": predicted_severity,
            "actual_label": _severity_label(actual_severity),
            "predicted_label": _severity_label(predicted_severity),
            "level_gap": None if actual_severity is None or predicted_severity is None else abs(actual_severity - predicted_severity)
        }
    }


@predict_bp.route('/predict')
def predict():
    """判决预测页面 - 默认显示最新案件，可通过case_id指定案件"""
    
    # 与标注/统计页面保持一致：优先URL参数，再用session中的最近查看案件，最后回退到最新案件
    case = None
    
    
    case_id = request.args.get('case_id', type=int)
    if case_id:
        case = Case.query.get(case_id)

    # 2. 其次从session获取上次查看的
    if not case:
        last_case_id = session.get('last_viewed_case')
        if last_case_id:
            case = Case.query.get(last_case_id)

    # 3. 最后获取最新案件
    if not case:
        case = Case.query.order_by(Case.id.desc()).first()

    if case:
        session['last_viewed_case'] = case.id
    
   
    cases = []
    if case:
        cases = [case]  
    
    
    return render_template(
        'predict.html',
        cases=cases,
        predict_method_options=PREDICT_METHOD_OPTIONS,
        predict_method_labels=PREDICT_METHOD_LABELS,
        prediction_detail=_build_prediction_detail(case) if case else None,
    )


@predict_bp.route('/predict/retry', methods=['POST'])
def retry_prediction():
    """重新触发指定案件的判决预测，并覆盖旧结果。"""
    case_id = request.form.get('case_id', type=int)
    if not case_id:
        flash('未找到要重新预测的案件。', 'error')
        return redirect(url_for('predict.predict'))

    case = Case.query.get(case_id)
    if not case:
        flash('案件不存在，无法重新预测。', 'error')
        return redirect(url_for('predict.predict'))

    content = (case.content or '').strip()
    if not content:
        flash('该案件没有可用于预测的文书内容。', 'error')
        return redirect(url_for('predict.predict', case_id=case_id))

    try:
        from .api import predict_judgement_with_api

        selected_method = (request.form.get('predict_method') or '').strip() or case.predict_method or 'official_step'
        if selected_method not in PREDICT_METHOD_LABELS:
            flash('选择的预测模型不存在。', 'error')
            return redirect(url_for('predict.predict', case_id=case_id))

        prediction_result = predict_judgement_with_api(
            content=content,
            case_type=case.sort or '其他',
            prompt_template=case.predict_prompt_template or None,
            method=selected_method
        )

        # 明确覆盖旧预测，避免页面继续展示历史结果。
        case.predict_result = prediction_result.get('prediction', '')
        case.predict_method = prediction_result.get('method', selected_method)
        case.predict_prompt_template = prediction_result.get(
            'used_prompt_template',
            case.predict_prompt_template or ''
        )
        db.session.commit()

        if prediction_result.get('success'):
            method_label = PREDICT_METHOD_LABELS.get(case.predict_method, case.predict_method)
            flash(f'已使用 {method_label} 重新预测，页面展示的是最新结果。', 'success')
        else:
            method_label = PREDICT_METHOD_LABELS.get(selected_method, selected_method)
            flash(f'已尝试切换到 {method_label} 并重新预测，但本次调用未成功。', 'warning')
    except Exception as exc:
        db.session.rollback()
        flash(f'重新预测失败：{exc}', 'error')

    return redirect(url_for('predict.predict', case_id=case_id))


# @predict_bp.route('/casesubmit', methods=['POST'])
# def case_submit():
#     return render_template('predict.html')
