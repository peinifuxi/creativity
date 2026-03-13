from flask import Blueprint, render_template, redirect, request
from sqlalchemy import or_
from .database import Case, db


manage_bp = Blueprint('manage', __name__)

@manage_bp.route('/manage')
def manage():
    # 1. 获取参数
    page = request.args.get('page', 1, type=int)
    per_page = 5
    keyword = request.args.get('keyword', '').strip()
    sort_type = request.args.get('sort', '').strip()
    
    # 2. 构建查询
    query = get_search_query(keyword, sort_type)
    
    # 3. 获取分页数据
    pagination = get_paginated_cases(query, page, per_page)
    cases = pagination.items
    
    # 4. 获取统计数据
    
    total_count = Case.query.count()
        
        
    
    filtered_count = query.count()
    
    # 5. 渲染
    return render_template('manage.html', 
                         cases=cases,
                         pagination=pagination,
                         keyword=keyword,
                         total_count=total_count,
                         filtered_count=filtered_count)

@manage_bp.route('/delete/<int:case_id>', methods=['POST'])
def delete_case(case_id):
    """删除指定案件"""
    try:
        case = Case.query.get_or_404(case_id)
        case_name = case.name
        
        db.session.delete(case)
        db.session.commit()
        
    
        
       
        return redirect('/manage')
        
    except Exception as e:
        db.session.rollback()
        
        return f"删除失败: {str(e)}", 500


# ========== 函数 ==========

def get_search_query(keyword=None, sort_type=None):
    """构建搜索查询"""
    query = Case.query
    
    if keyword:
        query = query.filter(
            or_(
                Case.content.like(f'%{keyword}%'),   # 内容中搜索
                Case.keywords.like(f'%{keyword}%')     # 关键词中搜索
            )
        )
    
    if sort_type:
        query = query.filter(Case.sort == sort_type)
    
    return query

def get_paginated_cases(query, page=1, per_page=5):
    """获取分页数据"""
    return query.order_by(Case.id.desc()).paginate(
        page=page, 
        per_page=per_page,
        error_out=False
    )