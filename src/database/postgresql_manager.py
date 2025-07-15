"""
PostgreSQL 기반 데이터베이스 관리자
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

class PostgreSQLManager:
    """PostgreSQL 기반 데이터베이스 관리자"""
    
    def __init__(self, 
                 host: str = "localhost",
                 port: int = 5432,
                 database: str = "fashion_recommendation",
                 user: str = "postgres",
                 password: str = "password"):
        
        self.connection_params = {
            'host': host,
            'port': port,
            'database': database,
            'user': user,
            'password': password
        }
        
        # 데이터베이스 초기화
        self._init_database()
    
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
    
    def _init_database(self):
        """데이터베이스 초기화 및 테이블 생성"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    self._create_tables(cursor)
                    conn.commit()
            
            logger.info("PostgreSQL 데이터베이스 초기화 완료")
            
        except Exception as e:
            logger.error(f"데이터베이스 초기화 실패: {e}")
            raise
    
    def _create_tables(self, cursor):
        """테이블 생성"""
        
        # 상품 테이블 (새로운 통합 스키마)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS products (
                product_id INTEGER PRIMARY KEY,
                category VARCHAR(50),
                category_code INTEGER,
                brand_en VARCHAR(100),
                brand_kr VARCHAR(100),
                price INTEGER,
                original_price INTEGER,
                discount_rate INTEGER,
                product_url TEXT,
                image_url TEXT,
                image_path TEXT,
                product_name TEXT,
                description TEXT,
                tags TEXT[],
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 사이즈 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS product_sizes (
                id SERIAL PRIMARY KEY,
                product_id INTEGER REFERENCES products(product_id) ON DELETE CASCADE,
                size_name VARCHAR(50),
                size_value VARCHAR(50),
                stock_status VARCHAR(20),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 리뷰 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS product_reviews (
                id SERIAL PRIMARY KEY,
                product_id INTEGER REFERENCES products(product_id) ON DELETE CASCADE,
                review_text TEXT,
                rating INTEGER,
                review_date DATE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 스타일 키워드 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS product_style_keywords (
                id SERIAL PRIMARY KEY,
                product_id INTEGER REFERENCES products(product_id) ON DELETE CASCADE,
                keyword VARCHAR(100),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 이미지 정보 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS product_images (
                id SERIAL PRIMARY KEY,
                product_id INTEGER REFERENCES products(product_id) ON DELETE CASCADE,
                image_filename VARCHAR(255),
                image_path TEXT,
                image_url TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 사용자 선호도 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_preferences (
                user_id VARCHAR(100),
                preference_type VARCHAR(50),
                preference_value TEXT,
                weight DECIMAL(3,2) DEFAULT 1.00,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, preference_type)
            )
        """)
        
        # 추천 히스토리 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS recommendation_history (
                id SERIAL PRIMARY KEY,
                user_id VARCHAR(100),
                product_id INTEGER REFERENCES products(product_id) ON DELETE CASCADE,
                recommendation_reason TEXT,
                confidence_score DECIMAL(5,4),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 인덱스 생성
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_category ON products(category)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_brand ON products(brand_en)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_price ON products(price)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_tags ON products USING GIN(tags)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sizes_product_id ON product_sizes(product_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_reviews_product_id ON product_reviews(product_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_keywords_product_id ON product_style_keywords(product_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_images_product_id ON product_images(product_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_preferences_user_id ON user_preferences(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_recommendation_history_user_id ON recommendation_history(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_recommendation_history_created_at ON recommendation_history(created_at)")
        
        # 풀텍스트 검색 인덱스
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_products_name_search 
            ON products USING gin(to_tsvector('english', product_name))
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_reviews_content_search 
            ON product_reviews USING gin(to_tsvector('english', review_text))
        """)
        
        logger.info("테이블 및 인덱스 생성 완료")
    
    def _safe_get_value(self, row, key, default=None, is_int=False):
        """안전하게 값을 가져오는 헬퍼 함수"""
        try:
            value = row.get(key, default)
            if pd.isna(value) or value == '' or str(value).strip() == '':
                return default
            value = str(value).strip()
            if is_int:
                return int(value) if value.isdigit() else default
            return value
        except:
            return default

    def insert_products_from_dataframe(self, df: pd.DataFrame):
        """DataFrame에서 상품 데이터 삽입"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    # 상품 데이터 삽입
                    for _, row in df.iterrows():
                        # CSV 컬럼명과 정확히 매핑
                        cursor.execute("""
                            INSERT INTO products 
                            (product_id, category, category_code, brand_en, brand_kr, price, 
                             original_price, discount_rate, product_url, image_url, image_path, product_name)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (product_id) DO UPDATE SET
                                category = EXCLUDED.category,
                                category_code = EXCLUDED.category_code,
                                brand_en = EXCLUDED.brand_en,
                                brand_kr = EXCLUDED.brand_kr,
                                price = EXCLUDED.price,
                                original_price = EXCLUDED.original_price,
                                discount_rate = EXCLUDED.discount_rate,
                                product_url = EXCLUDED.product_url,
                                image_url = EXCLUDED.image_url,
                                image_path = EXCLUDED.image_path,
                                product_name = EXCLUDED.product_name
                        """, (
                            self._safe_get_value(row, 'product_id', None, is_int=True),
                            self._safe_get_value(row, 'category', ''),
                            self._safe_get_value(row, 'category_code', None, is_int=True),
                            self._safe_get_value(row, 'brand_en', ''),
                            self._safe_get_value(row, 'brand_kr', ''),
                            self._safe_get_value(row, 'price', None, is_int=True),
                            self._safe_get_value(row, 'original_price', None, is_int=True),
                            self._safe_get_value(row, 'discount_rate', None, is_int=True),
                            self._safe_get_value(row, 'product_url', ''),
                            self._safe_get_value(row, 'image_url', ''),
                            self._safe_get_value(row, 'image_path', ''),
                            self._safe_get_value(row, 'product_name', '')
                        ))
                    
                    conn.commit()
                    logger.info(f"{len(df)}개 상품 데이터 삽입 완료")
                    
        except Exception as e:
            logger.error(f"상품 데이터 삽입 실패: {e}")
            raise
    
    def search_products_sql(self, 
                           filters: Dict[str, Any], 
                           user_preferences: Dict[str, Any] = None,
                           limit: int = 10) -> List[Dict[str, Any]]:
        """PostgreSQL 기반 상품 검색 (고급 쿼리)"""
        
        # 기본 쿼리 구성
        query = """
            SELECT DISTINCT 
                p.product_id,
                p.product_name,
                p.category,
                p.brand_en,
                p.brand_kr,
                p.price,
                p.original_price,
                p.discount_rate,
                p.product_url,
                p.image_url,
                p.image_path,
                p.tags,
                ARRAY_AGG(psk.keyword) FILTER (WHERE psk.keyword IS NOT NULL) as style_keywords
            FROM products p
            LEFT JOIN product_style_keywords psk ON p.product_id = psk.product_id
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
            where_conditions.append(f"p.brand_en ILIKE %s")
            params.append(f"%{filters['brand_en']}%")
        
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
        
        if filters.get('tags'):
            param_count += 1
            where_conditions.append(f"p.tags && %s")
            params.append(filters['tags'])
        
        # WHERE 절 추가
        if where_conditions:
            query += " WHERE " + " AND ".join(where_conditions)
        
        # GROUP BY 및 ORDER BY
        query += """
            GROUP BY p.product_id, p.product_name, p.category, p.brand_en, p.brand_kr, 
                     p.price, p.original_price, p.discount_rate, p.product_url, p.image_url, 
                     p.image_path, p.tags
            ORDER BY p.price ASC
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
                    
                    logger.info(f"PostgreSQL 검색 완료: {len(results)}개 결과")
                    return results
                    
        except Exception as e:
            logger.error(f"PostgreSQL 검색 실패: {e}")
            return []
    
    def search_products_fulltext(self, 
                                search_query: str, 
                                limit: int = 10) -> List[Dict[str, Any]]:
        """풀텍스트 검색 (PostgreSQL 특화 기능)"""
        
        query = """
            SELECT DISTINCT 
                p.product_id,
                p.product_name,
                p.category,
                p.brand,
                p.price,
                p.rating,
                p.review_count,
                p.length,
                p.chest,
                p.shoulder,
                p.url,
                p.image_url,
                ARRAY_AGG(sk.keyword) FILTER (WHERE sk.keyword IS NOT NULL) as style_keywords,
                ts_rank(to_tsvector('korean', p.product_name), plainto_tsquery('korean', %s)) as search_rank,
                (p.rating * LN(1 + p.review_count)) as base_score
            FROM products p
            LEFT JOIN style_keywords sk ON p.product_id = sk.product_id
            WHERE to_tsvector('korean', p.product_name) @@ plainto_tsquery('korean', %s)
            GROUP BY p.product_id, p.product_name, p.category, p.brand, p.price, 
                     p.rating, p.review_count, p.length, p.chest, p.shoulder, p.url, p.image_url
            ORDER BY search_rank DESC, base_score DESC
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
                    
                    logger.info(f"풀텍스트 검색 완료: {len(results)}개 결과")
                    return results
                    
        except Exception as e:
            logger.error(f"풀텍스트 검색 실패: {e}")
            return []
    
    def get_product_by_id(self, product_id: str) -> Optional[Dict[str, Any]]:
        """상품 ID로 상품 정보 조회"""
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                    cursor.execute("""
                        SELECT 
                            p.*,
                            ARRAY_AGG(sk.keyword) FILTER (WHERE sk.keyword IS NOT NULL) as style_keywords
                        FROM products p
                        LEFT JOIN style_keywords sk ON p.product_id = sk.product_id
                        WHERE p.product_id = %s
                        GROUP BY p.product_id, p.product_name, p.category, p.brand, p.price, 
                                 p.rating, p.review_count, p.length, p.chest, p.shoulder, p.url, p.image_url,
                                 p.created_at, p.updated_at
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
        """상품 ID로 리뷰 조회"""
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                    cursor.execute("""
                        SELECT * FROM reviews 
                        WHERE product_id = %s
                        ORDER BY helpful_count DESC, rating DESC
                    """, (product_id,))
                    
                    return [dict(row) for row in cursor.fetchall()]
                    
        except Exception as e:
            logger.error(f"리뷰 조회 실패: {e}")
            return []
    
    def save_user_preference(self, user_id: str, preference_type: str, preference_value: str, weight: float = 1.0):
        """사용자 선호도 저장"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        INSERT INTO user_preferences 
                        (user_id, preference_type, preference_value, weight)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (user_id, preference_type) 
                        DO UPDATE SET 
                            preference_value = EXCLUDED.preference_value,
                            weight = EXCLUDED.weight,
                            created_at = CURRENT_TIMESTAMP
                    """, (user_id, preference_type, preference_value, weight))
                    
                    conn.commit()
                    logger.info(f"사용자 선호도 저장 완료: {user_id} - {preference_type}")
                    
        except Exception as e:
            logger.error(f"사용자 선호도 저장 실패: {e}")
    
    def get_user_preferences(self, user_id: str) -> Dict[str, Any]:
        """사용자 선호도 조회"""
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                    cursor.execute("""
                        SELECT preference_type, preference_value, weight
                        FROM user_preferences
                        WHERE user_id = %s
                    """, (user_id,))
                    
                    preferences = {}
                    for row in cursor.fetchall():
                        pref_type = row['preference_type']
                        if pref_type not in preferences:
                            preferences[pref_type] = []
                        preferences[pref_type].append({
                            'value': row['preference_value'],
                            'weight': row['weight']
                        })
                    
                    return preferences
                    
        except Exception as e:
            logger.error(f"사용자 선호도 조회 실패: {e}")
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
    
    def get_statistics(self) -> Dict[str, Any]:
        """데이터베이스 통계 조회"""
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                    # 상품 통계
                    cursor.execute("SELECT COUNT(*) as total_products FROM products")
                    total_products = cursor.fetchone()['total_products']
                    
                    cursor.execute("SELECT COUNT(DISTINCT category) as category_count FROM products")
                    category_count = cursor.fetchone()['category_count']
                    
                    # 리뷰 통계
                    cursor.execute("SELECT COUNT(*) as total_reviews FROM product_reviews")
                    total_reviews = cursor.fetchone()['total_reviews']
                    
                    # 스타일 키워드 통계
                    cursor.execute("SELECT COUNT(*) as total_style_keywords FROM product_style_keywords")
                    total_style_keywords = cursor.fetchone()['total_style_keywords']
                    
                    # 사용자 통계
                    cursor.execute("SELECT COUNT(DISTINCT user_id) as unique_users FROM recommendation_history")
                    unique_users = cursor.fetchone()['unique_users']
                    
                    return {
                        'total_products': total_products,
                        'category_count': category_count,
                        'total_reviews': total_reviews,
                        'total_style_keywords': total_style_keywords,
                        'unique_users': unique_users
                    }
                    
        except Exception as e:
            logger.error(f"통계 조회 실패: {e}")
            return {}
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """성능 메트릭 조회 (PostgreSQL 특화)"""
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                    # 테이블 크기
                    cursor.execute("""
                        SELECT 
                            schemaname,
                            tablename,
                            attname,
                            n_distinct,
                            correlation
                        FROM pg_stats 
                        WHERE schemaname = 'public' 
                        AND tablename IN ('products', 'style_keywords', 'reviews')
                        ORDER BY tablename, attname
                    """)
                    
                    stats = cursor.fetchall()
                    
                    # 인덱스 사용 통계
                    cursor.execute("""
                        SELECT 
                            indexrelname,
                            idx_tup_read,
                            idx_tup_fetch
                        FROM pg_stat_user_indexes 
                        WHERE schemaname = 'public'
                    """)
                    
                    index_stats = cursor.fetchall()
                    
                    return {
                        'table_stats': [dict(row) for row in stats],
                        'index_stats': [dict(row) for row in index_stats]
                    }
                    
        except Exception as e:
            logger.error(f"성능 메트릭 조회 실패: {e}")
            return {}


def main():
    """PostgreSQL 매니저 테스트"""
    # 테스트 데이터 생성
    test_data = {
        'product_id': ['1', '2', '3'],
        'product_name': ['베이직 티셔츠', '스트릿 반팔', '꾸안꾸 무지'],
        'categories': ['상의', '상의', '상의'],
        'tags': [['베이직'], ['스트릿'], ['베이직', '꾸안꾸']],
        'rating': [4.8, 4.6, 4.9],
        'review_count': [1500, 800, 2200],
        'price': [29000, 35000, 25000],
        'url': ['https://musinsa.com/1', 'https://musinsa.com/2', 'https://musinsa.com/3']
    }
    
    df = pd.DataFrame(test_data)
    
    # PostgreSQL 매니저 초기화 (실제 환경에서는 적절한 연결 정보 사용)
    try:
        pg_manager = PostgreSQLManager(
            host="localhost",
            database="fashion_recommendation",
            user="postgres",
            password="password"
        )
        
        # 데이터 삽입
        pg_manager.insert_products_from_dataframe(df)
        
        # 검색 테스트
        results = pg_manager.search_products_sql(
            filters={'categories': '상의'},
            limit=5
        )
        
        print("PostgreSQL 검색 결과:")
        for product in results:
            print(f"- {product['product_name']} (평점: {product['rating']})")
        
        # 통계 조회
        stats = pg_manager.get_statistics()
        print(f"\n통계: {stats}")
        
    except Exception as e:
        print(f"PostgreSQL 연결 실패: {e}")
        print("PostgreSQL 서버가 실행 중이고 연결 정보가 올바른지 확인하세요.")


if __name__ == "__main__":
    main() 