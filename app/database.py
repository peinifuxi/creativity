from flask_sqlalchemy import SQLAlchemy
from datetime import date, datetime
import json

db = SQLAlchemy()

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
    predict_result = db.Column(db.Text,default='')
    


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