"""
고급 벡터 DB 관리 모듈
하이브리드 검색, 필터링, 스코어링 기능 추가
"""

import numpy as np
import pandas as pd
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path
import json
import time
from collections import defaultdict

try:
    import faiss
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False

from simple_vector_db import SimpleVectorDB


@dataclass
class SearchResult:
    """검색 결과 데이터 클래스"""
    product_id: str
    product_name: str
    similarity_score: float
    rating_score: float
    review_score: float
    final_score: float
    metadata: Dict[str, Any]


class AdvancedVectorDB(SimpleVectorDB):
    """고급 벡터 DB 클래스"""
    
    def __init__(self, 
                 db_path: str = "vector_db",
                 dimension: int = 128,
                 rating_weight: float = 0.3,
                 review_weight: float = 0.2,
                 similarity_weight: float = 0.5):
        super().__init__(db_path, dimension)
        self.rating_weight = rating_weight
        self.review_weight = review_weight
        self.similarity_weight = similarity_weight
        
        # 검색 통계
        self.search_stats = defaultdict(int)
        self.performance_stats = {
            'total_searches': 0,
            'avg_search_time': 0.0,
            'cache_hits': 0
        }
    
    def hybrid_search(self, 
                     query: str, 
                     top_k: int = 10,
                     filters: Optional[Dict[str, Any]] = None,
                     use_hybrid: bool = True) -> List[SearchResult]:
        """하이브리드 검색 (벡터 유사도 + 평점/리뷰 스코어링)"""
        start_time = time.time()
        
        # 벡터 검색 수행
        vector_results = self.search_similar_products(query, top_k * 2, filters)
        
        if not use_hybrid:
            # 벡터 검색만 사용
            results = []
            for result in vector_results[:top_k]:
                results.append(SearchResult(
                    product_id=result['product_id'],
                    product_name=result['product_name'],
                    similarity_score=result['similarity_score'],
                    rating_score=0.0,
                    review_score=0.0,
                    final_score=result['similarity_score'],
                    metadata=result['metadata']
                ))
        else:
            # 하이브리드 스코어링
            results = []
            for result in vector_results:
                metadata = result['metadata']
                
                # 평점 스코어 (0-1 정규화)
                rating = metadata.get('rating', 0.0)
                rating_score = min(rating / 5.0, 1.0)
                
                # 리뷰 수 스코어 (로그 스케일 정규화)
                review_count = metadata.get('review_count', 0)
                review_score = min(np.log1p(review_count) / 10.0, 1.0)
                
                # 최종 스코어 계산
                final_score = (
                    self.similarity_weight * result['similarity_score'] +
                    self.rating_weight * rating_score +
                    self.review_weight * review_score
                )
                
                results.append(SearchResult(
                    product_id=result['product_id'],
                    product_name=result['product_name'],
                    similarity_score=result['similarity_score'],
                    rating_score=rating_score,
                    review_score=review_score,
                    final_score=final_score,
                    metadata=metadata
                ))
            
            # 최종 스코어로 정렬
            results.sort(key=lambda x: x.final_score, reverse=True)
            results = results[:top_k]
        
        # 성능 통계 업데이트
        search_time = time.time() - start_time
        self.performance_stats['total_searches'] += 1
        self.performance_stats['avg_search_time'] = (
            (self.performance_stats['avg_search_time'] * (self.performance_stats['total_searches'] - 1) + search_time) /
            self.performance_stats['total_searches']
        )
        
        return results
    
    def search_by_category(self, 
                          category: str, 
                          top_k: int = 10,
                          min_rating: float = 4.0) -> List[SearchResult]:
        """카테고리별 검색"""
        filters = {
            'category': category,
            'min_rating': min_rating
        }
        
        # 카테고리 내에서 평점 높은 상품 검색
        results = []
        for i, metadata in enumerate(self.metadata):
            if (category.lower() in str(metadata.get('category', '')).lower() and
                metadata.get('rating', 0) >= min_rating):
                
                rating_score = min(metadata.get('rating', 0) / 5.0, 1.0)
                review_count = metadata.get('review_count', 0)
                review_score = min(np.log1p(review_count) / 10.0, 1.0)
                
                results.append(SearchResult(
                    product_id=self.product_ids[i],
                    product_name=metadata.get('product_name', ''),
                    similarity_score=0.0,
                    rating_score=rating_score,
                    review_score=review_score,
                    final_score=rating_score * 0.6 + review_score * 0.4,
                    metadata=metadata
                ))
        
        results.sort(key=lambda x: x.final_score, reverse=True)
        return results[:top_k]
    
    def search_trending_products(self, 
                                top_k: int = 10,
                                category: Optional[str] = None) -> List[SearchResult]:
        """트렌딩 상품 검색 (평점 + 리뷰 수 기준)"""
        results = []
        
        for i, metadata in enumerate(self.metadata):
            # 카테고리 필터 적용
            if category and category.lower() not in str(metadata.get('category', '')).lower():
                continue
            
            rating = metadata.get('rating', 0)
            review_count = metadata.get('review_count', 0)
            
            # 트렌딩 스코어 계산 (평점 * log(리뷰수))
            trending_score = rating * np.log1p(review_count) / 10.0
            
            results.append(SearchResult(
                product_id=self.product_ids[i],
                product_name=metadata.get('product_name', ''),
                similarity_score=0.0,
                rating_score=min(rating / 5.0, 1.0),
                review_score=min(np.log1p(review_count) / 10.0, 1.0),
                final_score=trending_score,
                metadata=metadata
            ))
        
        results.sort(key=lambda x: x.final_score, reverse=True)
        return results[:top_k]
    
    def get_search_recommendations(self, 
                                 user_query: str,
                                 top_k: int = 5) -> List[str]:
        """검색어 추천 (인기 검색어 기반)"""
        # 간단한 검색어 추천 로직
        popular_keywords = [
            '베이직', '오버핏', '스트릿', '꾸안꾸', '트렌디',
            '반팔', '티셔츠', '셔츠', '맨투맨', '후드'
        ]
        
        recommendations = []
        query_lower = user_query.lower()
        
        for keyword in popular_keywords:
            if keyword not in query_lower:
                recommendations.append(f"{user_query} {keyword}")
        
        return recommendations[:top_k]
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """성능 통계 반환"""
        stats = super().get_statistics()
        stats.update(self.performance_stats)
        return stats


