from openai import OpenAI
import json
from settings import settings  

def analyze_case_with_api(content):
    """调用DeepSeek API分析案件"""
    try:
        client = OpenAI(
            api_key=settings.DEEPSEEK_API_KEY,   
            base_url=settings.DEEPSEEK_BASE_URL  
        )
        
        first_line = content.strip().split('\n')[0]
        
        prompt = f"""
        分析案件，返回JSON格式，包含以下字段：
        1. title：必须是类似"张某、李某...案件类别判决书"的格式，第一行"{first_line}"如果是这种格式就保留，否则重新生成
        2. sort：刑事案件/民事案件/行政案件/其他（根据title中的案件类别判断）
        3. summary：800-1000字的详细摘要，**必须包含**以下信息：法院名称(court)、涉案人员(persons)、相关法律(laws)、纠纷描述(dispute)、案发地点(location)等关键内容，确保摘要完整涵盖案件要点
        4. keywords：5-10个关键词列表
        5. court：审理法院名称
        6. laws：涉及的相关法律条文列表（如["刑法第232条", "民法典第1045条"]）
        7. persons：所有涉案人员列表，每个人员包含角色和姓名（如[{{"role": "上诉人", "name": "张某"}}, {{"role": "被上诉人", "name": "李某"}}]）
        8. dispute：案件纠纷的简要描述
        9. location：案发地点
        
        内容：{content[:2000]}  # 增加输入内容长度
        """
        
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "你是一个法律分析助手，返回纯JSON。title格式必须是'人名...案件类别判决书'。摘要要详细完整，涵盖所有关键信息。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=2000  # 增加输出token数
        )
        
        result = json.loads(response.choices[0].message.content.replace('```json', '').replace('```', ''))
        
        # 确保title格式正确
        title = result.get('title', '')
        if not ('判决书' in title or '裁定书' in title):
            title = first_line[:50]
        
        # 根据title确定sort
        sort = '其他'
        if '刑事' in title:
            sort = '刑事案件'
        elif '民事' in title:
            sort = '民事案件'
        elif '行政' in title:
            sort = '行政案件'
        
        # 处理persons字段，确保是列表
        persons = result.get('persons', [])
        if not isinstance(persons, list):
            persons = []
        
        # 处理laws字段，确保是列表
        laws = result.get('laws', [])
        if not isinstance(laws, list):
            laws = []
            
        # 获取摘要，如果太短就补充
        summary = result.get('summary', '')
        if len(summary) < 300:  # 如果摘要太短
            summary = summary + " " + "（完整摘要请参考案件详情）"
            
        return {
            "title": title[:50],
            "sort": sort,
            "summary": summary[:1000],  # 增加到1000字
            "keywords": result.get('keywords', [])[:10],
            "court": result.get('court', '')[:50],
            "laws": laws,
            "persons": persons,
            "dispute": result.get('dispute', '')[:300],  # 纠纷描述也加长
            "location": result.get('location', '')[:100]
        }
        
    except Exception as e:
        print(f"API调用失败: {e}")
        first_line = content.strip().split('\n')[0]
        sort = '其他'
        if '刑事' in first_line:
            sort = '刑事案件'
        elif '民事' in first_line:
            sort = '民事案件'
        elif '行政' in first_line:
            sort = '行政案件'
            
        return {
            "title": first_line[:50],
            "sort": sort,
            "summary": content[:800] + "...",  # 失败时也用更长的摘要
            "keywords": [],
            "court": "",
            "laws": [],
            "persons": [],
            "dispute": "",
            "location": ""
        }