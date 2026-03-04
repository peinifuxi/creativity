import jieba
import jieba.analyse
import logging
from typing import List, Dict

jieba.setLogLevel(logging.INFO)

class LegalKeywordExtractor:
    """法律关键词提取器"""
    
    def __init__(self):
        # 添加法律专业词汇
        self._init_legal_dict()
        
        # 关键词分类
        self.categories = {
            '刑事罪名': ['故意杀人', '抢劫', '盗窃', '诈骗', '贪污', '受贿', '毒品'],
            '民事案由': ['合同纠纷', '侵权责任', '婚姻家庭', '继承', '劳动争议'],
            '行政案件': ['行政处罚', '行政许可', '行政强制'],
            '程序阶段': ['一审', '二审', '上诉', '抗诉', '裁定', '判决'],
            '刑罚种类': ['死刑', '有期徒刑', '罚金', '缓刑', '剥夺政治权利']
        }
    
    def _init_legal_dict(self):
        """初始化法律词典"""
        legal_words = [
            '故意杀人罪', '抢劫罪', '盗窃罪', '诈骗罪', '贪污罪', '受贿罪',
            '合同纠纷', '侵权责任', '行政处罚', '行政复议', '行政强制',
            '有期徒刑', '无期徒刑', '死刑', '缓刑', '罚金', '违约金',
            '一审', '二审', '再审', '上诉', '抗诉', '申诉', '裁定',
            '判决', '调解', '被告人', '原告', '被告', '上诉人'
        ]
        
        for word in legal_words:
            jieba.add_word(word)
    
    def extract_keywords(self, text: str, top_k: int = 30) -> Dict:
        """提取关键词"""
        if not text or len(text.strip()) < 50:
            return {'all': [], 'categorized': {}, 'top10': []}
        
        # 使用TF-IDF提取关键词
        keywords = jieba.analyse.extract_tags(
            text,
            topK=top_k,
            withWeight=True,
            allowPOS=('n', 'vn', 'nr', 'ns', 'nt', 'nz')
        )
        
        # 转换为列表
        keyword_list = []
        for word, weight in keywords:
            if len(word) > 1:  # 过滤单字
                keyword_list.append({
                    'word': word,
                    'weight': float(weight),
                    'category': '未分类'
                })
        
        # 分类关键词
        categorized = self._categorize_keywords(keyword_list)
        
        return {
            'all': keyword_list[:top_k],
            'categorized': categorized,
            'top10': keyword_list[:10]
        }
    
    def _categorize_keywords(self, keywords: List[Dict]) -> Dict[str, List]:
        """分类关键词"""
        categorized = {}
        
        for category, word_list in self.categories.items():
            category_keywords = []
            
            for keyword in keywords:
                word = keyword['word']
                for legal_word in word_list:
                    if legal_word in word:
                        kw_copy = keyword.copy()
                        kw_copy['category'] = category
                        category_keywords.append(kw_copy)
                        break
            
            if category_keywords:
                # 去重和排序
                seen = set()
                unique_kws = []
                for kw in category_keywords:
                    if kw['word'] not in seen:
                        seen.add(kw['word'])
                        unique_kws.append(kw)
                
                categorized[category] = sorted(
                    unique_kws,
                    key=lambda x: x['weight'],
                    reverse=True
                )[:5]  # 每类最多5个
        
        # 未分类的关键词
        uncategorized = [kw for kw in keywords if kw['category'] == '未分类']
        if uncategorized:
            categorized['其他关键词'] = uncategorized[:10]
        
        return categorized