def main():
    """고급 벡터 DB 테스트"""
    print("=== 고급 벡터 DB 테스트 ===")
    
    # 샘플 데이터 생성
    sample_data = {
        'product_id': ['1', '2', '3', '4', '5'],
        'product_name': [
            '베이직 오버핏 티셔츠',
            '스트릿 그래픽 반팔',
            '꾸안꾸 무지 티셔츠',
            '트렌디 로고 반팔',
            '빈티지 체크 셔츠'
        ],
        'description': [
            '베이직 오버핏 티셔츠 블랙',
            '스트릿 그래픽 반팔 화이트',
            '꾸안꾸 무지 티셔츠 그레이',
            '트렌디 로고 반팔 네이비',
            '빈티지 체크 셔츠 베이지'
        ],
        'style_keywords': [
            ['베이직', '오버핏'],
            ['스트릿', '그래픽'],
            ['베이직', '무지', '꾸안꾸'],
            ['트렌디', '로고'],
            ['빈티지', '체크']
        ],
        'rating': [4.8, 4.6, 4.9, 4.7, 4.5],
        'review_count': [1500, 800, 2200, 1200, 600],
        'category': ['상의', '상의', '상의', '상의', '상의']
    }
    
    df = pd.DataFrame(sample_data)
    
    # 고급 벡터 DB 초기화
    vector_db = AdvancedVectorDB()
    vector_db.add_products(df)
    
    # 하이브리드 검색 테스트
    print("\n=== 하이브리드 검색 테스트 ===")
    query = "꾸안꾸 느낌 나는 반팔"
    results = vector_db.hybrid_search(query, top_k=3, use_hybrid=True)
    
    for i, result in enumerate(results, 1):
        print(f"{i}. {result.product_name}")
        print(f"   유사도: {result.similarity_score:.3f}")
        print(f"   평점 스코어: {result.rating_score:.3f}")
        print(f"   리뷰 스코어: {result.review_score:.3f}")
        print(f"   최종 스코어: {result.final_score:.3f}")
        print()
    
    # 트렌딩 상품 검색 테스트
    print("=== 트렌딩 상품 검색 ===")
    trending_results = vector_db.search_trending_products(top_k=3)
    
    for i, result in enumerate(trending_results, 1):
        print(f"{i}. {result.product_name}")
        print(f"   트렌딩 스코어: {result.final_score:.3f}")
        print(f"   평점: {result.metadata.get('rating', 'N/A')}")
        print(f"   리뷰 수: {result.metadata.get('review_count', 'N/A')}")
        print()
    
    # 검색어 추천 테스트
    print("=== 검색어 추천 ===")
    recommendations = vector_db.get_search_recommendations("베이직")
    for rec in recommendations:
        print(f"- {rec}")
    
    # 성능 통계
    stats = vector_db.get_performance_stats()
    print(f"\n=== 성능 통계 ===")
    for key, value in stats.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main() 