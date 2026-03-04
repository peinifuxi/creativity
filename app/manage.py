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
    filtered_count = query.count()
    
    
    # 5. 渲染
    return render_template('manage.html', 
                         cases=cases,
                         pagination=pagination,
                         keyword=keyword,
                         selected_sort=sort_type,
                         filtered_count=filtered_count)

@manage_bp.route('/delete/<int:case_id>', methods=['POST'])
def delete_case(case_id):
    """删除指定案件"""
    try:
        case = Case.query.get_or_404(case_id)
        case_name = case.name
        
        db.session.delete(case)
        db.session.commit()
        
        print(f"案件删除成功: {case_name} (ID: {case_id})")
        return redirect('/manage')
        
    except Exception as e:
        db.session.rollback()
        print(f"删除失败: {e}")
        return f"删除失败: {str(e)}", 500

# ========== 函数 ==========

def get_search_query(keyword=None, sort_type=None):
    """构建搜索查询"""
    query = Case.query
    
    if keyword:
        query = query.filter(Case.keywords.contains(keyword))
    
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

def get_all_sorts():
    """获取所有分类（可加缓存）"""
    sorts = db.session.query(Case.sort).distinct().all()
    return [s[0] for s in sorts if s[0]]

##批量更改数据
@manage_bp.route('/fix')
def fix_sorts():
    """一次性修复分类数据"""
    try:
        # 更新所有数据
        Case.query.filter_by(sort='民事').update({'sort': '民事案件'})
        Case.query.filter_by(sort='刑事').update({'sort': '刑事案件'})
        Case.query.filter_by(sort='行政').update({'sort': '行政案件'})
        
        db.session.commit()
        return "分类数据修复成功！"
    except Exception as e:
        db.session.rollback()
        return f"修复失败：{str(e)}"