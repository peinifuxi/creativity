from flask import Blueprint, render_template, session
from .database import db, Case

statistic_bp = Blueprint('statistic', __name__)

@statistic_bp.route('/statistic')
def statistic():
    """统计页面 - 与标注页面显示同一个案件"""
    
    # 与标注页面完全相同的逻辑
    case = None
    
    # 1. 从session获取案件ID（与标注页面用同一个session键）
    last_case_id = session.get('last_viewed_case')
    if last_case_id:
        case = Case.query.get(last_case_id)
    
    # 2. 如果没有session记录，获取最近一个案件
    if not case:
        case = Case.query.order_by(Case.time.desc()).first()
    
    # 3. 将案件放入列表（保持模板兼容）
    cases = []
    if case:
        cases = [case]  # 只包含当前查看的案件
    
    # 4. 传递给模板
    return render_template('statistic.html', cases=cases)