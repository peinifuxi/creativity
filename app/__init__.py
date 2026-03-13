from flask import Flask
from .index import index_bp
from .manage import manage_bp
from .annotate import annotate_bp
from .statistic import statistic_bp
from .predict import predict_bp
from .database import db
import pymysql
import sys
import os

# 只添加这两行
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from settings import settings

pymysql.install_as_MySQLdb()

def create_app():
    app = Flask(__name__)

    app.config['SQLALCHEMY_DATABASE_URI'] = settings.SQLALCHEMY_DATABASE_URI  
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SQLALCHEMY_ECHO'] = False  
    app.config['SECRET_KEY'] = settings.SECRET_KEY  
    
    db.init_app(app)
    
    app.register_blueprint(index_bp)
    app.register_blueprint(manage_bp)
    app.register_blueprint(annotate_bp)
    app.register_blueprint(statistic_bp)
    app.register_blueprint(predict_bp)  
    
    
    return app
