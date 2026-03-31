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
            cursor.execute("SHOW COLUMNS FROM cases LIKE 'actual_result'")
            has_actual_result = cursor.fetchone() is not None

            cursor.execute("SHOW COLUMNS FROM cases LIKE 'predict_method'")
            has_predict_method = cursor.fetchone() is not None

            cursor.execute("SHOW COLUMNS FROM cases LIKE 'predict_prompt_template'")
            has_predict_prompt_template = cursor.fetchone() is not None

            if not has_actual_result:
                cursor.execute("ALTER TABLE cases ADD COLUMN actual_result TEXT NULL")
                cursor.execute("UPDATE cases SET actual_result = result WHERE (actual_result IS NULL OR actual_result = '')")

            if not has_predict_method:
                cursor.execute("ALTER TABLE cases ADD COLUMN predict_method VARCHAR(50) DEFAULT 'official_step'")

            if not has_predict_prompt_template:
                cursor.execute("ALTER TABLE cases ADD COLUMN predict_prompt_template TEXT NULL")

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