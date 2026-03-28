from flask import Blueprint, render_template, redirect, request
from .database import Case, db
from datetime import datetime
import json
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
        result = request.form.get('result', '')
        
        if not content:
            return "内容不能为空", 400
        
        # 先保存案件，标题先用空
        new_case = Case(name="", sort='其他', content=content, result=result)
        db.session.add(new_case)
        db.session.commit()
        
        # 调用API分析
        if content and len(content.strip()) > 50:
            try:
                from .api import analyze_case_with_api, extract_entities_relations
                analysis_result = analyze_case_with_api(content)  
                
                if analysis_result:
                    # 更新案件信息 - 包含所有新字段
                    new_case.name = analysis_result.get('title', '')[:50]
                    new_case.sort = analysis_result.get('sort', '其他')
                    new_case.summary = analysis_result.get('summary', '')
                    new_case.keywords = json.dumps(analysis_result.get('keywords', []), ensure_ascii=False)
                    
                    # 新增字段
                    new_case.court = analysis_result.get('court', '')[:50]
                    
                    # laws是列表，转成JSON字符串
                    laws = analysis_result.get('laws', [])
                    new_case.law = json.dumps(laws, ensure_ascii=False)
                    
                    # persons是列表，转成JSON字符串
                    persons = analysis_result.get('persons', [])
                    new_case.person = json.dumps(persons, ensure_ascii=False)
                    
                    # incident和location
                    new_case.incident = analysis_result.get('dispute', '')
                    new_case.location = analysis_result.get('location', '')[:100]
                    
                    
                    # 实体关系抽取 -> 生成人物关系图谱（存入 predict_result 字段）
                    # 构造抽取先验线索
                    hints = {
                        "persons": persons,
                        "incident": analysis_result.get('dispute', ''),
                        "location": analysis_result.get('location', ''),
                        "time": ""  # 可后续从正文规则提取
                    }
                    extract_result = extract_entities_relations(content, hints=hints)
                    if extract_result:
                        graph = extract_result.get('graph', {"nodes": [], "links": []})
                        # 若抽取返回了更规范的 persons，则同步覆盖人物字段
                        persons_from_extract = extract_result.get('persons')
                        if isinstance(persons_from_extract, list) and persons_from_extract:
                            new_case.person = json.dumps(persons_from_extract, ensure_ascii=False)
                        new_case.predict_result = json.dumps({"graph": graph, "raw": extract_result.get("raw", {})}, ensure_ascii=False)
                    
                    db.session.commit()
            except Exception as e:
                print(f"API分析失败: {e}")
                traceback.print_exc()
                
        
        return redirect(f'/annotate?case_id={new_case.id}')
        
    except Exception as e:
        db.session.rollback()
        return f"提交失败: {str(e)}", 500