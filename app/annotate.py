from flask import Blueprint, render_template, request, session
from .database import Case, db

import json

annotate_bp = Blueprint('annotate', __name__)



@annotate_bp.route('/annotate')
def annotate():
    """标注页面"""
    case = None
    
    # 1.优先从URL参数获取
    case_id = request.args.get('case_id', type=int)
    if case_id:
        case = Case.query.get(case_id)
    
    # 2.其次从session获取上次查看的
    if not case:
        last_case_id = session.get('last_viewed_case')
        if last_case_id:
            case = Case.query.get(last_case_id)
    
    # 3.最后获取最近的
    if not case:
        case = Case.query.order_by(Case.time.desc()).first()
    
    # 4. 最终找到的case
    if case:
        session['last_viewed_case'] = case.id
        db.session.commit()
        
        
        keywords_list = []
        if case.keywords:
            try:
                keywords_list = json.loads(case.keywords)
            except:
                keywords_list = []
        
        highlighted_summary = highlight_keywords(
            case.summary if case.summary else "",
            keywords_list  
        )

        graph_payload = case.get_graph_payload()
        graph = graph_payload.get("graph", {"nodes": [], "links": []})
        
        return render_template('annotate.html', 
                             case=case, 
                             highlighted_summary=highlighted_summary,
                             laws_list=case.get_law_list(),
                             persons_list=case.get_persons_list(),
                             graph_preview=graph,
                             mode='view')
    
    return render_template('annotate.html', case=None, mode='prompt')



def highlight_keywords(text, keywords):
    """高亮关键词"""
    if not text or not keywords:
        return text
    
    highlighted = text
    unique_keywords = list(set([str(k).strip() for k in keywords]))
    sorted_keywords = sorted(unique_keywords, key=len, reverse=True)
    
    for keyword in sorted_keywords:
        if len(keyword) > 1 and keyword in highlighted:
            highlighted_word = f'<span style="color: blue; font-weight: bold;">{keyword}</span>'
            highlighted = highlighted.replace(keyword, highlighted_word)
    
    return highlighted