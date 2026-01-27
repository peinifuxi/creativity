from flask import Blueprint, render_template, redirect, request
from .database import Case, db
from datetime import datetime
import json
from .nlp import analyzer  # 导入NLP分析器

index_bp = Blueprint('index', __name__)

@index_bp.route('/')
def index():
    return render_template('index.html')

@index_bp.route('/submit')
def submit_form():
    """显示提交表单"""
    return render_template('submit.html')

@index_bp.route('/casesubmit', methods=['POST'])
def case_submit():
    """处理案件提交 - 提交后跳转到标注页面显示该案件"""
    try:
        name = request.form.get('name')
        sort = request.form.get('sort')
        cause = request.form.get('cause')
        result = request.form.get('result')
        content = request.form.get('content')
        
        # 1. 先保存基本案件信息
        new_case = Case(name=name, sort=sort, cause=cause, result=result, content=content)
        db.session.add(new_case)
        db.session.commit()  # 先提交获取ID
        
        # 2. 进行NLP分析（如果内容足够长）
        if content and len(content.strip()) > 50:
            # 准备案件信息用于增强关键词
            case_info = {
                'sort': sort,
                'cause': cause,
                'result': result
            }
            
            # 调用NLP分析
            analysis_result = analyzer.analyze(content, case_info)
            
            if analysis_result:
                # 更新案件的分析结果
                new_case.summary = analysis_result['summary']
                # 只保存关键词列表，不保存分类结构（简化）
                new_case.keywords = json.dumps(
                    [kw['word'] for kw in analysis_result['keywords']['all'][:20]], 
                    ensure_ascii=False
                )
                new_case.is_nlp_analyzed = True
                new_case.analyzed_at = datetime.now()
                
                db.session.commit()
        
        # 3. 跳转到标注页面
        return redirect(f'/annotate?case_id={new_case.id}')
        
    except Exception as e:
        # 如果出错，至少保证案件保存成功
        db.session.rollback()
        # 重新保存基本案件信息
        new_case = Case(name=name, sort=sort, cause=cause, result=result, content=content)
        db.session.add(new_case)
        db.session.commit()
        return redirect(f'/annotate?case_id={new_case.id}')