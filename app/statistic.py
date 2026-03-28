from flask import Blueprint, render_template, session, request, redirect
from .database import db, Case
import json

statistic_bp = Blueprint('statistic', __name__)

@statistic_bp.route('/statistic')
def statistic():
    """统计页面 - 与标注页面显示同一个案件"""
    
    # 与标注页面完全相同的逻辑
    case = None
    
    
    last_case_id = session.get('last_viewed_case')
    if last_case_id:
        case = Case.query.get(last_case_id)
    
   
    if not case:
        case = Case.query.order_by(Case.time.desc()).first()
    
    # 解析人物关系图谱（来自 predict_result.graph）
    graph = {"nodes": [], "links": []}
    current_case_id = None
    raw = {}
    if case and case.predict_result:
        current_case_id = case.id
        try:
            pr = json.loads(case.predict_result)
            graph = pr.get("graph", graph)
            raw = pr.get("raw", {})
        except:
            graph = {"nodes": [], "links": []}
    
    cases = []
    if case:
        cases = [case]  
    
    
    return render_template('statistic.html',
                           cases=cases,
                           graph_json=json.dumps(graph, ensure_ascii=False),
                           current_case_id=current_case_id,
                           raw_json=json.dumps(raw, ensure_ascii=False),
                           doc_text=case.content if case else "")


@statistic_bp.route('/statistic/rebuild', methods=['POST', 'GET'])
def statistic_rebuild():
    """为指定或当前案件重跑实体关系抽取并保存，然后回到统计页"""
    case_id = request.values.get('case_id', type=int)
    case = None
    if case_id:
        case = Case.query.get(case_id)
    if not case:
        last_case_id = session.get('last_viewed_case')
        if last_case_id:
            case = Case.query.get(last_case_id)
    if not case:
        case = Case.query.order_by(Case.time.desc()).first()
    if case and case.content:
        try:
            from .api import extract_entities_relations
            # 提供先验线索以提升抽取质量
            persons = []
            try:
                if case.person:
                    persons = json.loads(case.person)
            except:
                persons = []
            hints = {
                "persons": persons if isinstance(persons, list) else [],
                "incident": case.incident or "",
                "location": case.location or "",
                "time": ""  # 可扩展：从正文或 time 字段提取
            }
            extract_result = extract_entities_relations(case.content, hints=hints)
            if extract_result:
                graph = extract_result.get('graph', {"nodes": [], "links": []})
                persons_from_extract = extract_result.get('persons')
                if isinstance(persons_from_extract, list) and persons_from_extract:
                    case.person = json.dumps(persons_from_extract, ensure_ascii=False)
                case.predict_result = json.dumps({"graph": graph, "raw": extract_result.get("raw", {})}, ensure_ascii=False)
                db.session.commit()
        except Exception:
            db.session.rollback()
    return redirect('/statistic')


@statistic_bp.route('/statistic/save_graph', methods=['POST'])
def statistic_save_graph():
    """保存人工纠偏后的图谱"""
    case_id = request.form.get('case_id', type=int)
    graph_json = request.form.get('graph_json', '')
    case = None
    if case_id:
        case = Case.query.get(case_id)
    if not case:
        last_case_id = session.get('last_viewed_case')
        if last_case_id:
            case = Case.query.get(last_case_id)
    if not case:
        case = Case.query.order_by(Case.time.desc()).first()
    if not case:
        return redirect('/statistic')
    try:
        new_graph = json.loads(graph_json) if graph_json else {"nodes": [], "links": []}
    except Exception:
        new_graph = {"nodes": [], "links": []}
    try:
        # 保留原始 raw，若存在
        raw = {}
        try:
            if case.predict_result:
                pr = json.loads(case.predict_result)
                raw = pr.get('raw', {})
        except:
            raw = {}
        case.predict_result = json.dumps({"graph": new_graph, "raw": raw}, ensure_ascii=False)
        db.session.commit()
    except Exception:
        db.session.rollback()
    return redirect('/statistic')



# @statistic_bp.route('/casesubmit', methods=['POST'])
# def case_submit():
#     return render_template('statistic.html')