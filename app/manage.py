from flask import Blueprint, render_template,redirect, request
from .database import Case,db

manage_bp = Blueprint('manage', __name__)

@manage_bp.route('/manage')
def manage():
    cases = Case.query.all()
    return render_template('manage.html', cases=cases)


@manage_bp.route('/delete/<int:case_id>', methods=['POST'])
def delete_case(case_id):
    """删除案例 - POST方法"""
    try:
        case = Case.query.get(case_id)
        if case:
            db.session.delete(case)
            db.session.commit()
    except Exception as e:
        db.session.rollback()
    
    return redirect('/manage')