# nlp/summarizer.py
import re
from typing import List, Dict

class LegalSummarizer:
    """法律文书摘要器"""
    
    def __init__(self):
        self.legal_keywords = {
            '本院认为': 3.0,
            '判决如下': 3.0,
            '裁定如下': 3.0,
            '经审理查明': 2.5,
            '经查明': 2.5,
            '证据': 1.8,
            '判处': 2.0,
            '上诉': 1.5,
            '抗诉': 1.5,
            '申诉': 1.5
        }
    
    def _clean_text(self, text: str) -> str:
        """清理文本"""
        if not text:
            return ""
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
    
    def _split_sentences(self, text: str) -> List[str]:
        """分割句子"""
        sentences = re.split(r'[。！？；]', text)
        return [s.strip() for s in sentences if len(s.strip()) > 10]
    
    def extract_summary(self, text: str, num_sentences: int = 10) -> Dict:
        """提取摘要"""
        text = self._clean_text(text)
        if len(text) < 100:
            return {'summary': text, 'method': 'raw'}
        
        sentences = self._split_sentences(text)
        
        if len(sentences) <= num_sentences:
            summary = '。'.join(sentences) + '。'
            return {
                'summary': summary,
                'method': 'all',
                'compression_ratio': len(summary) / len(text)
            }
        
        # 计算句子重要性
        scores = []
        for i, sent in enumerate(sentences):
            score = 1.0
            
            # 1. 位置权重
            if i == 0 or i == len(sentences) - 1:
                score *= 2.0
            elif i < 3 or i > len(sentences) - 4:
                score *= 1.5
            
            # 2. 关键词权重
            for keyword, weight in self.legal_keywords.items():
                if keyword in sent:
                    score *= weight
            
            # 3. 长度权重
            if 15 < len(sent) < 100:
                score *= 1.2
            
            scores.append(score)
        
        # 选择分数最高的句子
        top_indices = sorted(
            range(len(scores)),
            key=lambda i: scores[i],
            reverse=True
        )[:num_sentences]
        top_indices.sort()  # 保持原文顺序
        
        # 生成摘要
        selected_sentences = [sentences[i] for i in top_indices]
        summary = '。'.join(selected_sentences) + '。'
        
        return {
            'summary': summary,
            'sentences': selected_sentences,
            'indices': top_indices,
            'method': 'extractive',
            'compression_ratio': len(summary) / len(text)
        }