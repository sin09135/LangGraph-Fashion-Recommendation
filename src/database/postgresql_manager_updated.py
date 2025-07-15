"""
PostgreSQL 기반 데이터베이스 관리자 (정규화된 구조 반영)
고성능 관계형 데이터베이스 시스템
"""

import psycopg2
import psycopg2.extras
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple
import json
import os
from datetime import datetime
import logging
from contextlib import contextmanager

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PostgreSQLManagerUpdated:
    """PostgreSQL 기반 데이터베이스 관리자 (정규화된 구조)"""
    
    def __init__(self, 
                 host: str = "localhost",
                 port: int = 5432,
                 database: str = "fashion_recommendation",
                 user: str = "postgres",
                 password: str = "postgres"):
        
        self.connection_params = {
            'host': host,
            'port': port,
            'database': database,
            'user': user,
            'password': password
        }
        
        logger.info("PostgreSQL 매니저 초기화 완료 (정규화된 구조)")
    
    @contextmanager
    def get_connection(self):
        """데이터베이스 연결 컨텍스트 매니저"""
        conn = None
        try:
            conn = psycopg2.connect(**self.connection_params)
            yield conn
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"데이터베이스 연결 오류: {e}")
            raise
        finally:
            if conn:
                conn.close()
    
    def search_products_sql(self, 
                           filters: Dict[str, Any], 
                           user_preferences: Dict[str, Any] = None,
                           limit: int = 10) -> List[Dict[str, Any]]:
        """정규화된 구조 기반 상품 검색"""
        
        # 기본 쿼리 구성 (정규화된 테이블 구조 반영)
        query = """
            SELECT DISTINCT 
                p.product_id,
                p.product_name,
                p.category,
                p.brand_id,
                b.brand_en,
                b.brand_kr,
                b.brand_popularity,
                p.price,
                p.original_price,
                p.discount_rate,
                p.product_url,
                p.image_url,
                p.image_path,
                p.tags,
                -- 리뷰 통계
                COALESCE(AVG(pr.rating), 0) as avg_rating,
                COUNT(DISTINCT pr.id) as review_count,
                -- 스타일 키워드
                ARRAY_AGG(DISTINCT psk.keyword) FILTER (WHERE psk.keyword IS NOT NULL) as style_keywords,
                -- 사이즈 정보
                COUNT(DISTINCT ps.id) as size_count,
                -- 신뢰도 점수 계산
                (COALESCE(AVG(pr.rating), 0) * LN(1 + COUNT(DISTINCT pr.id))) as confidence_score
            FROM products p
            LEFT JOIN brands b ON p.brand_id = b.brand_id
            LEFT JOIN product_reviews pr ON p.product_id = pr.product_id
            LEFT JOIN product_style_keywords psk ON p.product_id = psk.product_id
            LEFT JOIN product_sizes ps ON p.product_id = ps.product_id
        """
        
        where_conditions = []
        params = []
        param_count = 0
        
        # 필터 조건 추가
        if filters.get('category'):
            param_count += 1
            where_conditions.append(f"p.category = %s")
            params.append(filters['category'])
        
        if filters.get('brand_en'):
            param_count += 1
            where_conditions.append(f"b.brand_en ILIKE %s")
            params.append(f"%{filters['brand_en']}%")
        
        if filters.get('brand_kr'):
            param_count += 1
            where_conditions.append(f"b.brand_kr ILIKE %s")
            params.append(f"%{filters['brand_kr']}%")
        
        if filters.get('price_min'):
            param_count += 1
            where_conditions.append(f"p.price >= %s")
            params.append(filters['price_min'])
        
        if filters.get('price_max'):
            param_count += 1
            where_conditions.append(f"p.price <= %s")
            params.append(filters['price_max'])
        
        if filters.get('discount_rate_min'):
            param_count += 1
            where_conditions.append(f"p.discount_rate >= %s")
            params.append(filters['discount_rate_min'])
        
        if filters.get('rating_min'):
            param_count += 1
            where_conditions.append(f"AVG(pr.rating) >= %s")
            params.append(filters['rating_min'])
        
        if filters.get('style_keywords'):
            param_count += 1
            where_conditions.append(f"psk.keyword = ANY(%s)")
            params.append(filters['style_keywords'])
        
        if filters.get('size_name'):
            param_count += 1
            where_conditions.append(f"ps.size_name = %s")
            params.append(filters['size_name'])
        
        # WHERE 절 추가
        if where_conditions:
            query += " WHERE " + " AND ".join(where_conditions)
        
        # GROUP BY 및 ORDER BY
        query += """
            GROUP BY p.product_id, p.product_name, p.category, p.brand_id, 
                     b.brand_en, b.brand_kr, b.brand_popularity, p.price, 
                     p.original_price, p.discount_rate, p.product_url, 
                     p.image_url, p.image_path, p.tags
            ORDER BY confidence_score DESC, b.brand_popularity DESC, p.price ASC
            LIMIT %s
        """
        params.append(limit)
        
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                    cursor.execute(query, params)
                    
                    results = []
                    for row in cursor.fetchall():
                        product = dict(row)
                        # 스타일 키워드가 None이면 빈 리스트로
                        if product['style_keywords'] is None:
                            product['style_keywords'] = []
                        
                        results.append(product)
                    
                    logger.info(f"정규화된 PostgreSQL 검색 완료: {len(results)}개 결과")
                    return results
                    
        except Exception as e:
            logger.error(f"PostgreSQL 검색 실패: {e}")
            return []
    
    def search_products_fulltext(self, 
                                search_query: str, 
                                limit: int = 10) -> List[Dict[str, Any]]:
        """정규화된 구조 기반 풀텍스트 검색"""
        
        query = """
            SELECT DISTINCT 
                p.product_id,
                p.product_name,
                p.category,
                p.brand_id,
                b.brand_en,
                b.brand_kr,
                b.brand_popularity,
                p.price,
                p.original_price,
                p.discount_rate,
                p.product_url,
                p.image_url,
                p.image_path,
                p.tags,
                -- 리뷰 통계
                COALESCE(AVG(pr.rating), 0) as avg_rating,
                COUNT(DISTINCT pr.id) as review_count,
                -- 스타일 키워드
                ARRAY_AGG(DISTINCT psk.keyword) FILTER (WHERE psk.keyword IS NOT NULL) as style_keywords,
                -- 검색 랭킹
                ts_rank(to_tsvector('korean', p.product_name), plainto_tsquery('korean', %s)) as search_rank,
                -- 신뢰도 점수
                (COALESCE(AVG(pr.rating), 0) * LN(1 + COUNT(DISTINCT pr.id))) as confidence_score
            FROM products p
            LEFT JOIN brands b ON p.brand_id = b.brand_id
            LEFT JOIN product_reviews pr ON p.product_id = pr.product_id
            LEFT JOIN product_style_keywords psk ON p.product_id = psk.product_id
            WHERE to_tsvector('korean', p.product_name) @@ plainto_tsquery('korean', %s)
            GROUP BY p.product_id, p.product_name, p.category, p.brand_id, 
                     b.brand_en, b.brand_kr, b.brand_popularity, p.price, 
                     p.original_price, p.discount_rate, p.product_url, 
                     p.image_url, p.image_path, p.tags
            ORDER BY search_rank DESC, confidence_score DESC, b.brand_popularity DESC
            LIMIT %s
        """
        
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                    cursor.execute(query, (search_query, search_query, limit))
                    
                    results = []
                    for row in cursor.fetchall():
                        product = dict(row)
                        if product['style_keywords'] is None:
                            product['style_keywords'] = []
                        results.append(product)
                    
                    logger.info(f"정규화된 풀텍스트 검색 완료: {len(results)}개 결과")
                    return results
                    
        except Exception as e:
            logger.error(f"풀텍스트 검색 실패: {e}")
            return []
    
    def get_product_by_id(self, product_id: str) -> Optional[Dict[str, Any]]:
        """상품 ID로 상품 정보 조회 (정규화된 구조)"""
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                    cursor.execute("""
                        SELECT 
                            p.*,
                            b.brand_en,
                            b.brand_kr,
                            b.brand_popularity,
                            COALESCE(AVG(pr.rating), 0) as avg_rating,
                            COUNT(DISTINCT pr.id) as review_count,
                            ARRAY_AGG(DISTINCT psk.keyword) FILTER (WHERE psk.keyword IS NOT NULL) as style_keywords,
                            COUNT(DISTINCT ps.id) as size_count
                        FROM products p
                        LEFT JOIN brands b ON p.brand_id = b.brand_id
                        LEFT JOIN product_reviews pr ON p.product_id = pr.product_id
                        LEFT JOIN product_style_keywords psk ON p.product_id = psk.product_id
                        LEFT JOIN product_sizes ps ON p.product_id = ps.product_id
                        WHERE p.product_id = %s
                        GROUP BY p.product_id, p.product_name, p.category, p.brand_id, 
                                 p.price, p.original_price, p.discount_rate, p.product_url, 
                                 p.image_url, p.image_path, p.tags, p.created_at,
                                 b.brand_en, b.brand_kr, b.brand_popularity
                    """, (product_id,))
                    
                    row = cursor.fetchone()
                    if row:
                        product = dict(row)
                        if product['style_keywords'] is None:
                            product['style_keywords'] = []
                        return product
                    
                    return None
                    
        except Exception as e:
            logger.error(f"상품 조회 실패: {e}")
            return None
    
    def get_reviews_by_product_id(self, product_id: str) -> List[Dict[str, Any]]:
        """상품 ID로 리뷰 조회 (정규화된 구조)"""
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                    cursor.execute("""
                        SELECT 
                            pr.*,
                            p.rating as product_rating
                        FROM product_reviews pr
                        LEFT JOIN products p ON pr.product_id = p.product_id
                        WHERE pr.product_id = %s
                        ORDER BY pr.likes DESC, pr.review_date DESC
                    """, (product_id,))
                    
                    return [dict(row) for row in cursor.fetchall()]
                    
        except Exception as e:
            logger.error(f"리뷰 조회 실패: {e}")
            return []
    
    def get_sizes_by_product_id(self, product_id: str) -> List[Dict[str, Any]]:
        """상품 ID로 사이즈 정보 조회"""
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                    cursor.execute("""
                        SELECT * FROM product_sizes 
                        WHERE product_id = %s
                        ORDER BY keyword_order
                    """, (product_id,))
                    
                    return [dict(row) for row in cursor.fetchall()]
                    
        except Exception as e:
            logger.error(f"사이즈 조회 실패: {e}")
            return []
    
    def get_brand_statistics(self) -> Dict[str, Any]:
        """브랜드별 통계 정보"""
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                    cursor.execute("""
                        SELECT 
                            b.brand_id,
                            b.brand_kr,
                            b.brand_en,
                            b.brand_popularity,
                            COUNT(p.product_id) as product_count,
                            AVG(p.price) as avg_price,
                            AVG(pr.rating) as avg_rating,
                            COUNT(DISTINCT pr.id) as total_reviews
                        FROM brands b
                        LEFT JOIN products p ON b.brand_id = p.brand_id
                        LEFT JOIN product_reviews pr ON p.product_id = pr.product_id
                        GROUP BY b.brand_id, b.brand_kr, b.brand_en, b.brand_popularity
                        ORDER BY b.brand_popularity DESC
                        LIMIT 20
                    """)
                    
                    return [dict(row) for row in cursor.fetchall()]
                    
        except Exception as e:
            logger.error(f"브랜드 통계 조회 실패: {e}")
            return []
    
    def search_by_style_keywords(self, keywords: List[str], limit: int = 10) -> List[Dict[str, Any]]:
        """스타일 키워드로 상품 검색"""
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                    cursor.execute("""
                        SELECT DISTINCT 
                            p.product_id,
                            p.product_name,
                            p.category,
                            b.brand_kr,
                            p.price,
                            p.image_url,
                            COUNT(DISTINCT psk.keyword) as keyword_match_count,
                            ARRAY_AGG(DISTINCT psk.keyword) FILTER (WHERE psk.keyword = ANY(%s)) as matched_keywords
                        FROM products p
                        LEFT JOIN brands b ON p.brand_id = b.brand_id
                        LEFT JOIN product_style_keywords psk ON p.product_id = psk.product_id
                        WHERE psk.keyword = ANY(%s)
                        GROUP BY p.product_id, p.product_name, p.category, b.brand_kr, p.price, p.image_url
                        ORDER BY keyword_match_count DESC, p.price ASC
                        LIMIT %s
                    """, (keywords, keywords, limit))
                    
                    return [dict(row) for row in cursor.fetchall()]
                    
        except Exception as e:
            logger.error(f"스타일 키워드 검색 실패: {e}")
            return []
    
    def get_statistics(self) -> Dict[str, Any]:
        """전체 통계 정보"""
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                    # 기본 통계
                    cursor.execute("SELECT COUNT(*) as total_products FROM products")
                    total_products = cursor.fetchone()['total_products']
                    
                    cursor.execute("SELECT COUNT(*) as total_brands FROM brands")
                    total_brands = cursor.fetchone()['total_brands']
                    
                    cursor.execute("SELECT COUNT(*) as total_reviews FROM product_reviews")
                    total_reviews = cursor.fetchone()['total_reviews']
                    
                    cursor.execute("SELECT COUNT(*) as total_keywords FROM product_style_keywords")
                    total_keywords = cursor.fetchone()['total_keywords']
                    
                    cursor.execute("SELECT COUNT(*) as total_sizes FROM product_sizes")
                    total_sizes = cursor.fetchone()['total_sizes']
                    
                    # 카테고리별 통계
                    cursor.execute("""
                        SELECT category, COUNT(*) as count
                        FROM products 
                        GROUP BY category 
                        ORDER BY count DESC
                    """)
                    category_stats = [dict(row) for row in cursor.fetchall()]
                    
                    # 평점 통계
                    cursor.execute("""
                        SELECT 
                            AVG(rating) as avg_rating,
                            COUNT(*) as total_rated_reviews
                        FROM product_reviews 
                        WHERE rating IS NOT NULL
                    """)
                    rating_stats = cursor.fetchone()
                    
                    return {
                        'total_products': total_products,
                        'total_brands': total_brands,
                        'total_reviews': total_reviews,
                        'total_keywords': total_keywords,
                        'total_sizes': total_sizes,
                        'category_stats': category_stats,
                        'avg_rating': rating_stats['avg_rating'] if rating_stats else 0,
                        'total_rated_reviews': rating_stats['total_rated_reviews'] if rating_stats else 0
                    }
                    
        except Exception as e:
            logger.error(f"통계 조회 실패: {e}")
            return {}
    
    def save_recommendation_history(self, user_id: str, product_id: str, 
                                  recommendation_reason: str, confidence_score: float):
        """추천 히스토리 저장"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        INSERT INTO recommendation_history 
                        (user_id, product_id, recommendation_reason, confidence_score)
                        VALUES (%s, %s, %s, %s)
                    """, (user_id, product_id, recommendation_reason, confidence_score))
                    conn.commit()
                    
        except Exception as e:
            logger.error(f"추천 히스토리 저장 실패: {e}")

def main():
    """테스트 함수"""
    manager = PostgreSQLManagerUpdated()
    
    # 통계 확인
    stats = manager.get_statistics()
    print("📊 데이터베이스 통계:")
    for key, value in stats.items():
        print(f"  {key}: {value}")
    
    # 브랜드 통계 확인
    brand_stats = manager.get_brand_statistics()
    print(f"\n🏷️ 브랜드 통계 (상위 5개):")
    for brand in brand_stats[:5]:
        print(f"  {brand['brand_kr']}: {brand['product_count']}개 상품, 평균 평점: {brand['avg_rating']:.1f}")

if __name__ == "__main__":
    main() 