from flask import Blueprint, render_template, request, session
from .database import Case, db
import json

annotate_bp = Blueprint('annotate', __name__)

@annotate_bp.route('/annotate')
def annotate():
    """标注页面"""
    case = None
    
    # 1.优先从URL参数获取
    case_id = request.args.get('case_id', type=int)
    if case_id:
        case = Case.query.get(case_id)
    
    # 2.其次从session获取上次查看的
    if not case:
        last_case_id = session.get('last_viewed_case')
        if last_case_id:
            case = Case.query.get(last_case_id)
    
    # 3.最后获取最近的
    if not case:
        case = Case.query.order_by(Case.time.desc()).first()
    
    # 4. 最终找到的case
    if case:
        session['last_viewed_case'] = case.id
        db.session.commit()
        
        # 解析关键词
        keywords_list = []
        if case.keywords:
            try:
                keywords_list = json.loads(case.keywords)
            except:
                keywords_list = []
        
        # 解析人物列表
        persons_list = []
        if case.person:
            try:
                persons_list = json.loads(case.person)
            except:
                persons_list = []
        
        # 解析法律列表
        laws_list = []
        if case.law:
            try:
                laws_list = json.loads(case.law)
            except:
                laws_list = []
        
        # 收集所有需要高亮的内容
        highlight_items = []
        
        # 添加关键词（蓝色）
        highlight_items.extend([(kw, 'blue') for kw in keywords_list])
        
        # 添加人物姓名（橙色）
        for p in persons_list:
            if isinstance(p, dict) and 'name' in p:
                highlight_items.append((p['name'], 'orange'))
        
        # 添加法律条文（绿色）
        highlight_items.extend([(law, 'green') for law in laws_list])
        
        # 添加法院（紫色）
        if case.court:
            highlight_items.append((case.court, 'purple'))
        
        # 添加地点（棕色）
        if case.location:
            highlight_items.append((case.location, 'brown'))
        
        # 在摘要中高亮所有内容
        highlighted_summary = highlight_multiple_items(
        case.summary if case.summary else "",
        persons_list,
        laws_list,
        case.court,
        case.location,
        case.incident  # 传入纠纷描述
)
        
        return render_template('annotate.html', 
                     case=case, 
                     highlighted_summary=highlighted_summary,
                     laws_list=laws_list,      # 传递法律列表
                     persons_list=persons_list, # 传递人员列表
                     mode='view')
    
    return render_template('annotate.html', case=None, mode='prompt')


def highlight_multiple_items(text, persons_list, laws_list, court, location, incident):
    """高亮多个不同颜色的项目"""
    if not text:
        return text
    
    color_map = {
        'green': '#2e7d32',
        'orange': '#ed6c02',
        'purple': '#9c27b0',
        'brown': '#8b5a2b',
        'red': '#d32f2f'  # 为纠纷关键词添加红色
    }
    
    highlighted = text
    items = []
    
    # 1. 添加人物姓名（橙色）
    for p in persons_list:
        if isinstance(p, dict) and 'name' in p:
            items.append((p['name'], 'orange'))
    
    # 2. 添加法律条文（绿色）
    for law in laws_list:
        if law:
            items.append((law, 'green'))
    
    # 3. 添加法院（紫色）
    if court:
        items.append((court, 'purple'))
    
    # 4. 添加地点（棕色）- 从 location 和 incident 中提取
    # 从 location 字段提取
    if location:
        import re
        locations = re.split(r'[；;、，]', location)
        for loc in locations:
            loc = loc.strip()
            if loc and len(loc) > 2:
                items.append((loc, 'brown'))
    
    # 5. 从纠纷描述中提取关键词（红色）- 可选
    if incident:
        # 常见的纠纷关键词
        dispute_keywords = ['抢劫', '杀人', '故意伤害', '盗窃', '诈骗', '合同纠纷', 
                           '侵权', '劳动争议', '婚姻', '抚养权', '遗产']
        for kw in dispute_keywords:
            if kw in incident:
                items.append((kw, 'red'))
    
    # 按长度排序，长的先替换
    sorted_items = sorted(items, key=lambda x: len(x[0]), reverse=True)
    
    for item_text, color_name in sorted_items:
        if not item_text or len(item_text.strip()) < 2:
            continue
            
        item_str = item_text.strip()
        color_code = color_map.get(color_name, color_name)
        
        # 避免重复替换
        if item_str in highlighted:
            highlighted_word = f'<span style="color: {color_code}; font-weight: bold; background-color: #f0f0f0; padding: 2px 4px; border-radius: 3px;">{item_str}</span>'
            highlighted = highlighted.replace(item_str, highlighted_word)
    
    return highlighted