import os
from dotenv import load_dotenv

# 加载.env文件
load_dotenv()

class Settings:
    # 数据库
    SQLALCHEMY_DATABASE_URI = f"mysql+pymysql://root:{os.getenv('DB_PASSWORD')}@localhost/annotation_db?charset=utf8mb4"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # API
    DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY')
    DEEPSEEK_BASE_URL = "https://api.deepseek.com"
    
    # Flask
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-key')
    
    # 业务常量
    MAX_TITLE_LENGTH = 50
    MAX_SUMMARY_LENGTH = 500
    MAX_KEYWORDS = 10

settings = Settings()