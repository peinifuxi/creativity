from flask import Blueprint, render_template, redirect, request
from .database import Case, db
from datetime import datetime
import json
import traceback

index_bp = Blueprint('index', __name__)

@index_bp.route('/')
def index():
    return render_template('index.html')


# @index_bp.route('/casesubmit', methods=['POST'])
# def case_submit():
#     """处理案件提交 - 提交后跳转到标注页面显示该案件"""
#     try:
#         # 获取内容
#         content = request.form.get('content')
#         result = request.form.get('result', '')
        
#         if not content:
#             return "内容不能为空", 400
        
#         # 先保存案件，标题先用空
#         new_case = Case(name="", sort='其他', content=content, result=result)
#         db.session.add(new_case)
#         db.session.commit()
        
#         # 调用API分析
#         if content and len(content.strip()) > 50:
#             try:
#                 from .api import analyze_case_with_api
#                 analysis_result = analyze_case_with_api(content)  
                
#                 if analysis_result:
#                     # 更新案件信息
#                     new_case.name = analysis_result.get('title', '')[:50]
#                     new_case.sort = analysis_result.get('sort', '其他')
#                     new_case.summary = analysis_result.get('summary', '')
#                     new_case.keywords = json.dumps(analysis_result.get('keywords', []), ensure_ascii=False)
                    
#                     db.session.commit()
#             except Exception as e:
#                 print(f"API分析失败: {e}")
                
        
#         return redirect(f'/annotate?case_id={new_case.id}')
        
    # except Exception as e:
    #     db.session.rollback()
    #     return f"提交失败: {str(e)}", 500