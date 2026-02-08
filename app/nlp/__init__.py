from .summarizer import LegalSummarizer
from .keyword import LegalKeywordExtractor

class LegalDocumentAnalyzer:
    """法律文档分析器（整合类）"""
    
    def __init__(self):
        self.summarizer = LegalSummarizer()
        self.keyword_extractor = LegalKeywordExtractor()
    
    def analyze(self, text: str, case_info: dict = None) -> dict:
        """
        分析法律文档
        Args:
            text: 文书内容
            case_info: 案件信息（可选）
        """
        if not text or len(text.strip()) < 50:
            return None
        
        # 提取摘要
        summary_result = self.summarizer.extract_summary(text, num_sentences=10)
        
        # 提取关键词
        keyword_result = self.keyword_extractor.extract_keywords(text)
        
        # 如果提供案件信息，增强关键词
        if case_info:
            keyword_result = self._enhance_keywords(keyword_result, case_info)
        
        return {
            'summary': summary_result.get('summary', ''),
            'keywords': keyword_result,
            'stats': {
                'text_length': len(text),
                'summary_length': len(summary_result.get('summary', '')),
                'keyword_count': len(keyword_result)
            }
        }
    
    def _enhance_keywords(self, keyword_result: dict, case_info: dict) -> dict:
        """使用案件信息增强关键词"""
        enhanced = keyword_result.copy()
        
        # 添加案件信息作为关键词
        if case_info.get('cause'):
            enhanced['categorized']['案件信息'] = [{
                'word': case_info['cause'],
                'weight': 10.0,
                'category': '案由'
            }]
        
        if case_info.get('result'):
            if '案件信息' not in enhanced['categorized']:
                enhanced['categorized']['案件信息'] = []
            enhanced['categorized']['案件信息'].append({
                'word': case_info['result'],
                'weight': 9.0,
                'category': '判决结果'
            })
        
        return enhanced

# 创建全局实例
analyzer = LegalDocumentAnalyzer()