from flask import Blueprint, render_template, session, request
from .database import db, Case

predict_bp = Blueprint('predict', __name__)

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
    
    
    return render_template('predict.html', cases=cases)


# @predict_bp.route('/casesubmit', methods=['POST'])
# def case_submit():
#     return render_template('predict.html')
