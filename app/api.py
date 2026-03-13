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
        分析案件，返回JSON：
        1. title：必须是类似"张某、李某...案件类别判决书"的格式，第一行"{first_line}"如果是这种格式就保留，否则重新生成
        2. sort：刑事案件/民事案件/行政案件/其他（根据title中的案件类别判断）
        3. summary：500字摘要  # ✅ 这里没问题
        4. keywords：5-10个关键词列表
        
        内容：{content[:1500]}
        """
        
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "你是一个法律分析助手，返回纯JSON。title格式必须是'人名...案件类别判决书'。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=1000  #
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
            
        return {
            "title": title[:50],
            "sort": sort,
            "summary": result.get('summary', '')[:500],  
            "keywords": result.get('keywords', [])[:10]
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
            "summary": content[:500] + "...",  
            "keywords": []
        }