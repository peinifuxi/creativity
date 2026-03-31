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
    
    
    law = db.Column(db.String(100), default='')
    summary = db.Column(db.Text, default='')  
    keywords = db.Column(db.Text, default='[]')


    person = db.Column(db.String(100), default='')
    incident = db.Column(db.String(200), default='')
    location = db.Column(db.String(100), default='')

    result = db.Column(db.Text,default='')
    actual_result = db.Column(db.Text,default='')
    predict_result = db.Column(db.Text,default='')
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