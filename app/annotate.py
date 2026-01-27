from flask import Blueprint, render_template, request,session
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
        # 增加浏览量
        case.browses += 1
        db.session.commit()
        return render_template('annotate.html', case=case, mode='view')
    
    return render_template('annotate.html', case=None, mode='prompt')