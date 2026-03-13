from flask import Blueprint, render_template, session
from .database import db, Case

predict_bp = Blueprint('predict', __name__)

@predict_bp.route('/predict')
def predict():
    """判决预测页面 - 与标注页面显示同一个案件"""
    
    # 与标注页面完全相同的逻辑
    case = None
    
    
    last_case_id = session.get('last_viewed_case')
    if last_case_id:
        case = Case.query.get(last_case_id)
    
   
    if not case:
        case = Case.query.order_by(Case.time.desc()).first()
    
   
    cases = []
    if case:
        cases = [case]  
    
    
    return render_template('predict.html', cases=cases)


# @predict_bp.route('/casesubmit', methods=['POST'])
# def case_submit():
#     return render_template('predict.html')
