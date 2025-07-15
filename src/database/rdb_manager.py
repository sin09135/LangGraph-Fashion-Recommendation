"""
RDB 기반 데이터베이스 관리자
SQLite/PostgreSQL 지원
"""

import sqlite3
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple
import json
import os
from datetime import datetime
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RDBManager:
    """RDB 기반 데이터베이스 관리자"""
    
    def __init__(self, db_path: str = "fashion_recommendation.db", db_type: str = "sqlite"):
        self.db_path = db_path
        self.db_type = db_type
        self.connection = None
        
        # 데이터베이스 초기화
        self._init_database()
    
    def _init_database(self):
        """데이터베이스 초기화 및 테이블 생성"""
        try:
            if self.db_type == "sqlite":
                self.connection = sqlite3.connect(self.db_path)
                self.connection.row_factory = sqlite3.Row  # 딕셔너리 형태로 결과 반환
            
            self._create_tables()
            logger.info(f"데이터베이스 초기화 완료: {self.db_path}")
            
        except Exception as e:
            logger.error(f"데이터베이스 초기화 실패: {e}")
            raise
    
    def _create_tables(self):
        """테이블 생성"""
        cursor = self.connection.cursor()
        
        # 상품 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS products (
                product_id TEXT PRIMARY KEY,
                product_name TEXT NOT NULL,
                category TEXT,
                brand TEXT,
                price INTEGER,
                rating REAL DEFAULT 0.0,
                review_count INTEGER DEFAULT 0,
                length REAL,
                chest REAL,
                shoulder REAL,
                url TEXT,
                image_url TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 스타일 키워드 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS style_keywords (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id TEXT,
                keyword TEXT NOT NULL,
                weight REAL DEFAULT 1.0,
                FOREIGN KEY (product_id) REFERENCES products (product_id) ON DELETE CASCADE
            )
        """)
        
        # 리뷰 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id TEXT,
                review_id TEXT,
                content TEXT,
                rating INTEGER,
                helpful_count INTEGER DEFAULT 0,
                created_at TIMESTAMP,
                FOREIGN KEY (product_id) REFERENCES products (product_id) ON DELETE CASCADE
            )
        """)
        
        # 사용자 선호도 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_preferences (
                user_id TEXT,
                preference_type TEXT,
                preference_value TEXT,
                weight REAL DEFAULT 1.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, preference_type)
            )
        """)
        
        # 추천 히스토리 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS recommendation_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                product_id TEXT,
                recommendation_reason TEXT,
                confidence_score REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (product_id) REFERENCES products (product_id) ON DELETE CASCADE
            )
        """)
        
        # 인덱스 생성
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_category ON products(category)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_rating ON products(rating)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_price ON products(price)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_style_keywords_keyword ON style_keywords(keyword)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_reviews_product_id ON reviews(product_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_reviews_rating ON reviews(rating)")
        
        self.connection.commit()
        logger.info("테이블 및 인덱스 생성 완료")
    
    def insert_products_from_dataframe(self, df: pd.DataFrame):
        """DataFrame에서 상품 데이터 삽입"""
        cursor = self.connection.cursor()
        
        try:
            for _, row in df.iterrows():
                # 상품 기본 정보 삽입
                cursor.execute("""
                    INSERT OR REPLACE INTO products 
                    (product_id, product_name, category, brand, price, rating, review_count, 
                     length, chest, shoulder, url, image_url)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    str(row.get('product_id', '')),
                    str(row.get('product_name', '')),
                    str(row.get('categories', '')),
                    str(row.get('brand', '')),
                    int(row.get('price', 0)) if pd.notna(row.get('price')) else None,
                    float(row.get('rating', 0.0)) if pd.notna(row.get('rating')) else 0.0,
                    int(row.get('review_count', 0)) if pd.notna(row.get('review_count')) else 0,
                    float(row.get('length', 0)) if pd.notna(row.get('length')) else None,
                    float(row.get('chest', 0)) if pd.notna(row.get('chest')) else None,
                    float(row.get('shoulder', 0)) if pd.notna(row.get('shoulder')) else None,
                    str(row.get('url', '')),
                    str(row.get('image_url', ''))
                ))
                
                # 스타일 키워드 삽입
                style_keywords = row.get('tags', [])
                if isinstance(style_keywords, list):
                    for keyword in style_keywords:
                        cursor.execute("""
                            INSERT OR REPLACE INTO style_keywords (product_id, keyword)
                            VALUES (?, ?)
                        """, (str(row.get('product_id', '')), str(keyword)))
            
            self.connection.commit()
            logger.info(f"{len(df)}개 상품 데이터 삽입 완료")
            
        except Exception as e:
            self.connection.rollback()
            logger.error(f"상품 데이터 삽입 실패: {e}")
            raise
    
    def search_products_sql(self, 
                           filters: Dict[str, Any], 
                           user_preferences: Dict[str, Any] = None,
                           limit: int = 10) -> List[Dict[str, Any]]:
        """SQL 기반 상품 검색"""
        
        # 기본 쿼리 구성
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
                GROUP_CONCAT(sk.keyword) as style_keywords,
                (p.rating * LOG(1 + p.review_count)) as base_score
            FROM products p
            LEFT JOIN style_keywords sk ON p.product_id = sk.product_id
        """
        
        where_conditions = []
        params = []
        
        # 필터 조건 추가
        if filters.get('categories'):
            where_conditions.append("p.category LIKE ?")
            params.append(f"%{filters['categories']}%")
        
        if filters.get('tags'):
            where_conditions.append("sk.keyword = ?")
            params.append(filters['tags'])
        
        if filters.get('color'):
            where_conditions.append("p.product_name LIKE ?")
            params.append(f"%{filters['color']}%")
        
        if filters.get('brand'):
            where_conditions.append("p.brand LIKE ?")
            params.append(f"%{filters['brand']}%")
        
        if filters.get('price_range') == '저렴':
            where_conditions.append("p.price <= (SELECT AVG(price) * 0.7 FROM products)")
        elif filters.get('price_range') == '고급':
            where_conditions.append("p.price >= (SELECT AVG(price) * 1.3 FROM products)")
        
        if filters.get('length'):
            op, value = filters['length']
            if op == '<=':
                where_conditions.append("p.length <= ?")
            elif op == '>=':
                where_conditions.append("p.length >= ?")
            elif op == '==':
                where_conditions.append("p.length = ?")
            params.append(value)
        
        if filters.get('chest'):
            op, value = filters['chest']
            if op == '<=':
                where_conditions.append("p.chest <= ?")
            elif op == '>=':
                where_conditions.append("p.chest >= ?")
            elif op == '==':
                where_conditions.append("p.chest = ?")
            params.append(value)
        
        if filters.get('shoulder'):
            op, value = filters['shoulder']
            if op == '<=':
                where_conditions.append("p.shoulder <= ?")
            elif op == '>=':
                where_conditions.append("p.shoulder >= ?")
            elif op == '==':
                where_conditions.append("p.shoulder = ?")
            params.append(value)
        
        # 크롭티 필터
        if filters.get('tags') and '크롭' in str(filters['tags']):
            where_conditions.append("p.category LIKE '%상의%' AND p.length < 66")
        
        # WHERE 절 추가
        if where_conditions:
            query += " WHERE " + " AND ".join(where_conditions)
        
        # GROUP BY 및 ORDER BY
        query += """
            GROUP BY p.product_id
            ORDER BY base_score DESC
            LIMIT ?
        """
        params.append(limit)
        
        try:
            cursor = self.connection.cursor()
            cursor.execute(query, params)
            
            results = []
            for row in cursor.fetchall():
                product = dict(row)
                # 스타일 키워드를 리스트로 변환
                if product['style_keywords']:
                    product['style_keywords'] = product['style_keywords'].split(',')
                else:
                    product['style_keywords'] = []
                
                results.append(product)
            
            logger.info(f"SQL 검색 완료: {len(results)}개 결과")
            return results
            
        except Exception as e:
            logger.error(f"SQL 검색 실패: {e}")
            return []
    
    def get_product_by_id(self, product_id: str) -> Optional[Dict[str, Any]]:
        """상품 ID로 상품 정보 조회"""
        cursor = self.connection.cursor()
        
        try:
            cursor.execute("""
                SELECT 
                    p.*,
                    GROUP_CONCAT(sk.keyword) as style_keywords
                FROM products p
                LEFT JOIN style_keywords sk ON p.product_id = sk.product_id
                WHERE p.product_id = ?
                GROUP BY p.product_id
            """, (product_id,))
            
            row = cursor.fetchone()
            if row:
                product = dict(row)
                if product['style_keywords']:
                    product['style_keywords'] = product['style_keywords'].split(',')
                else:
                    product['style_keywords'] = []
                return product
            
            return None
            
        except Exception as e:
            logger.error(f"상품 조회 실패: {e}")
            return None
    
    def get_reviews_by_product_id(self, product_id: str) -> List[Dict[str, Any]]:
        """상품 ID로 리뷰 조회"""
        cursor = self.connection.cursor()
        
        try:
            cursor.execute("""
                SELECT * FROM reviews 
                WHERE product_id = ?
                ORDER BY helpful_count DESC, rating DESC
            """, (product_id,))
            
            return [dict(row) for row in cursor.fetchall()]
            
        except Exception as e:
            logger.error(f"리뷰 조회 실패: {e}")
            return []
    
    def save_user_preference(self, user_id: str, preference_type: str, preference_value: str, weight: float = 1.0):
        """사용자 선호도 저장"""
        cursor = self.connection.cursor()
        
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO user_preferences 
                (user_id, preference_type, preference_value, weight)
                VALUES (?, ?, ?, ?)
            """, (user_id, preference_type, preference_value, weight))
            
            self.connection.commit()
            logger.info(f"사용자 선호도 저장 완료: {user_id} - {preference_type}")
            
        except Exception as e:
            self.connection.rollback()
            logger.error(f"사용자 선호도 저장 실패: {e}")
    
    def get_user_preferences(self, user_id: str) -> Dict[str, Any]:
        """사용자 선호도 조회"""
        cursor = self.connection.cursor()
        
        try:
            cursor.execute("""
                SELECT preference_type, preference_value, weight
                FROM user_preferences
                WHERE user_id = ?
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
        cursor = self.connection.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO recommendation_history 
                (user_id, product_id, recommendation_reason, confidence_score)
                VALUES (?, ?, ?, ?)
            """, (user_id, product_id, recommendation_reason, confidence_score))
            
            self.connection.commit()
            
        except Exception as e:
            self.connection.rollback()
            logger.error(f"추천 히스토리 저장 실패: {e}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """데이터베이스 통계 조회"""
        cursor = self.connection.cursor()
        
        try:
            # 상품 통계
            cursor.execute("SELECT COUNT(*) as total_products FROM products")
            total_products = cursor.fetchone()['total_products']
            
            cursor.execute("SELECT AVG(rating) as avg_rating FROM products")
            avg_rating = cursor.fetchone()['avg_rating']
            
            cursor.execute("SELECT COUNT(DISTINCT category) as category_count FROM products")
            category_count = cursor.fetchone()['category_count']
            
            # 리뷰 통계
            cursor.execute("SELECT COUNT(*) as total_reviews FROM reviews")
            total_reviews = cursor.fetchone()['total_reviews']
            
            return {
                'total_products': total_products,
                'avg_rating': avg_rating,
                'category_count': category_count,
                'total_reviews': total_reviews
            }
            
        except Exception as e:
            logger.error(f"통계 조회 실패: {e}")
            return {}
    
    def close(self):
        """데이터베이스 연결 종료"""
        if self.connection:
            self.connection.close()
            logger.info("데이터베이스 연결 종료")


def main():
    """RDB 매니저 테스트"""
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
    
    # RDB 매니저 초기화
    rdb_manager = RDBManager()
    
    try:
        # 데이터 삽입
        rdb_manager.insert_products_from_dataframe(df)
        
        # 검색 테스트
        results = rdb_manager.search_products_sql(
            filters={'categories': '상의'},
            limit=5
        )
        
        print("검색 결과:")
        for product in results:
            print(f"- {product['product_name']} (평점: {product['rating']})")
        
        # 통계 조회
        stats = rdb_manager.get_statistics()
        print(f"\n통계: {stats}")
        
    finally:
        rdb_manager.close()


if __name__ == "__main__":
    main() 