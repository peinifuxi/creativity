from flask import Blueprint, render_template, session, request, redirect
from .database import db, Case
import json
from datetime import datetime

statistic_bp = Blueprint('statistic', __name__)


def _resolve_current_case():
    """定位当前案件：优先 URL 参数，再取 session，最后回退到最新案件。"""
    case = None
    case_id = request.values.get('case_id', type=int)
    if case_id:
        case = Case.query.get(case_id)

    if not case:
        last_case_id = session.get('last_viewed_case')
        if last_case_id:
            case = Case.query.get(last_case_id)

    if not case:
        case = Case.query.order_by(Case.id.desc()).first()

    if case:
        session['last_viewed_case'] = case.id
    return case

@statistic_bp.route('/statistic')
def statistic():
    """统计页面 - 与标注页面显示同一个案件"""
    case = _resolve_current_case()

    graph_payload = {"graph": {"nodes": [], "links": []}, "raw": {}}
    current_case_id = None
    if case:
        current_case_id = case.id
        graph_payload = case.get_graph_payload()

    cases = []
    if case:
        cases = [case]  

    return render_template(
        'statistic.html',
        cases=cases,
        graph_json=json.dumps(graph_payload.get("graph", {"nodes": [], "links": []}), ensure_ascii=False),
        current_case_id=current_case_id,
        raw_json=json.dumps(graph_payload.get("raw", {}), ensure_ascii=False),
        doc_text=case.content if case else ""
    )


@statistic_bp.route('/statistic/rebuild', methods=['POST', 'GET'])
def statistic_rebuild():
    """为当前案件重跑知识图谱抽取并保存。"""
    case = _resolve_current_case()
    if case and case.content:
        try:
            from .api import extract_entities_relations

            hints = {
                "persons": case.get_persons_list(),
                "incident": case.incident or "",
                "location": case.location or "",
                "time": ""
            }
            extract_result = extract_entities_relations(case.content, hints=hints)
            if extract_result:
                graph = extract_result.get('graph', {"nodes": [], "links": []})
                persons_from_extract = extract_result.get('persons')
                if isinstance(persons_from_extract, list) and persons_from_extract:
                    case.person = json.dumps(persons_from_extract, ensure_ascii=False)
                case.graph_result = json.dumps(
                    {
                        "graph": graph,
                        "raw": extract_result.get("raw", {}),
                        "meta": extract_result.get("meta", {})
                    },
                    ensure_ascii=False
                )
                db.session.commit()
        except Exception:
            db.session.rollback()
    return redirect(f'/statistic?case_id={case.id}' if case else '/statistic')


@statistic_bp.route('/statistic/save_graph', methods=['POST'])
def statistic_save_graph():
    """保存人工纠偏后的图谱。"""
    case = _resolve_current_case()
    if not case:
        return redirect('/statistic')

    graph_json = request.form.get('graph_json', '')
    try:
        new_graph = json.loads(graph_json) if graph_json else {"nodes": [], "links": []}
    except Exception:
        new_graph = {"nodes": [], "links": []}

    try:
        payload = case.get_graph_payload()
        raw = payload.get("raw", {})
        meta = payload.get("meta", {})
        meta["updated_at"] = datetime.now().isoformat(timespec="seconds")
        meta["source"] = "manual_edit"
        case.graph_result = json.dumps({"graph": new_graph, "raw": raw, "meta": meta}, ensure_ascii=False)
        db.session.commit()
    except Exception:
        db.session.rollback()
    return redirect(f'/statistic?case_id={case.id}')



# @statistic_bp.route('/casesubmit', methods=['POST'])
# def case_submit():
#     return render_template('statistic.html')