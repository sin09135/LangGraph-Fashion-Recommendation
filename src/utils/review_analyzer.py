"""
리뷰 분석기
리뷰 텍스트를 분석하여 키워드 추출, 감정 분석, 스타일 매칭을 수행합니다.
"""

import re
import json
import pandas as pd
from typing import List, Dict, Any, Tuple
from collections import Counter
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


class ReviewAnalyzer:
    """리뷰 텍스트 분석기"""
    
    def __init__(self):
        # 패션 관련 키워드 사전
        self.fashion_keywords = {
            '착용감': ['착용감', '입기', '편안', '불편', '딱맞', '크다', '작다', '핏', '핏감'],
            '스타일': ['스타일', '패션', '코디', '매치', '룩', '느낌', '무드', '분위기'],
            '색상': ['색상', '컬러', '색깔', '블랙', '화이트', '그레이', '네이비', '베이지'],
            '소재': ['소재', '면', '코튼', '린넨', '데님', '니트', '실크', '폴리에스터'],
            '사이즈': ['사이즈', '크기', 'M', 'L', 'XL', 'S', '오버핏', '레귤러핏', '슬림핏'],
            '품질': ['품질', '퀄리티', '내구성', '마모', '색바램', '수선', '스티치'],
            '가격': ['가격', '가성비', '비싸다', '저렴', '합리적', '돈값', '아깝다'],
            '배송': ['배송', '택배', '빠르다', '느리다', '포장', '박스', '플러스배송']
        }
        
        # 긍정/부정 키워드
        self.positive_words = [
            '좋다', '만족', '추천', '훌륭', '완벽', '최고', '대박', '감동', '사랑',
            '편안', '예쁘다', '멋지다', '깔끔', '세련', '고급', '품질', '가성비'
        ]
        
        self.negative_words = [
            '별로', '실망', '아쉽', '불편', '크다', '작다', '비싸다', '아깝다',
            '색바램', '마모', '퀄리티', '기대이하', '후회', '환불'
        ]
        
        # TF-IDF 벡터라이저 초기화
        self.vectorizer = TfidfVectorizer(
            max_features=1000,
            stop_words=['이', '가', '을', '를', '의', '에', '로', '으로', '도', '만', '은', '는'],
            ngram_range=(1, 2)
        )
        
    def extract_keywords(self, text: str) -> Dict[str, List[str]]:
        """리뷰 텍스트에서 패션 관련 키워드 추출"""
        text_lower = text.lower()
        extracted_keywords = {}
        
        for category, keywords in self.fashion_keywords.items():
            found_keywords = []
            for keyword in keywords:
                if keyword in text_lower:
                    found_keywords.append(keyword)
            if found_keywords:
                extracted_keywords[category] = found_keywords
        
        return extracted_keywords
    
    def analyze_sentiment(self, text: str) -> Dict[str, float]:
        """리뷰 텍스트 감정 분석"""
        text_lower = text.lower()
        
        positive_count = sum(1 for word in self.positive_words if word in text_lower)
        negative_count = sum(1 for word in self.negative_words if word in text_lower)
        
        total_words = len(text.split())
        if total_words == 0:
            return {'positive_score': 0, 'negative_score': 0, 'sentiment_score': 0}
        
        positive_score = positive_count / total_words
        negative_score = negative_count / total_words
        sentiment_score = positive_score - negative_score
        
        return {
            'positive_score': positive_score,
            'negative_score': negative_score,
            'sentiment_score': sentiment_score
        }
    
    def extract_style_info(self, text: str) -> Dict[str, Any]:
        """리뷰에서 스타일 관련 정보 추출"""
        style_info = {
            'fit_type': None,
            'color_mentioned': [],
            'material_mentioned': [],
            'size_feedback': None,
            'style_keywords': []
        }
        
        text_lower = text.lower()
        
        # 핏 타입 추출
        if '오버핏' in text_lower or '오버사이즈' in text_lower:
            style_info['fit_type'] = '오버핏'
        elif '레귤러핏' in text_lower or '레귤러' in text_lower:
            style_info['fit_type'] = '레귤러핏'
        elif '슬림핏' in text_lower or '슬림' in text_lower:
            style_info['fit_type'] = '슬림핏'
        
        # 색상 추출
        colors = ['블랙', '화이트', '그레이', '네이비', '베이지', '브라운', '핑크', '레드', '블루']
        for color in colors:
            if color in text_lower:
                style_info['color_mentioned'].append(color)
        
        # 소재 추출
        materials = ['면', '코튼', '린넨', '데님', '니트', '실크', '폴리에스터']
        for material in materials:
            if material in text_lower:
                style_info['material_mentioned'].append(material)
        
        # 사이즈 피드백
        if '크다' in text_lower or '크네' in text_lower:
            style_info['size_feedback'] = '크다'
        elif '작다' in text_lower or '작네' in text_lower:
            style_info['size_feedback'] = '작다'
        elif '딱맞' in text_lower or '적당' in text_lower:
            style_info['size_feedback'] = '적당'
        
        # 스타일 키워드
        style_keywords = ['캐주얼', '정장', '스포티', '빈티지', '미니멀', '스트릿', '클래식', '모던']
        for keyword in style_keywords:
            if keyword in text_lower:
                style_info['style_keywords'].append(keyword)
        
        return style_info
    
    def analyze_product_reviews(self, reviews: List[Dict[str, Any]]) -> Dict[str, Any]:
        """상품의 모든 리뷰를 종합 분석"""
        if not reviews:
            return {}
        
        all_texts = [review.get('content', '') for review in reviews]
        all_keywords = []
        all_sentiments = []
        all_style_infos = []
        
        for text in all_texts:
            if text.strip():
                # 키워드 추출
                keywords = self.extract_keywords(text)
                all_keywords.append(keywords)
                
                # 감정 분석
                sentiment = self.analyze_sentiment(text)
                all_sentiments.append(sentiment)
                
                # 스타일 정보 추출
                style_info = self.extract_style_info(text)
                all_style_infos.append(style_info)
        
        # 종합 분석 결과
        analysis_result = {
            'total_reviews': len(reviews),
            'avg_sentiment': np.mean([s['sentiment_score'] for s in all_sentiments]) if all_sentiments else 0,
            'positive_ratio': sum(1 for s in all_sentiments if s['sentiment_score'] > 0) / len(all_sentiments) if all_sentiments else 0,
            'keyword_summary': self._summarize_keywords(all_keywords),
            'style_summary': self._summarize_styles(all_style_infos),
            'common_phrases': self._extract_common_phrases(all_texts)
        }
        
        return analysis_result
    
    def _summarize_keywords(self, all_keywords: List[Dict[str, List[str]]]) -> Dict[str, List[str]]:
        """키워드 요약"""
        summary = {}
        for category in self.fashion_keywords.keys():
            category_keywords = []
            for keywords in all_keywords:
                if category in keywords:
                    category_keywords.extend(keywords[category])
            
            if category_keywords:
                # 빈도순으로 정렬
                counter = Counter(category_keywords)
                summary[category] = [word for word, _ in counter.most_common(5)]
        
        return summary
    
    def _summarize_styles(self, all_style_infos: List[Dict[str, Any]]) -> Dict[str, Any]:
        """스타일 정보 요약"""
        fit_types = [info['fit_type'] for info in all_style_infos if info['fit_type']]
        colors = [color for info in all_style_infos for color in info['color_mentioned']]
        materials = [material for info in all_style_infos for material in info['material_mentioned']]
        style_keywords = [keyword for info in all_style_infos for keyword in info['style_keywords']]
        
        return {
            'most_common_fit': Counter(fit_types).most_common(1)[0][0] if fit_types else None,
            'popular_colors': [color for color, _ in Counter(colors).most_common(3)],
            'popular_materials': [material for material, _ in Counter(materials).most_common(3)],
            'style_keywords': [keyword for keyword, _ in Counter(style_keywords).most_common(5)]
        }
    
    def _extract_common_phrases(self, texts: List[str]) -> List[str]:
        """자주 언급되는 문구 추출"""
        # 간단한 구현: 2-3단어 조합 찾기
        phrases = []
        for text in texts:
            words = text.split()
            for i in range(len(words) - 1):
                phrase = f"{words[i]} {words[i+1]}"
                if len(phrase) > 3:  # 너무 짧은 조합 제외
                    phrases.append(phrase)
        
        counter = Counter(phrases)
        return [phrase for phrase, count in counter.most_common(10) if count > 1]
    
    def find_similar_products_by_reviews(self, 
                                       target_reviews: List[Dict[str, Any]], 
                                       all_products_reviews: Dict[str, List[Dict[str, Any]]],
                                       top_k: int = 5) -> List[Tuple[str, float]]:
        """리뷰 내용 기반으로 유사한 상품 찾기"""
        if not target_reviews:
            return []
        
        # 타겟 상품의 리뷰 텍스트 결합
        target_text = ' '.join([review.get('content', '') for review in target_reviews])
        
        # 모든 상품의 리뷰 텍스트 준비
        product_texts = {}
        for product_id, reviews in all_products_reviews.items():
            if reviews:
                product_texts[product_id] = ' '.join([review.get('content', '') for review in reviews])
        
        if not product_texts:
            return []
        
        # TF-IDF 벡터화
        all_texts = [target_text] + list(product_texts.values())
        tfidf_matrix = self.vectorizer.fit_transform(all_texts)
        
        # 코사인 유사도 계산
        similarities = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:])
        
        # 유사도 순으로 정렬
        product_ids = list(product_texts.keys())
        similarity_scores = list(zip(product_ids, similarities[0]))
        similarity_scores.sort(key=lambda x: x[1], reverse=True)
        
        return similarity_scores[:top_k]
    
    def generate_review_based_recommendation_reason(self, 
                                                  product_analysis: Dict[str, Any],
                                                  user_query: str = "") -> str:
        """리뷰 분석 결과를 바탕으로 추천 이유 생성"""
        reasons = []
        
        # 감정 점수 기반
        sentiment_score = product_analysis.get('avg_sentiment', 0)
        if sentiment_score > 0.1:
            reasons.append("사용자들이 매우 만족하는 상품")
        elif sentiment_score > 0:
            reasons.append("전반적으로 좋은 평가를 받은 상품")
        
        # 긍정 비율 기반
        positive_ratio = product_analysis.get('positive_ratio', 0)
        if positive_ratio > 0.8:
            reasons.append(f"리뷰의 {int(positive_ratio * 100)}%가 긍정적")
        
        # 키워드 기반
        keyword_summary = product_analysis.get('keyword_summary', {})
        if '착용감' in keyword_summary:
            reasons.append("착용감이 좋다는 리뷰가 많음")
        if '가격' in keyword_summary:
            reasons.append("가성비가 좋다는 평가")
        
        # 스타일 정보 기반
        style_summary = product_analysis.get('style_summary', {})
        if style_summary.get('most_common_fit'):
            reasons.append(f"{style_summary['most_common_fit']} 스타일로 인기")
        
        if not reasons:
            reasons.append("사용자들의 다양한 경험을 바탕으로 추천")
        
        return " ".join(reasons)


