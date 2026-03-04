from flask import Blueprint, render_template, redirect, request
from .database import Case, db
from datetime import datetime
import json
from .nlp import analyzer  # 导入NLP分析器
import traceback

index_bp = Blueprint('index', __name__)

@index_bp.route('/')
def index():
    return render_template('index.html')


@index_bp.route('/casesubmit', methods=['POST'])
def case_submit():
    """处理案件提交 - 提交后跳转到标注页面显示该案件"""
    try:
        # 获取内容
        content = request.form.get('content')
        
        if not content:
            return "内容不能为空", 400
        
        # 提取标题
        first_line = content.strip().split('\n')[0]
        if '案  由' in first_line:
            title = first_line.split('案  由')[0].strip()
            # 用"案  由"分割内容，取后面的部分作为实际内容
            content_parts = content.split('案  由')
            if len(content_parts) > 1:
                content_without_title = content_parts[1].strip()
            else:
                content_without_title = content
        else:
            title = first_line[:100] + "..." if len(first_line) > 100 else first_line
            # 去掉第一行
            content_lines = content.strip().split('\n')
            content_without_title = '\n'.join(content_lines[1:]).strip() if len(content_lines) > 1 else content
        
        # 确定案件类型
        if '刑事' in title:
            sort = '刑事案件'
        elif '民事' in title:
            sort = '民事案件'
        elif '行政' in title:
            sort = '行政案件'
        else:
            sort = '其他'
        
        # 保存案件
        new_case = Case(name=title, sort=sort, content=content_without_title)
        db.session.add(new_case)
        db.session.commit()
        
        # NLP分析
        if content_without_title and len(content_without_title.strip()) > 50:
            try:
                analysis_result = analyzer.analyze(content_without_title, {'sort': sort})
                if analysis_result:
                    new_case.summary = analysis_result['summary']
                    new_case.keywords = json.dumps(
                        [kw['word'] for kw in analysis_result['keywords']['all'][:20]], 
                        ensure_ascii=False
                    )
                    new_case.is_nlp_analyzed = True
                    new_case.analyzed_at = datetime.now()
                    db.session.commit()
            except:
                db.session.rollback()
                new_case = Case.query.get(new_case.id)
        
        return redirect(f'/annotate?case_id={new_case.id}')
        
    except Exception as e:
        db.session.rollback()
        return f"提交失败: {str(e)}", 500