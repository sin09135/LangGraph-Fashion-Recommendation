"""
PostgreSQL 기반 추천 에이전트
고성능 관계형 데이터베이스를 활용한 추천 시스템
"""

import os
import sys
import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import math
import re

# 프로젝트 루트 경로 추가
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from database.postgresql_manager import PostgreSQLManager

@dataclass
class ProductRecommendation:
    """상품 추천 데이터 클래스"""
    product_id: str
    product_name: str
    category: str
    style_keywords: List[str]
    rating: float
    review_count: int
    description: str
    recommendation_reason: str
    confidence_score: float
    price: Optional[str] = None
    url: str = ''
    image_url: str = ''
    representative_review: Optional[str] = None

def safe_int(val, default=0):
    """안전한 정수 변환"""
    try:
        if val is None or (isinstance(val, float) and math.isnan(val)):
            return default
        return int(val)
    except Exception:
        return default

def safe_float(val, default=0.0):
    """안전한 실수 변환"""
    try:
        if val is None or (isinstance(val, float) and math.isnan(val)):
            return default
        return float(val)
    except Exception:
        return default

class PostgreSQLRecommendationAgent:
    """PostgreSQL 기반 추천 에이전트"""
    
    def __init__(self, 
                 host: str = "localhost",
                 port: int = 5432,
                 database: str = "fashion_recommendation",
                 user: str = "postgres",
                 password: str = "password"):
        
        self.pg_manager = PostgreSQLManager(
            host=host,
            port=port,
            database=database,
            user=user,
            password=password
        )
        self.recommendation_history: List[Dict[str, Any]] = []
        
        # 시스템 프롬프트
        self.system_prompt = """
        당신은 패션 상품 추천 전문가입니다.
        
        추천 설명 스타일:
        - 친근하고 자연스러운 톤 사용
        - 구체적인 스타일 특징 언급
        - 평점과 리뷰 수 활용
        - 사용자 요청과의 연관성 강조
        - 이모티콘 적절히 활용
        """
    
    def recommend_products(self, 
                          user_request: Dict[str, Any], 
                          top_k: int = 5) -> List[ProductRecommendation]:
        """상품 추천 수행 (PostgreSQL 기반)"""
        filters = user_request.get('filters', {})
        user_preferences = user_request.get('user_preferences', {})
        query = user_request.get('original_query', '')
        user_id = user_request.get('user_id', 'anonymous')

        print("🔍 PostgreSQL 기반 추천 시작")
        
        # 1. 검색 방식 결정
        if self._should_use_fulltext_search(query):
            print("🔍 풀텍스트 검색 실행")
            sql_results = self.pg_manager.search_products_fulltext(
                search_query=query,
                limit=top_k * 3
            )
        else:
            print("🔍 SQL 기반 검색 실행")
            sql_results = self.pg_manager.search_products_sql(
                filters=filters,
                user_preferences=user_preferences,
                limit=top_k * 3
            )
        
        if not sql_results:
            print("⚠️ 검색 결과가 없습니다. 필터를 완화합니다.")
            # 필터 완화
            relaxed_filters = self._relax_filters(filters)
            sql_results = self.pg_manager.search_products_sql(
                filters=relaxed_filters,
                user_preferences=user_preferences,
                limit=top_k * 3
            )
        
        # 2. 스코어링 및 정렬
        scored_products = self._score_products(sql_results, user_preferences, query)
        
        # 3. 추천 결과 생성
        recommendations = []
        for product in scored_products[:top_k]:
            reason = self._generate_recommendation_reason(product, user_request)
            
            # 대표 리뷰 추출
            representative_review = self._get_representative_review(product['product_id'])
            
            recommendation = ProductRecommendation(
                product_id=str(product['product_id']),
                product_name=str(product['product_name']),
                category=str(product['category']),
                style_keywords=product.get('style_keywords', []),
                rating=safe_float(product.get('rating', 0.0)),
                review_count=safe_int(product.get('review_count', 0)),
                description=str(product['product_name']),
                recommendation_reason=str(reason),
                confidence_score=safe_float(product.get('confidence_score', 0.0)),
                price=str(product.get('price', '가격 정보 없음')),
                url=str(product.get('url', '')),
                image_url=str(product.get('image_url', '')),
                representative_review=representative_review
            )
            recommendations.append(recommendation)
            
            # 추천 히스토리 저장
            self.pg_manager.save_recommendation_history(
                user_id=user_id,
                product_id=product['product_id'],
                recommendation_reason=reason,
                confidence_score=product.get('confidence_score', 0.0)
            )
        
        self._save_recommendation_history(user_request, recommendations)
        print(f"✅ PostgreSQL 기반 추천 완료: {len(recommendations)}개 상품")
        
        return recommendations
    
    def _should_use_fulltext_search(self, query: str) -> bool:
        """풀텍스트 검색 사용 여부 결정"""
        if not query or len(query.strip()) < 3:
            return False
        
        # 명확한 키워드가 있는 경우 풀텍스트 검색 사용
        keywords = ['베이직', '스트릿', '꾸안꾸', '트렌디', '캐주얼', '오버핏', '크롭']
        return any(keyword in query for keyword in keywords)
    
    def _relax_filters(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """필터 완화 (결과가 없을 때)"""
        relaxed_filters = filters.copy()
        
        # 스타일 필터 제거
        if 'tags' in relaxed_filters:
            del relaxed_filters['tags']
        
        # 색상 필터 제거
        if 'color' in relaxed_filters:
            del relaxed_filters['color']
        
        # 가격대 필터 제거
        if 'price_range' in relaxed_filters:
            del relaxed_filters['price_range']
        
        # 사이즈 필터 제거
        for size_field in ['length', 'chest', 'shoulder']:
            if size_field in relaxed_filters:
                del relaxed_filters[size_field]
        
        return relaxed_filters
    
    def _score_products(self, 
                       products: List[Dict[str, Any]], 
                       user_preferences: Dict[str, Any],
                       query: str = "") -> List[Dict[str, Any]]:
        """상품 스코어링 (PostgreSQL 특화)"""
        scored_products = []
        
        for product in products:
            # 기본 점수 계산
            base_score = product.get('base_score', 0.0)
            
            # 검색 순위 점수 (풀텍스트 검색 결과인 경우)
            search_rank_score = product.get('search_rank', 0.0) * 0.5
            
            # 사용자 선호도 점수
            preference_score = 0.0
            
            # 스타일 선호도
            if 'tags' in user_preferences:
                user_styles = user_preferences['tags']
                product_styles = product.get('style_keywords', [])
                
                for user_style in user_styles:
                    if user_style in product_styles:
                        preference_score += 0.3
            
            # 카테고리 선호도
            if 'categories' in user_preferences:
                user_categories = user_preferences['categories']
                product_category = product.get('category', '')
                
                for user_category in user_categories:
                    if user_category.lower() in product_category.lower():
                        preference_score += 0.2
            
            # 색상 선호도
            if 'color' in user_preferences:
                user_colors = user_preferences['color']
                product_name = product.get('product_name', '')
                
                for user_color in user_colors:
                    if user_color.lower() in product_name.lower():
                        preference_score += 0.1
            
            # 쿼리 매칭 점수
            query_score = 0.0
            if query:
                query_lower = query.lower()
                product_name = product.get('product_name', '').lower()
                
                # 정확 매칭
                if query_lower in product_name:
                    query_score += 0.5
                
                # 키워드 매칭
                for word in query_lower.split():
                    if word in product_name and len(word) > 2:
                        query_score += 0.1
            
            # 최종 점수 계산
            confidence_score = (
                base_score + 
                search_rank_score + 
                preference_score + 
                query_score
            )
            
            product['confidence_score'] = confidence_score
            scored_products.append(product)
        
        # 점수로 정렬
        scored_products.sort(key=lambda x: x['confidence_score'], reverse=True)
        
        return scored_products
    
    def _generate_recommendation_reason(self, 
                                      product: Dict[str, Any], 
                                      user_request: Dict[str, Any]) -> str:
        """추천 이유 생성"""
        product_name = product.get('product_name', '')
        category = product.get('category', '')
        style_keywords = product.get('style_keywords', [])
        rating = product.get('rating', 0.0)
        review_count = product.get('review_count', 0)
        
        reasons = []
        
        # 스타일 관련 이유
        if style_keywords:
            style_text = ', '.join(style_keywords[:2])  # 상위 2개만
            reasons.append(f"{style_text} 스타일")
        
        # 평점 관련 이유
        if rating >= 4.8:
            reasons.append("매우 높은 평점")
        elif rating >= 4.5:
            reasons.append("높은 평점")
        
        # 리뷰 수 관련 이유
        if review_count >= 1000:
            reasons.append("많은 리뷰")
        elif review_count >= 100:
            reasons.append("적당한 리뷰")
        
        # 카테고리 관련 이유
        if category:
            reasons.append(f"{category} 카테고리")
        
        # 사용자 요청과의 연관성
        original_query = user_request.get('original_query', '').lower()
        if original_query and any(word in product_name.lower() for word in original_query.split()):
            reasons.append("요청과 일치")
        
        # 추천 이유 조합
        if reasons:
            reason_text = ', '.join(reasons)
            return f"{reason_text}의 상품이에요! {rating:.1f}점의 높은 평점을 받았답니다 😊 리뷰도 {review_count}개나 있어요!"
        else:
            return f"{category} 카테고리의 상품이에요! {rating:.1f}점의 평점을 받았답니다 😊"
    
    def _get_representative_review(self, product_id: str) -> Optional[str]:
        """대표 리뷰 추출"""
        try:
            reviews = self.pg_manager.get_reviews_by_product_id(product_id)
            if reviews:
                # 가장 도움이 많이 된 리뷰 반환
                best_review = max(reviews, key=lambda x: x.get('helpful_count', 0))
                return best_review.get('content', '')[:100] + "..."  # 100자로 제한
            return None
        except Exception as e:
            print(f"대표 리뷰 추출 실패: {e}")
            return None
    
    def _save_recommendation_history(self, 
                                   user_request: Dict[str, Any], 
                                   recommendations: List[ProductRecommendation]):
        """추천 히스토리 저장"""
        history_entry = {
            'timestamp': pd.Timestamp.now().isoformat(),
            'user_request': user_request,
            'recommendations_count': len(recommendations),
            'recommendations': [
                {
                    'product_id': rec.product_id,
                    'product_name': rec.product_name,
                    'confidence_score': rec.confidence_score
                }
                for rec in recommendations
            ]
        }
        
        self.recommendation_history.append(history_entry)
    
    def get_recommendation_summary(self) -> Dict[str, Any]:
        """추천 요약 정보"""
        if not self.recommendation_history:
            return {
                'total_recommendations': 0,
                'recent_recommendations': 0,
                'most_recommended_products': []
            }
        
        # 최근 추천 수
        recent_count = len([h for h in self.recommendation_history 
                          if pd.Timestamp.now() - pd.Timestamp(h['timestamp']) < pd.Timedelta(hours=1)])
        
        # 가장 많이 추천된 상품
        product_counts = {}
        for history in self.recommendation_history:
            for rec in history['recommendations']:
                product_id = rec['product_id']
                product_counts[product_id] = product_counts.get(product_id, 0) + 1
        
        most_recommended = sorted(product_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        
        return {
            'total_recommendations': sum(len(h['recommendations']) for h in self.recommendation_history),
            'recent_recommendations': recent_count,
            'most_recommended_products': [
                {'product_id': pid, 'count': count} for pid, count in most_recommended
            ]
        }
    
    def update_user_feedback(self, 
                           product_id: str, 
                           feedback_type: str, 
                           feedback_value: float):
        """사용자 피드백 반영"""
        # 사용자 선호도 업데이트
        if feedback_type == 'like':
            # 좋아하는 스타일/카테고리 등록
            product = self.pg_manager.get_product_by_id(product_id)
            if product:
                style_keywords = product.get('style_keywords', [])
                category = product.get('category', '')
                
                # 스타일 선호도 저장
                for style in style_keywords:
                    self.pg_manager.save_user_preference(
                        user_id='anonymous',  # 실제로는 사용자 ID 사용
                        preference_type='tags',
                        preference_value=style,
                        weight=feedback_value
                    )
                
                # 카테고리 선호도 저장
                if category:
                    self.pg_manager.save_user_preference(
                        user_id='anonymous',
                        preference_type='categories',
                        preference_value=category,
                        weight=feedback_value
                    )
        
        print(f"피드백 반영 완료: {product_id} - {feedback_type}")
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """성능 메트릭 조회"""
        try:
            # 데이터베이스 통계
            db_stats = self.pg_manager.get_statistics()
            
            # 성능 메트릭
            perf_metrics = self.pg_manager.get_performance_metrics()
            
            return {
                'database_stats': db_stats,
                'performance_metrics': perf_metrics
            }
        except Exception as e:
            print(f"성능 메트릭 조회 실패: {e}")
            return {}
    
    def close(self):
        """리소스 정리"""
        # PostgreSQL 연결은 컨텍스트 매니저로 자동 관리됨
        pass


def main():
    """PostgreSQL 추천 에이전트 테스트"""
    # 테스트 데이터 생성
    test_data = {
        'product_id': ['1', '2', '3', '4', '5'],
        'product_name': [
            '베이직 오버핏 티셔츠 블랙',
            '스트릿 그래픽 반팔 화이트',
            '꾸안꾸 무지 티셔츠 그레이',
            '트렌디 로고 반팔 네이비',
            '빈티지 체크 셔츠 베이지'
        ],
        'categories': ['상의', '상의', '상의', '상의', '상의'],
        'tags': [
            ['베이직', '오버핏'],
            ['스트릿', '그래픽'],
            ['베이직', '무지', '꾸안꾸'],
            ['트렌디', '로고'],
            ['빈티지', '체크']
        ],
        'rating': [4.8, 4.6, 4.9, 4.7, 4.5],
        'review_count': [1500, 800, 2200, 1200, 600],
        'price': [29000, 35000, 25000, 32000, 45000],
        'url': [
            'https://musinsa.com/1',
            'https://musinsa.com/2',
            'https://musinsa.com/3',
            'https://musinsa.com/4',
            'https://musinsa.com/5'
        ]
    }
    
    df = pd.DataFrame(test_data)
    
    try:
        # PostgreSQL 매니저로 데이터 삽입
        pg_manager = PostgreSQLManager(
            host="localhost",
            database="fashion_recommendation",
            user="postgres",
            password="password"
        )
        pg_manager.insert_products_from_dataframe(df)
        
        # PostgreSQL 추천 에이전트 테스트
        agent = PostgreSQLRecommendationAgent(
            host="localhost",
            database="fashion_recommendation",
            user="postgres",
            password="password"
        )
        
        # 테스트 요청
        user_request = {
            'original_query': '베이직 스타일의 상의 추천해줘',
            'filters': {
                'categories': '상의',
                'tags': '베이직'
            },
            'user_preferences': {
                'tags': ['베이직'],
                'categories': ['상의']
            },
            'user_id': 'test_user'
        }
        
        recommendations = agent.recommend_products(user_request, top_k=3)
        
        print("PostgreSQL 기반 추천 결과:")
        for i, rec in enumerate(recommendations, 1):
            print(f"\n{i}. {rec.product_name}")
            print(f"   평점: {rec.rating}, 리뷰: {rec.review_count}")
            print(f"   스타일: {rec.style_keywords}")
            print(f"   추천 이유: {rec.recommendation_reason}")
        
        # 요약 정보
        summary = agent.get_recommendation_summary()
        print(f"\n추천 요약: {summary}")
        
        # 성능 메트릭
        metrics = agent.get_performance_metrics()
        print(f"\n성능 메트릭: {metrics}")
        
    except Exception as e:
        print(f"PostgreSQL 연결 실패: {e}")
        print("PostgreSQL 서버가 실행 중이고 연결 정보가 올바른지 확인하세요.")


if __name__ == "__main__":
    main() 