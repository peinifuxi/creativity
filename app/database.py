from flask_sqlalchemy import SQLAlchemy
from datetime import date, datetime
import json

db = SQLAlchemy()


def init_database(app):
    """根据当前模型创建所有数据表。"""
    with app.app_context():
        db.create_all()

class Case(db.Model):
    __tablename__ = 'cases'
    
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=True)
    time = db.Column(db.Date, default=date.today) 
    sort = db.Column(db.String(10))
    
    content = db.Column(db.Text, default='') 
    
    court = db.Column(db.String(50), default='')
    law = db.Column(db.Text, default='[]')
    summary = db.Column(db.Text, default='')  
    keywords = db.Column(db.Text, default='[]')


    person = db.Column(db.Text, default='[]')
    incident = db.Column(db.Text, default='')
    location = db.Column(db.String(200), default='')

    result = db.Column(db.Text,default='')
    actual_result = db.Column(db.Text,default='')
    predict_result = db.Column(db.Text,default='')
    graph_result = db.Column(db.Text, default='')
    predict_method = db.Column(db.String(50), default='official_step')
    predict_prompt_template = db.Column(db.Text, default='')
    


     # 索引
    __table_args__ = (
        db.Index('idx_case_sort', sort),              # 分类筛选
    )
    

    def get_keywords_list(self):
        """获取关键词列表"""
        if not self.keywords or self.keywords == '[]':
            return []
        try:
            return json.loads(self.keywords)
        except:
            return []

    def get_law_list(self):
        """获取法规列表，兼容旧字符串格式。"""
        if not self.law:
            return []
        try:
            parsed = json.loads(self.law)
            if isinstance(parsed, list):
                return parsed
        except:
            pass
        return [self.law] if str(self.law).strip() else []

    def get_persons_list(self):
        """获取涉案人员列表，兼容旧字符串格式。"""
        if not self.person:
            return []
        try:
            parsed = json.loads(self.person)
            if isinstance(parsed, list):
                return parsed
        except:
            pass
        raw = str(self.person).strip()
        if not raw:
            return []
        return [{"name": raw, "role": ""}]

    def get_graph_payload(self):
        """获取知识图谱结构，默认返回空图。"""
        empty_payload = {
            "graph": {"nodes": [], "links": []},
            "raw": {},
            "meta": {
                "version": "legacy",
                "updated_at": "",
                "chunk_count": 0,
                "source": ""
            }
        }
        if not self.graph_result or not self.graph_result.strip():
            return empty_payload
        try:
            parsed = json.loads(self.graph_result)
            if isinstance(parsed, dict):
                graph = parsed.get("graph") if isinstance(parsed.get("graph"), dict) else {"nodes": [], "links": []}
                raw = parsed.get("raw") if isinstance(parsed.get("raw"), dict) else {}
                meta = parsed.get("meta") if isinstance(parsed.get("meta"), dict) else empty_payload["meta"]
                nodes = graph.get("nodes") if isinstance(graph.get("nodes"), list) else []
                links = graph.get("links") if isinstance(graph.get("links"), list) else []
                return {"graph": {"nodes": nodes, "links": links}, "raw": raw, "meta": meta}
        except:
            pass
        return empty_payload

    def get_actual_result(self):
        """获取真实判决结果，优先使用actual_result，谨慎兼容旧字段result。"""
        if self.actual_result and self.actual_result.strip():
            return self.actual_result

        legacy_result = (self.result or '').strip()
        if not legacy_result:
            return ''

        # 兼容历史数据：过长文本大概率是误写入的完整文书，不作为“真实判决结果”展示
        if len(legacy_result) > 300:
            return ''

        return legacy_result