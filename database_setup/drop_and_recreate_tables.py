#!/usr/bin/env python3
"""
기존 테이블 삭제 및 새 테이블 생성
"""

import psycopg2
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def drop_and_recreate_tables():
    """기존 테이블 삭제 및 새 테이블 생성"""
    
    # 데이터베이스 설정
    db_config = {
        'host': 'localhost',
        'port': 5432,
        'database': 'fashion_recommendation',
        'user': 'postgres',
        'password': 'postgres'
    }
    
    try:
        # 데이터베이스 연결
        conn = psycopg2.connect(**db_config)
        conn.autocommit = True
        logger.info("PostgreSQL 데이터베이스에 성공적으로 연결되었습니다.")
        
        with conn.cursor() as cursor:
            # 1. 기존 테이블 삭제 (순서 중요)
            logger.info("기존 테이블 삭제 중...")
            
            cursor.execute("DROP TABLE IF EXISTS product_images CASCADE")
            cursor.execute("DROP TABLE IF EXISTS product_style_keywords CASCADE")
            cursor.execute("DROP TABLE IF EXISTS product_reviews CASCADE")
            cursor.execute("DROP TABLE IF EXISTS product_sizes CASCADE")
            cursor.execute("DROP TABLE IF EXISTS products CASCADE")
            
            # 인덱스도 함께 삭제
            cursor.execute("DROP INDEX IF EXISTS idx_products_category CASCADE")
            cursor.execute("DROP INDEX IF EXISTS idx_products_brand CASCADE")
            cursor.execute("DROP INDEX IF EXISTS idx_products_price CASCADE")
            cursor.execute("DROP INDEX IF EXISTS idx_products_tags CASCADE")
            cursor.execute("DROP INDEX IF EXISTS idx_sizes_product_id CASCADE")
            cursor.execute("DROP INDEX IF EXISTS idx_reviews_product_id CASCADE")
            cursor.execute("DROP INDEX IF EXISTS idx_keywords_product_id CASCADE")
            cursor.execute("DROP INDEX IF EXISTS idx_images_product_id CASCADE")
            
            logger.info("기존 테이블이 성공적으로 삭제되었습니다.")
            
            # 2. 새 테이블 생성
            logger.info("새 테이블 생성 중...")
            
            # 상품 테이블 (CSV + JSON 통합)
            cursor.execute("""
                CREATE TABLE products (
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
                CREATE TABLE product_sizes (
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
                CREATE TABLE product_reviews (
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
                CREATE TABLE product_style_keywords (
                    id SERIAL PRIMARY KEY,
                    product_id INTEGER REFERENCES products(product_id) ON DELETE CASCADE,
                    keyword VARCHAR(100),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 이미지 정보 테이블
            cursor.execute("""
                CREATE TABLE product_images (
                    id SERIAL PRIMARY KEY,
                    product_id INTEGER REFERENCES products(product_id) ON DELETE CASCADE,
                    image_filename VARCHAR(255),
                    image_path TEXT,
                    image_url TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 인덱스 생성
            cursor.execute("CREATE INDEX idx_products_category ON products(category)")
            cursor.execute("CREATE INDEX idx_products_brand ON products(brand_en)")
            cursor.execute("CREATE INDEX idx_products_price ON products(price)")
            cursor.execute("CREATE INDEX idx_products_tags ON products USING GIN(tags)")
            cursor.execute("CREATE INDEX idx_sizes_product_id ON product_sizes(product_id)")
            cursor.execute("CREATE INDEX idx_reviews_product_id ON product_reviews(product_id)")
            cursor.execute("CREATE INDEX idx_keywords_product_id ON product_style_keywords(product_id)")
            cursor.execute("CREATE INDEX idx_images_product_id ON product_images(product_id)")
            
            logger.info("새 테이블과 인덱스가 성공적으로 생성되었습니다.")
        
        conn.close()
        print("✅ 테이블 재생성이 완료되었습니다!")
        return True
        
    except Exception as e:
        logger.error(f"테이블 재생성 실패: {e}")
        print(f"❌ 테이블 재생성에 실패했습니다: {e}")
        return False

if __name__ == "__main__":
    drop_and_recreate_tables() 