def main():
    """테스트 함수"""
    analyzer = ReviewAnalyzer()
    
    # 테스트 리뷰
    test_reviews = [
        {
            'content': '착용감이 정말 좋아요! 오버핏이라 편안하고 스타일리시해요. 블랙 컬러가 깔끔하고 가성비도 좋습니다.',
            'rating': 5
        },
        {
            'content': '사이즈가 딱 맞고 소재도 좋아요. 면 소재라 편안하고 세탁도 잘 됩니다.',
            'rating': 4
        },
        {
            'content': '색상이 예쁘고 핏감이 완벽해요. 캐주얼하게 입기 좋습니다.',
            'rating': 5
        }
    ]
    
    # 분석 실행
    analysis = analyzer.analyze_product_reviews(test_reviews)
    
    print("=== 리뷰 분석 결과 ===")
    print(f"총 리뷰 수: {analysis['total_reviews']}")
    print(f"평균 감정 점수: {analysis['avg_sentiment']:.3f}")
    print(f"긍정 비율: {analysis['positive_ratio']:.1%}")
    print(f"키워드 요약: {analysis['keyword_summary']}")
    print(f"스타일 요약: {analysis['style_summary']}")
    
    # 추천 이유 생성
    reason = analyzer.generate_review_based_recommendation_reason(analysis)
    print(f"추천 이유: {reason}")


if __name__ == "__main__":
    main() 