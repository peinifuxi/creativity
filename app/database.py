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
    cause = db.Column(db.String(200))
    result = db.Column(db.String(200))
    content = db.Column(db.Text)
    browses = db.Column(db.Integer, default=0)
    
    # ========== 新增NLP相关字段 ==========
    summary = db.Column(db.Text, default='')  # 文本摘要
    keywords = db.Column(db.Text, default='[]')  # 关键词列表（JSON格式）
    is_nlp_analyzed = db.Column(db.Boolean, default=False)  # 是否已分析
    analyzed_at = db.Column(db.DateTime)  # 分析时间


     # 添加索引
    __table_args__ = (
        db.Index('idx_case_sort', sort),              # 分类筛选
    )
    
    def get_keywords_list(self):
        """获取关键词列表"""
        if self.keywords and self.keywords != '[]':
            try:
                return json.loads(self.keywords)
            except:
                return []
        return []
    
    def get_analysis_info(self):
        """获取分析信息"""
        return {
            'summary': self.summary,
            'keywords': self.get_keywords_list(),
            'is_analyzed': self.is_nlp_analyzed,
            'analyzed_at': self.analyzed_at.strftime('%Y-%m-%d %H:%M') if self.analyzed_at else None
        }

def init_data():
    """初始化数据"""
    if Case.query.count() == 0:
        initial_cases = [
            Case(
            ),
        ]
        db.session.add_all(initial_cases)
        db.session.commit()