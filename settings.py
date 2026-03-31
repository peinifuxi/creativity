import os
from dotenv import load_dotenv
from urllib.parse import quote_plus

# 加载.env文件
load_dotenv()

class Settings:
    # 数据库
    DB_HOST = os.getenv('DB_HOST', '127.0.0.1')
    DB_PORT = int(os.getenv('DB_PORT', '3306'))
    DB_USER = os.getenv('DB_USER', 'root')
    DB_PASSWORD = quote_plus(os.getenv('DB_PASSWORD', ''))
    DB_NAME = os.getenv('DB_NAME', 'annotation_db')
    SQLALCHEMY_DATABASE_URI = (
        f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
        "?charset=utf8mb4"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # API
    DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY')
    DEEPSEEK_BASE_URL = "https://api.deepseek.com"

    # 判决预测方法配置（四种方案）
    PREDICT_METHOD_DEFAULT = os.getenv('PREDICT_METHOD_DEFAULT', 'official_step')

    # 方案1：官方现成大模型（硅基流动）
    SILICONFLOW_API_KEY = os.getenv('SILICONFLOW_API_KEY')
    SILICONFLOW_BASE_URL = os.getenv('SILICONFLOW_BASE_URL', 'https://api.siliconflow.cn/v1')
    SILICONFLOW_MODEL = os.getenv('SILICONFLOW_MODEL', 'deepseek-ai/DeepSeek-V3.2')
    SILICONFLOW_TIMEOUT = int(os.getenv('SILICONFLOW_TIMEOUT', '90'))

    # 方案2：自部署微调模型（预留）
    SELF_HOSTED_MODEL_URL = os.getenv('SELF_HOSTED_MODEL_URL', '')
    SELF_HOSTED_API_KEY = os.getenv('SELF_HOSTED_API_KEY', '')
    SELF_HOSTED_MODEL_NAME = os.getenv('SELF_HOSTED_MODEL_NAME', 'lawgpt')
    SELF_HOSTED_TIMEOUT = int(os.getenv('SELF_HOSTED_TIMEOUT', '60'))

    # 方案3：Coze工作流（预留）
    COZE_WORKFLOW_URL = os.getenv('COZE_WORKFLOW_URL', '')
    COZE_API_KEY = os.getenv('COZE_API_KEY', '')
    COZE_PROJECT_ID = os.getenv('COZE_PROJECT_ID', '')
    COZE_SESSION_ID = os.getenv('COZE_SESSION_ID', '')
    COZE_TIMEOUT = int(os.getenv('COZE_TIMEOUT', '90'))
    
    # Flask
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-key')
    
    # 业务常量
    MAX_TITLE_LENGTH = 50
    MAX_SUMMARY_LENGTH = 500
    MAX_KEYWORDS = 10

settings = Settings()