"""
PostgreSQL 기반 추천 에이전트 (정규화된 구조 반영)
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
from datetime import datetime

# 프로젝트 루트 경로 추가
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from database.postgresql_manager_updated import PostgreSQLManagerUpdated

@dataclass
class ProductRecommendation:
    """상품 추천 데이터 클래스"""
    product_id: str
    product_name: str
    category: str
    brand_kr: str
    brand_en: str
    style_keywords: List[str]
    avg_rating: float
    review_count: int
    description: str
    recommendation_reason: str
    confidence_score: float
    price: Optional[str] = None
    url: str = ''
    image_url: str = ''
    representative_review: Optional[str] = None
    size_count: int = 0

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

class PostgreSQLRecommendationAgentUpdated:
    """PostgreSQL 기반 추천 에이전트 (정규화된 구조)"""
    
    def __init__(self, 
                 host: str = "localhost",
                 port: int = 5432,
                 database: str = "fashion_recommendation",
                 user: str = "postgres",
                 password: str = "postgres"):
        
        self.pg_manager = PostgreSQLManagerUpdated(
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
        - 브랜드 인기도 반영
        - 사용자 요청과의 연관성 강조
        - 이모티콘 적절히 활용
        """
    
    def recommend_products(self, 
                          user_request: Dict[str, Any], 
                          top_k: int = 5) -> List[ProductRecommendation]:
        """상품 추천 수행 (확장성 있는 검색 전략)"""
        filters = user_request.get('filters', {})
        user_preferences = user_request.get('user_preferences', {})
        query = user_request.get('original_query', '')
        user_id = user_request.get('user_id', 'anonymous')

        print("🔍 확장성 있는 PostgreSQL 기반 추천 시작")
        
        # 1. 다단계 검색 전략 실행
        sql_results = self._multi_stage_search(query, filters, user_preferences, top_k)
        
        if not sql_results:
            print("⚠️ 모든 검색 전략에서 결과가 없습니다.")
            return []
        
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
                brand_kr=str(product.get('brand_kr', '')),
                brand_en=str(product.get('brand_en', '')),
                style_keywords=product.get('style_keywords', []),
                avg_rating=safe_float(product.get('avg_rating', 0.0)),
                review_count=safe_int(product.get('review_count', 0)),
                description=str(product['product_name']),
                recommendation_reason=str(reason),
                confidence_score=safe_float(product.get('confidence_score', 0.0)),
                price=str(product.get('price', '가격 정보 없음')),
                url=str(product.get('product_url', '')),
                image_url=str(product.get('image_url', '')),
                representative_review=representative_review,
                size_count=safe_int(product.get('size_count', 0))
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
        print(f"✅ 확장성 있는 PostgreSQL 기반 추천 완료: {len(recommendations)}개 상품")
        
        return recommendations
    
    def _multi_stage_search(self, 
                           query: str, 
                           filters: Dict[str, Any], 
                           user_preferences: Dict[str, Any],
                           top_k: int) -> List[Dict[str, Any]]:
        """다단계 검색 전략 (벡터DB vs SQL 검색 선택)"""
        search_results = []
        
        # 검색 전략 결정
        search_strategy = self._determine_search_strategy(query, filters, user_preferences)
        print(f"🎯 선택된 검색 전략: {search_strategy}")
        
        # 1단계: 선택된 전략으로 검색
        print("🔍 1단계: 주요 검색 전략 실행")
        if search_strategy == "vector":
            results = self._vector_search(query, filters, user_preferences, top_k * 2)
        elif search_strategy == "hybrid":
            results = self._hybrid_search(query, filters, user_preferences, top_k * 2)
        else:  # sql
            results = self._sql_search(query, filters, user_preferences, top_k * 2)
        
        if results:
            search_results.extend(results)
            print(f"✅ 1단계 결과: {len(results)}개")
        
        # 2단계: 보완 검색 (다른 전략으로)
        if len(search_results) < top_k:
            print("🔍 2단계: 보완 검색 전략 실행")
            if search_strategy == "vector":
                # 벡터 검색 후 SQL 검색으로 보완
                results = self._sql_search(query, filters, user_preferences, top_k * 2)
            elif search_strategy == "sql":
                # SQL 검색 후 벡터 검색으로 보완
                results = self._vector_search(query, filters, user_preferences, top_k * 2)
            else:  # hybrid
                # 하이브리드 후 SQL 검색으로 보완
                results = self._sql_search(query, filters, user_preferences, top_k * 2)
            
            if results:
                search_results.extend(results)
                print(f"✅ 2단계 결과: {len(results)}개")
        
        # 3단계: 필터 완화 (스타일 키워드 제거)
        if len(search_results) < top_k:
            print("🔍 3단계: 스타일 키워드 필터 완화")
            relaxed_filters = self._relax_style_filters(filters)
            results = self.pg_manager.search_products_sql(
                filters=relaxed_filters,
                user_preferences=user_preferences,
                limit=top_k * 2
            )
            if results:
                search_results.extend(results)
                print(f"✅ 3단계 결과: {len(results)}개")
        
        # 4단계: 브랜드 필터 완화
        if len(search_results) < top_k:
            print("🔍 4단계: 브랜드 필터 완화")
            relaxed_filters = self._relax_brand_filters(filters)
            results = self.pg_manager.search_products_sql(
                filters=relaxed_filters,
                user_preferences=user_preferences,
                limit=top_k * 2
            )
            if results:
                search_results.extend(results)
                print(f"✅ 4단계 결과: {len(results)}개")
        
        # 5단계: 가격대 필터 완화
        if len(search_results) < top_k:
            print("🔍 5단계: 가격대 필터 완화")
            relaxed_filters = self._relax_price_filters(filters)
            results = self.pg_manager.search_products_sql(
                filters=relaxed_filters,
                user_preferences=user_preferences,
                limit=top_k * 2
            )
            if results:
                search_results.extend(results)
                print(f"✅ 5단계 결과: {len(results)}개")
        
        # 6단계: 카테고리 기반 추천
        if len(search_results) < top_k:
            print("🔍 6단계: 카테고리 기반 추천")
            category = filters.get('category')
            if category:
                category_filters = {'category': category}
                results = self.pg_manager.search_products_sql(
                    filters=category_filters,
                    user_preferences={},
                    limit=top_k * 2
                )
                if results:
                    search_results.extend(results)
                    print(f"✅ 6단계 결과: {len(results)}개")
        
        # 7단계: 인기 상품 기반 추천 (평점 높은 순)
        if len(search_results) < top_k:
            print("🔍 7단계: 인기 상품 기반 추천")
            popular_filters = {'min_rating': 4.0, 'min_reviews': 10}
            results = self.pg_manager.search_products_sql(
                filters=popular_filters,
                user_preferences={},
                limit=top_k * 2
            )
            if results:
                search_results.extend(results)
                print(f"✅ 7단계 결과: {len(results)}개")
        
        # 중복 제거 및 정렬
        unique_results = self._remove_duplicates(search_results)
        print(f"📊 총 검색 결과: {len(unique_results)}개 (중복 제거 후)")
        
        return unique_results
    
    def _determine_search_strategy(self, query: str, filters: Dict[str, Any], user_preferences: Dict[str, Any]) -> str:
        """검색 전략 결정 (벡터DB vs SQL)"""
        
        # 1. 자연어 쿼리 특성 분석
        natural_language_indicators = [
            '같은', '비슷한', '이런', '저런', '스타일', '느낌', '분위기',
            '어떤', '추천', '좋은', '인기', '트렌디', '꾸안꾸', '베이직'
        ]
        
        # 2. 구체적 필터 존재 여부
        has_specific_filters = bool(
            filters.get('category') or 
            filters.get('brand_kr') or 
            filters.get('brand_en') or
            filters.get('price_min') or 
            filters.get('price_max') or
            filters.get('size_name')
        )
        
        # 3. 스타일 키워드 존재 여부
        has_style_keywords = bool(filters.get('style_keywords'))
        
        # 4. 자연어 쿼리 길이
        query_length = len(query.strip()) if query else 0
        
        # 전략 결정 로직
        if query_length > 10 and any(indicator in query for indicator in natural_language_indicators):
            if has_specific_filters:
                return "hybrid"  # 자연어 + 구체적 필터 = 하이브리드
            else:
                return "vector"  # 자연어만 = 벡터 검색
        elif has_specific_filters or has_style_keywords:
            return "sql"  # 구체적 필터 = SQL 검색
        elif query_length > 5:
            return "hybrid"  # 중간 길이 쿼리 = 하이브리드
        else:
            return "sql"  # 기본값 = SQL 검색
    
    def _vector_search(self, query: str, filters: Dict[str, Any], user_preferences: Dict[str, Any], limit: int) -> List[Dict[str, Any]]:
        """벡터DB 검색 (풀텍스트 검색으로 대체)"""
        try:
            # 현재는 풀텍스트 검색으로 벡터 검색 시뮬레이션
            return self.pg_manager.search_products_fulltext(query, limit)
        except Exception as e:
            print(f"⚠️ 벡터 검색 실패: {e}")
            return []
    
    def _sql_search(self, query: str, filters: Dict[str, Any], user_preferences: Dict[str, Any], limit: int) -> List[Dict[str, Any]]:
        """SQL 검색"""
        return self.pg_manager.search_products_sql(filters, user_preferences, limit)
    
    def _hybrid_search(self, query: str, filters: Dict[str, Any], user_preferences: Dict[str, Any], limit: int) -> List[Dict[str, Any]]:
        """하이브리드 검색 (벡터 + SQL)"""
        results = []
        
        # 벡터 검색 결과
        vector_results = self._vector_search(query, {}, {}, limit // 2)
        if vector_results:
            results.extend(vector_results)
        
        # SQL 검색 결과
        sql_results = self._sql_search(query, filters, user_preferences, limit // 2)
        if sql_results:
            results.extend(sql_results)
        
        return results
    
    def _relax_style_filters(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """스타일 키워드 필터 완화"""
        relaxed_filters = filters.copy()
        if 'style_keywords' in relaxed_filters:
            del relaxed_filters['style_keywords']
        return relaxed_filters
    
    def _relax_brand_filters(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """브랜드 필터 완화"""
        relaxed_filters = filters.copy()
        if 'brand_en' in relaxed_filters:
            del relaxed_filters['brand_en']
        if 'brand_kr' in relaxed_filters:
            del relaxed_filters['brand_kr']
        return relaxed_filters
    
    def _relax_price_filters(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """가격대 필터 완화"""
        relaxed_filters = filters.copy()
        if 'price_min' in relaxed_filters:
            del relaxed_filters['price_min']
        if 'price_max' in relaxed_filters:
            del relaxed_filters['price_max']
        return relaxed_filters
    
    def _remove_duplicates(self, products: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """중복 제거"""
        seen = set()
        unique_products = []
        
        for product in products:
            product_id = str(product.get('product_id', ''))
            if product_id not in seen:
                seen.add(product_id)
                unique_products.append(product)
        
        return unique_products
    
    def _should_use_fulltext_search(self, query: str) -> bool:
        """풀텍스트 검색 사용 여부 결정"""
        if not query or len(query.strip()) < 3:
            return False
        
        # 명확한 키워드가 있는 경우 풀텍스트 검색 사용
        keywords = ['베이직', '스트릿', '꾸안꾸', '트렌디', '캐주얼', '오버핏', '크롭', '반팔', '티셔츠', '가방']
        return any(keyword in query for keyword in keywords)
    
    def _score_products(self, 
                       products: List[Dict[str, Any]], 
                       user_preferences: Dict[str, Any],
                       query: str = "") -> List[Dict[str, Any]]:
        """상품 스코어링 (정규화된 구조 반영)"""
        scored_products = []
        
        for product in products:
            score = 0.0
            
            # 1. 기본 신뢰도 점수 (이미 계산됨)
            score += safe_float(product.get('confidence_score', 0.0)) * 0.4
            
            # 2. 리뷰 수 점수
            review_count = safe_int(product.get('review_count', 0))
            score += min(review_count / 100.0, 1.0) * 0.15
            
            # 3. 평점 점수
            avg_rating = safe_float(product.get('avg_rating', 0.0))
            score += (avg_rating / 5.0) * 0.15
            
            # 4. 사이즈 다양성 점수
            size_count = safe_int(product.get('size_count', 0))
            score += min(size_count / 10.0, 1.0) * 0.1
            
            # 5. 사용자 선호도 매칭 점수
            if user_preferences:
                preference_score = self._calculate_preference_score(product, user_preferences)
                score += preference_score * 0.1
            
            product['confidence_score'] = score
            scored_products.append(product)
        
        # 점수 기준으로 정렬
        scored_products.sort(key=lambda x: x.get('confidence_score', 0), reverse=True)
        
        return scored_products
    
    def _calculate_preference_score(self, product: Dict[str, Any], user_preferences: Dict[str, Any]) -> float:
        """사용자 선호도 매칭 점수 계산"""
        score = 0.0
        
        # 브랜드 선호도
        if 'preferred_brands' in user_preferences:
            preferred_brands = user_preferences['preferred_brands']
            if product.get('brand_kr') in preferred_brands or product.get('brand_en') in preferred_brands:
                score += 0.5
        
        # 카테고리 선호도
        if 'preferred_categories' in user_preferences:
            preferred_categories = user_preferences['preferred_categories']
            if product.get('category') in preferred_categories:
                score += 0.3
        
        # 가격대 선호도
        if 'preferred_price_range' in user_preferences:
            price_range = user_preferences['preferred_price_range']
            product_price = safe_int(product.get('price', 0))
            if price_range[0] <= product_price <= price_range[1]:
                score += 0.2
        
        return score
    
    def _generate_recommendation_reason(self, 
                                      product: Dict[str, Any], 
                                      user_request: Dict[str, Any]) -> str:
        """추천 이유 생성 (정규화된 구조 반영)"""
        reasons = []
        
        # 평점 기반
        avg_rating = safe_float(product.get('avg_rating', 0.0))
        review_count = safe_int(product.get('review_count', 0))
        if avg_rating >= 4.8 and review_count >= 100:
            reasons.append("🌟 매우 높은 평점과 많은 리뷰")
        elif avg_rating >= 4.5 and review_count >= 50:
            reasons.append("⭐ 높은 평점과 좋은 리뷰")
        
        # 사이즈 다양성
        size_count = safe_int(product.get('size_count', 0))
        if size_count >= 6:
            reasons.append("📏 다양한 사이즈 옵션")
        
        # 스타일 키워드 매칭
        style_keywords = product.get('style_keywords', [])
        if style_keywords and isinstance(style_keywords, list):
            keyword_str = ', '.join(style_keywords[:3])
            reasons.append(f"🏷️ {keyword_str} 스타일")
        
        # 사용자 요청과의 매칭
        query = user_request.get('original_query', '')
        if query and any(keyword in query for keyword in ['베이직', '기본']):
            if '베이직' in str(style_keywords):
                reasons.append("✨ 베이직한 디자인으로 활용도 높음")
        
        if not reasons:
            reasons.append("💫 추천 상품")
        
        return ' | '.join(reasons)
    
    def _get_representative_review(self, product_id: str) -> Optional[str]:
        """대표 리뷰 추출"""
        try:
            reviews = self.pg_manager.get_reviews_by_product_id(product_id)
            if reviews:
                # 좋아요 수가 많은 리뷰를 우선 선택
                reviews.sort(key=lambda x: safe_int(x.get('likes', 0)), reverse=True)
                return reviews[0].get('content', '')[:100] + '...'
            return None
        except Exception:
            return None
    
    def _save_recommendation_history(self, 
                                   user_request: Dict[str, Any], 
                                   recommendations: List[ProductRecommendation]):
        """추천 히스토리 저장"""
        history_entry = {
            'timestamp': datetime.now().isoformat(),
            'user_request': user_request,
            'recommendations': [
                {
                    'product_id': rec.product_id,
                    'product_name': rec.product_name,
                    'confidence_score': rec.confidence_score,
                    'recommendation_reason': rec.recommendation_reason
                }
                for rec in recommendations
            ]
        }
        self.recommendation_history.append(history_entry)
    
    def get_recommendation_summary(self) -> Dict[str, Any]:
        """추천 요약 정보"""
        if not self.recommendation_history:
            return {}
        
        total_recommendations = len(self.recommendation_history)
        total_products = sum(len(entry['recommendations']) for entry in self.recommendation_history)
        
        # 카테고리별 추천 통계
        category_counts = {}
        brand_counts = {}
        
        for entry in self.recommendation_history:
            for rec in entry['recommendations']:
                # 카테고리 카운트 (실제로는 product_id로 조회 필요)
                category_counts[rec.get('category', 'unknown')] = category_counts.get(rec.get('category', 'unknown'), 0) + 1
        
        return {
            'total_recommendations': total_recommendations,
            'total_products_recommended': total_products,
            'category_distribution': category_counts,
            'brand_distribution': brand_counts
        }
    
    def update_user_feedback(self, 
                           product_id: str, 
                           feedback_type: str, 
                           feedback_value: float):
        """사용자 피드백 업데이트"""
        # 사용자 선호도 업데이트 로직
        print(f"📝 사용자 피드백 업데이트: {product_id}, {feedback_type}, {feedback_value}")
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """성능 메트릭 조회"""
        try:
            stats = self.pg_manager.get_statistics()
            brand_stats = self.pg_manager.get_brand_statistics()
            
            # brand_stats가 리스트인지 확인 후 슬라이싱
            top_brands = brand_stats[:10] if isinstance(brand_stats, list) else []
            
            return {
                'database_stats': stats,
                'top_brands': top_brands,
                'recommendation_summary': self.get_recommendation_summary()
            }
        except Exception as e:
            print(f"❌ 성능 메트릭 조회 실패: {e}")
            return {}
    
    def close(self):
        """리소스 정리"""
        print("🔒 PostgreSQL 추천 에이전트 종료")

def main():
    """테스트 함수"""
    agent = PostgreSQLRecommendationAgentUpdated()
    
    # 테스트 추천 요청
    test_request = {
        'original_query': '베이직한 반팔 티셔츠 추천해줘',
        'filters': {
            'category': '상의',
            'price_max': 50000
        },
        'user_preferences': {
            'preferred_brands': ['무신사 스탠다드', '아디다스'],
            'preferred_categories': ['상의'],
            'preferred_price_range': [10000, 50000]
        },
        'user_id': 'test_user'
    }
    
    print("🚀 추천 시스템 테스트 시작")
    recommendations = agent.recommend_products(test_request, top_k=3)
    
    print(f"\n📋 추천 결과 ({len(recommendations)}개):")
    for i, rec in enumerate(recommendations, 1):
        print(f"\n{i}. {rec.product_name}")
        print(f"   브랜드: {rec.brand_kr}")
        print(f"   평점: {rec.avg_rating:.1f} ({rec.review_count}개 리뷰)")
        print(f"   가격: {rec.price}")
        print(f"   추천 이유: {rec.recommendation_reason}")
        print(f"   신뢰도: {rec.confidence_score:.3f}")
    
    # 성능 메트릭 확인
    metrics = agent.get_performance_metrics()
    print(f"\n📊 성능 메트릭:")
    print(f"  총 상품 수: {metrics.get('database_stats', {}).get('total_products', 0)}")
    print(f"  총 브랜드 수: {metrics.get('database_stats', {}).get('total_brands', 0)}")
    print(f"  총 리뷰 수: {metrics.get('database_stats', {}).get('total_reviews', 0)}")
    
    agent.close()

if __name__ == "__main__":
    main() 