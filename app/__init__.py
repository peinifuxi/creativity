from flask import Flask
from .index import index_bp
from .manage import manage_bp
from .annotate import annotate_bp
from .statistic import statistic_bp
from .nlp_analyse import nlp_bp
from .database import db, init_data



def create_app():
    app = Flask(__name__)

    app.secret_key = 'prefixkid'
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db.sqlite3'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    with app.app_context():
        db.init_app(app)
        db.create_all()
        # init_data()
    
    # 注册所有蓝图
    app.register_blueprint(index_bp)
    app.register_blueprint(manage_bp)
    app.register_blueprint(annotate_bp)
    app.register_blueprint(statistic_bp)
    app.register_blueprint(nlp_bp)  # 新增注册NLP蓝图
    app.run(debug=True)
    return app

