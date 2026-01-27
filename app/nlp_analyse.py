from flask import Blueprint, request, jsonify, current_app
from .database import db, Case, datetime
from .nlp import analyzer

import json

nlp_bp = Blueprint('nlp', __name__)

@nlp_bp.route('/api/analyze/case/<int:case_id>', methods=['POST'])
def analyze_case(case_id):
    """分析指定案件"""
    try:
        case = Case.query.get_or_404(case_id)
        
        # 检查是否已分析过
        if case.is_nlp_analyzed:
            return jsonify({
                'success': True,
                'message': '已分析过',
                'data': case.get_analysis_info()
            })
        
        # 准备案件信息
        case_info = {
            'sort': case.sort,
            'cause': case.cause,
            'result': case.result
        }
        
        # 调用NLP分析
        analysis_result = analyzer.analyze(case.content, case_info)
        
        if analysis_result:
            # 更新数据库
            case.summary = analysis_result['summary']
            case.keywords = json.dumps(analysis_result['keywords']['all'], ensure_ascii=False)
            case.is_nlp_analyzed = True
            case.analyzed_at = datetime.now()
            
            db.session.commit()
            
            return jsonify({
                'success': True,
                'message': '分析完成',
                'data': {
                    'summary': analysis_result['summary'],
                    'keywords': analysis_result['keywords'],
                    'stats': analysis_result['stats']
                }
            })
        else:
            return jsonify({
                'success': False,
                'message': '分析失败：内容太短'
            }), 400
            
    except Exception as e:
        current_app.logger.error(f'分析失败: {str(e)}')
        return jsonify({
            'success': False,
            'message': f'分析失败: {str(e)}'
        }), 500

@nlp_bp.route('/api/analyze/text', methods=['POST'])
def analyze_text():
    """直接分析文本（不保存到数据库）"""
    try:
        data = request.get_json()
        text = data.get('text', '')
        
        if not text:
            return jsonify({'success': False, 'message': '文本为空'}), 400
        
        # 可选：从请求中获取案件信息
        case_info = data.get('case_info', {})
        
        # 分析
        result = analyzer.analyze(text, case_info)
        
        if result:
            return jsonify({
                'success': True,
                'data': result
            })
        else:
            return jsonify({
                'success': False,
                'message': '分析失败'
            }), 400
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'请求失败: {str(e)}'
        }), 500

@nlp_bp.route('/api/case/<int:case_id>/analysis', methods=['GET'])
def get_case_analysis(case_id):
    """获取案件分析结果"""
    try:
        case = Case.query.get_or_404(case_id)
        
        if not case.is_nlp_analyzed:
            return jsonify({
                'success': False,
                'message': '尚未分析',
                'code': 'NOT_ANALYZED'
            }), 404
        
        return jsonify({
            'success': True,
            'data': case.get_analysis_info()
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'获取失败: {str(e)}'
        }), 500