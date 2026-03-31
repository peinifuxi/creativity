from flask import Blueprint, render_template, redirect, request
from .database import Case, db
from datetime import datetime
import json
import traceback
from sqlalchemy.exc import IntegrityError
from settings import settings

index_bp = Blueprint('index', __name__)

@index_bp.route('/')
def index():
    return render_template('index.html')


def _build_initial_case_name(content: str) -> str:
    """生成一个可落库的初始案件名，避免unique约束冲突。"""
    first_line = (content or '').strip().split('\n')[0].strip()
    if not first_line:
        first_line = '未命名案件'

    base_name = first_line[:35]
    suffix = datetime.now().strftime('%Y%m%d%H%M%S')
    return f"{base_name}_{suffix}"[:50]


def _make_unique_case_name(candidate_name: str, case_id: int = None) -> str:
    """确保案件名唯一，避免unique约束报错。"""
    candidate_name = (candidate_name or '').strip()[:50]
    if not candidate_name:
        candidate_name = f"未命名案件_{datetime.now().strftime('%Y%m%d%H%M%S')}"

    existing = Case.query.filter(Case.name == candidate_name)
    if case_id:
        existing = existing.filter(Case.id != case_id)
    if existing.first() is None:
        return candidate_name

    base = candidate_name[:40]
    index = 2
    while True:
        new_name = f"{base}_{index}"[:50]
        duplicate = Case.query.filter(Case.name == new_name)
        if case_id:
            duplicate = duplicate.filter(Case.id != case_id)
        if duplicate.first() is None:
            return new_name
        index += 1


@index_bp.route('/casesubmit', methods=['POST'])
def case_submit():
    """提交文书后写入数据库，并触发分析与判决预测。"""
    try:
        content = (request.form.get('content') or '').strip()
        actual_result = (request.form.get('result') or '').strip()
        prompt_template = (request.form.get('predict_prompt_template') or '').strip()
        predict_method = (request.form.get('predict_method') or '').strip() or 'official_step'

        if not content:
            return "内容不能为空", 400

        new_case = Case(
            name=_make_unique_case_name(_build_initial_case_name(content)),
            sort='其他',
            content=content,
            result=actual_result,
            actual_result=actual_result,
            predict_method=predict_method
        )
        db.session.add(new_case)
        db.session.commit()

        from .api import analyze_case_with_api, predict_judgement_with_api

        if len(content) > 50 and settings.DEEPSEEK_API_KEY:
            try:
                analysis_result = analyze_case_with_api(content)
                if analysis_result:
                    analyzed_name = (analysis_result.get('title') or new_case.name)[:50]
                    new_case.name = _make_unique_case_name(analyzed_name, case_id=new_case.id)
                    new_case.sort = analysis_result.get('sort', new_case.sort)
                    new_case.summary = analysis_result.get('summary', '')
                    new_case.keywords = json.dumps(analysis_result.get('keywords', []), ensure_ascii=False)
                    db.session.flush()
            except Exception as analyze_error:
                db.session.rollback()
                new_case = Case.query.get(new_case.id)
                print(f"案件分析失败: {analyze_error}")

        try:
            prediction_result = predict_judgement_with_api(
                content=content,
                case_type=new_case.sort,
                prompt_template=prompt_template if prompt_template else None,
                method=predict_method
            )
            new_case.predict_result = prediction_result.get('prediction', '')
            new_case.predict_method = prediction_result.get('method', predict_method)
            new_case.predict_prompt_template = prediction_result.get('used_prompt_template', prompt_template or '')
        except Exception as predict_error:
            print(f"判决预测失败: {predict_error}")

        db.session.commit()
        return redirect(f'/annotate?case_id={new_case.id}')

    except IntegrityError as integrity_error:
        db.session.rollback()
        return f"提交失败: 数据重复或约束冲突（{str(integrity_error.orig)}）", 400

    except Exception as e:
        db.session.rollback()
        print(traceback.format_exc())
        return f"提交失败: {str(e)}", 500