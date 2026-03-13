from app import create_app
import os


 ##                 sudo service mysql start      wsl启动mysql数据库

app = create_app()


if __name__ == '__main__':
    
    app.run(port=5000)

    