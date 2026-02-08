from flask import Blueprint, render_template, redirect, request
from sqlalchemy import or_
from .database import Case, db

manage_bp = Blueprint('manage', __name__)

@manage_bp.route('/manage')
def manage():
    # 1. 获取搜索参数
    keyword = request.args.get('keyword', '').strip()
    sort_type = request.args.get('sort', '').strip()
    
    # 2. 基础查询
    query = Case.query
    
    # 3. 应用搜索条件
    if keyword:
        query = query.filter(
            or_(
                Case.name.contains(keyword),
                Case.cause.contains(keyword),
                Case.content.contains(keyword),
                Case.summary.contains(keyword)
            )
        )
    
    if sort_type:
        query = query.filter(Case.sort == sort_type)
    
    # 4. 排序（保持原有）
    cases = query.all()
    
    # 5. 获取所有分类用于下拉框
    all_sorts = db.session.query(Case.sort).distinct().all()
    all_sorts = [s[0] for s in all_sorts if s[0]]
    
    # 6. 统计信息
    total_count = Case.query.count()
    filtered_count = len(cases)
    
    return render_template('manage.html', 
                         cases=cases,
                         keyword=keyword,
                         selected_sort=sort_type,
                         all_sorts=all_sorts,
                         total_count=total_count,
                         filtered_count=filtered_count)

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