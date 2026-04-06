import pymysql
from sqlalchemy.engine.url import make_url

from app import create_app
from app.database import init_database
from settings import settings


def create_mysql_database():
    """如果数据库不存在，先创建数据库本身。"""
    url = make_url(settings.SQLALCHEMY_DATABASE_URI)
    database_name = url.database
    charset = url.query.get('charset', 'utf8mb4')

    connection = pymysql.connect(
        host=url.host or 'localhost',
        port=url.port or 3306,
        user=url.username,
        password=url.password or '',
        charset=charset,
    )

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{database_name}` "
                f"CHARACTER SET {charset} COLLATE {charset}_unicode_ci"
            )
        connection.commit()
    finally:
        connection.close()


def ensure_schema_columns():
    """补齐历史数据库缺失字段。"""
    url = make_url(settings.SQLALCHEMY_DATABASE_URI)

    connection = pymysql.connect(
        host=url.host or 'localhost',
        port=url.port or 3306,
        user=url.username,
        password=url.password or '',
        database=url.database,
        charset=url.query.get('charset', 'utf8mb4'),
    )

    try:
        with connection.cursor() as cursor:
            def has_column(column_name: str) -> bool:
                cursor.execute(f"SHOW COLUMNS FROM cases LIKE '{column_name}'")
                return cursor.fetchone() is not None

            has_actual_result = has_column('actual_result')
            has_predict_method = has_column('predict_method')
            has_predict_prompt_template = has_column('predict_prompt_template')
            has_court = has_column('court')
            has_graph_result = has_column('graph_result')

            if not has_actual_result:
                cursor.execute("ALTER TABLE cases ADD COLUMN actual_result TEXT NULL")
                cursor.execute("UPDATE cases SET actual_result = result WHERE (actual_result IS NULL OR actual_result = '')")

            if not has_predict_method:
                cursor.execute("ALTER TABLE cases ADD COLUMN predict_method VARCHAR(50) DEFAULT 'official_step'")

            if not has_predict_prompt_template:
                cursor.execute("ALTER TABLE cases ADD COLUMN predict_prompt_template TEXT NULL")

            if not has_court:
                cursor.execute("ALTER TABLE cases ADD COLUMN court VARCHAR(50) DEFAULT ''")

            if not has_graph_result:
                cursor.execute("ALTER TABLE cases ADD COLUMN graph_result TEXT NULL")

            # 旧表结构中的 law/person/incident/location 长度较短，统一放宽为兼容图谱元数据的长度。
            cursor.execute("ALTER TABLE cases MODIFY COLUMN law TEXT")
            cursor.execute("ALTER TABLE cases MODIFY COLUMN person TEXT")
            cursor.execute("ALTER TABLE cases MODIFY COLUMN incident TEXT")
            cursor.execute("ALTER TABLE cases MODIFY COLUMN location VARCHAR(200)")

        connection.commit()
    finally:
        connection.close()


def main():
    create_mysql_database()

    app = create_app()
    init_database(app)
    ensure_schema_columns()

    print('数据库和数据表创建完成')


if __name__ == '__main__':
    main()