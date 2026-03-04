from flask import Blueprint, render_template, request, session
from .database import Case, db

annotate_bp = Blueprint('annotate', __name__)



@annotate_bp.route('/annotate')
def annotate():
    """标注页面"""
    case = None
    
    # 优先从URL参数获取
    case_id = request.args.get('case_id', type=int)
    if case_id:
        case = Case.query.get(case_id)
    
    # 其次从session获取上次查看的
    if not case:
        last_case_id = session.get('last_viewed_case')
        if last_case_id:
            case = Case.query.get(last_case_id)
    
    # 最后获取最近的
    if not case:
        case = Case.query.order_by(Case.time.desc()).first()
    
    # 显示案件或提示
    if case:
        # 记录当前查看的案件到session
        session['last_viewed_case'] = case.id
        
        case.browses += 1
        db.session.commit()
        
        # 处理摘要高亮
        highlighted_summary = highlight_keywords(
            case.summary if case.summary else "",
            case.get_keywords_list()
        )
        
        return render_template('annotate.html', 
                             case=case, 
                             highlighted_summary=highlighted_summary,
                             mode='view')
    
    return render_template('annotate.html', case=None, mode='prompt')


def highlight_keywords(text, keywords):
    """高亮关键词"""
    if not text or not keywords:
        return text
    
    highlighted = text
    # 去重并排序，先处理长词避免嵌套问题
    unique_keywords = list(set([str(k).strip() for k in keywords]))
    sorted_keywords = sorted(unique_keywords, key=len, reverse=True)
    
    for keyword in sorted_keywords:
        if len(keyword) > 1 and keyword in highlighted:
            highlighted_word = f'<span style="color: blue; font-weight: bold;">{keyword}</span>'
            highlighted = highlighted.replace(keyword, highlighted_word)
    
    return highlighted