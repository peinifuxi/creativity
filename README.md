📋 法律文书标注与分析系统
一个基于Flask的法律文书智能标注与分析系统，自动提取文书摘要和关键词，支持案件管理和统计。

🚀 快速开始
环境要求
Python 3.8+

pip（Python包管理器）

安装步骤
克隆项目

bash
git clone <项目地址>
cd annotation_system
安装依赖

bash
pip install -r requirements
运行应用

bash
python app.py
# 或
python -m app
访问应用
打开浏览器访问：http://127.0.0.1:5000

📁 项目结构
text
annotation_system/
├── app.py                    # 主应用入口


│
├── app/                    # 蓝图模块
├── __init__.py             # 应用模块入口
│   ├── index.py            # 首页蓝图（案件提交）
│   ├── annotate.py         # 标注页面蓝图
│   ├── statistic.py        # 统计页面蓝图
│   ├──  manage.py           # 管理页面蓝图
│   ├── nlp.py              # 自然语言处理蓝图
|   └── database.py         # 数据库模型定义
│
├── nlp/                     # NLP处理模块
│   ├── __init__.py         # NLP模块入口
│   ├── summarizer.py       # 文本摘要功能
│   └── keyword_extractor.py # 关键词提取功能
│
├── templates/              # HTML模板
│   ├── index.html         # 首页（案件提交）
│   ├── annotate.html      # 标注页面
│   ├── statistic.html     # 统计页面
│   └── manage.html        # 管理页面
│
└── data/                   # 数据文件（可选）
    └── legal_dict.txt     # 法律专业词典
📦 依赖说明
核心依赖
Flask (2.3.0+) - Web框架

Flask-SQLAlchemy (3.0.0+) - 数据库ORM

jieba (0.42.1+) - 中文分词和NLP处理

安装所有依赖
bash
pip install Flask Flask-SQLAlchemy jieba
或使用提供的 requirements.txt：

bash
pip install -r requirements.txt
🔧 配置说明
数据库配置
默认使用SQLite数据库，文件为 db.sqlite3

修改数据库配置（在 app.py 中）：

python
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///your_database.db'
Session配置
确保在 app.py 中设置secret_key：

python
app.secret_key = 'your-secret-key-here'
📝 功能说明
1. 首页 (/)
提交新的法律文书案件

自动进行NLP分析（提取摘要和关键词）

2. 标注页面 (/annotate)
查看案件详细信息

左栏：显示自动提取的关键词

右栏：

文书摘要（自动生成）

完整文书内容（可展开/收起）

自动记录最近查看的案件

3. 统计页面 (/statistic)
显示当前查看案件的关键词统计

与标注页面保持同步（显示同一案件）

4. 管理页面 (/manage)
查看所有案件列表

删除案件

点击案件名称查看详情

🤖 NLP功能
自动提取功能
文本摘要

基于TextRank算法

提取文书核心内容（约5句话）

智能识别法律文书重要部分

关键词提取

基于TF-IDF算法

分类显示：罪名、程序、刑罚等

支持法律专业术语识别

自定义词典
系统使用法律专业词典（data/legal_dict.txt），包含：

法律罪名：故意杀人罪、抢劫罪等

法律程序：一审、二审、上诉等

法律术语：有期徒刑、罚金等

🗄️ 数据库模型
Case表结构
python
class Case:
    id: Integer                    # 主键
    name: String(50)               # 案件名称
    sort: String(10)               # 案件类型（刑事/民事/行政）
    cause: String(200)             # 案由
    result: String(200)            # 判决结果
    content: Text                  # 文书内容
    browses: Integer               # 浏览量
    
    # NLP分析结果
    summary: Text                  # 文本摘要
    keywords: Text                 # 关键词（JSON格式）
    is_nlp_analyzed: Boolean       # 是否已分析
    analyzed_at: DateTime          # 分析时间
🔍 使用示例
提交案件
访问 http://127.0.0.1:5000

填写：

案例名称：测试案件

案例类型：刑事

文书内容：（粘贴裁判文书）

点击提交，自动跳转到标注页面

查看分析结果
标注页面：显示摘要和关键词

统计页面：显示关键词统计

管理页面：查看所有案件

🐛 常见问题
Q1: 启动时出现端口占用错误
bash
# 方法1：更换端口
python app.py --port=5001

# 方法2：结束占用进程（Windows）
netstat -ano | findstr :5000
taskkill /PID [进程ID] /F
Q2: 关键词没有显示
检查是否安装jieba：pip install jieba

检查文书内容是否足够长（>50字符）

查看控制台是否有NLP分析错误

Q3: Session不工作
确保在 app.py 中设置了secret_key：

python
app.secret_key = 'your-secret-key'
Q4: 数据库表不存在
删除旧的数据库文件，重新运行应用：

bash
# 删除 db.sqlite3 文件
python app.py  # 自动创建新表
📊 技术栈
后端：Flask + SQLAlchemy

前端：HTML + Jinja2模板

NLP：jieba中文分词

数据库：SQLite（可更换为MySQL/PostgreSQL）

样式：内联CSS（浅蓝色主题）

🔄 工作流程
text
用户提交文书 → 保存到数据库 → 自动NLP分析 → 
↓
标注页面显示结果 ← 跳转 ← 保存分析结果
↓  
统计页面同步显示 ← Session记录当前案件
📈 扩展建议
可添加的功能
批量导入：支持上传多个文书文件

高级搜索：按关键词搜索案件

分析报告：生成详细的分析报告

用户系统：多用户支持

API接口：提供RESTful API

性能优化
使用缓存减少NLP分析时间

数据库索引优化

异步处理长文本分析

📄 许可证
本项目仅供学习使用。

🙏 致谢
jieba - 优秀的中文分词工具

Flask - 轻量级Web框架

SQLAlchemy - Python SQL工具包

📞 联系
如有问题或建议，请提交Issue或联系项目维护者。

开始使用：python app.py → 访问 http://localhost:5000

祝您使用愉快！🎉
