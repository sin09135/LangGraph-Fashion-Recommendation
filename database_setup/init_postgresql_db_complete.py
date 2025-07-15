#!/usr/bin/env python3
"""
완전한 PostgreSQL 패션 추천 시스템 데이터베이스 초기화
3개 데이터 소스 통합: CSV + JSON + 이미지
"""

import json
import csv
import os
import psycopg2
from psycopg2.extras import RealDictCursor
import re
from urllib.parse import urlparse
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class CompletePostgreSQLInitializer:
    def __init__(self, db_config):
        self.db_config = db_config
        self.conn = None
        
    def connect(self):
        """데이터베이스 연결"""
        try:
            self.conn = psycopg2.connect(**self.db_config)
            self.conn.autocommit = True
            logger.info("PostgreSQL 데이터베이스에 성공적으로 연결되었습니다.")
            return True
        except Exception as e:
            logger.error(f"데이터베이스 연결 실패: {e}")
            return False
    
    def create_tables(self):
        """테이블 생성"""
        try:
            with self.conn.cursor() as cursor:
                # 상품 테이블 (CSV + JSON 통합)
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
                
                # 인덱스 생성
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_category ON products(category)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_brand ON products(brand_en)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_price ON products(price)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_tags ON products USING GIN(tags)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_sizes_product_id ON product_sizes(product_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_reviews_product_id ON product_reviews(product_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_keywords_product_id ON product_style_keywords(product_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_images_product_id ON product_images(product_id)")
                
                logger.info("모든 테이블과 인덱스가 성공적으로 생성되었습니다.")
                
        except Exception as e:
            logger.error(f"테이블 생성 실패: {e}")
            raise
    
    def extract_product_id_from_url(self, url):
        """URL에서 product_id 추출"""
        if not url:
            return None
        match = re.search(r'/products/(\d+)', url)
        return int(match.group(1)) if match else None
    
    def load_csv_data(self):
        """CSV 데이터 로드 (인코딩, 헤더 robust)"""
        csv_file = "data/musinsa_products_all_categories.csv"
        products_data = {}
        try:
            with open(csv_file, 'r', encoding='utf-8-sig') as file:
                reader = csv.DictReader(file)
                # 필드명 체크
                fieldnames = reader.fieldnames
                if not fieldnames or 'category' not in fieldnames or 'product_id' not in fieldnames:
                    raise ValueError(f"CSV 헤더 오류: {fieldnames}")
                for row in reader:
                    if not row.get('product_id'):
                        continue
                    try:
                        product_id = int(row['product_id'])
                    except Exception:
                        continue
                    products_data[product_id] = {
                        'product_id': product_id,
                        'category': row.get('category', ''),
                        'category_code': int(row['category_code']) if row.get('category_code') else None,
                        'brand_en': row.get('brand_en', ''),
                        'brand_kr': row.get('brand_kr', ''),
                        'price': int(row['price']) if row.get('price') else 0,
                        'original_price': int(row['original_price']) if row.get('original_price') else 0,
                        'discount_rate': int(row['discount_rate']) if row.get('discount_rate') else 0,
                        'product_url': row.get('product_url', ''),
                        'image_url': row.get('image_url', ''),
                        'image_path': row.get('image_path', ''),
                        'product_name': row.get('product_name', ''),
                        'description': '',
                        'tags': []
                    }
            logger.info(f"CSV에서 {len(products_data)}개 상품 데이터를 로드했습니다.")
            return products_data
        except Exception as e:
            logger.error(f"CSV 데이터 로드 실패: {e}")
            return {}

    def load_json_data(self):
        """JSON 데이터 로드 (리스트면 dict로 변환)"""
        json_file = "data/merged_all_data.json"
        try:
            with open(json_file, 'r', encoding='utf-8') as file:
                data = json.load(file)
            # 리스트면 dict로 변환
            if isinstance(data, list):
                data_dict = {}
                for item in data:
                    pid = item.get('product_id')
                    if pid is not None:
                        data_dict[int(pid)] = item
                data = data_dict
            logger.info(f"JSON에서 {len(data)}개 상품 데이터를 로드했습니다.")
            return data
        except Exception as e:
            logger.error(f"JSON 데이터 로드 실패: {e}")
            return {}
    
    def scan_image_files(self):
        """이미지 파일 스캔"""
        image_dir = "data/musinsa_images"
        image_data = {}
        
        try:
            if not os.path.exists(image_dir):
                logger.warning(f"이미지 디렉토리가 존재하지 않습니다: {image_dir}")
                return {}
            
            for filename in os.listdir(image_dir):
                if filename.endswith(('.jpg', '.jpeg', '.png')):
                    # 파일명에서 product_id 추출 (예: 가방_001_1481573_17138561629515_big.jpg)
                    parts = filename.split('_')
                    if len(parts) >= 3:
                        try:
                            product_id = int(parts[2])
                            if product_id not in image_data:
                                image_data[product_id] = []
                            image_data[product_id].append({
                                'filename': filename,
                                'path': os.path.join(image_dir, filename)
                            })
                        except ValueError:
                            continue
            
            logger.info(f"이미지 디렉토리에서 {len(image_data)}개 상품의 이미지를 찾았습니다.")
            return image_data
            
        except Exception as e:
            logger.error(f"이미지 파일 스캔 실패: {e}")
            return {}
    
    def merge_data(self, csv_data, json_data, image_data):
        """3개 데이터 소스 통합"""
        merged_data = {}
        
        # CSV 데이터를 기본으로 사용
        for product_id, csv_info in csv_data.items():
            merged_data[product_id] = csv_info.copy()
            
            # JSON 데이터 병합
            if product_id in json_data:
                json_info = json_data[product_id]
                merged_data[product_id]['description'] = json_info.get('description', '')
                
                # 태그 처리
                tags = []
                if 'tags' in json_info:
                    tags.extend(json_info['tags'])
                if 'style_keywords' in json_info:
                    tags.extend(json_info['style_keywords'])
                merged_data[product_id]['tags'] = list(set(tags))  # 중복 제거
            
            # 이미지 정보 추가
            if product_id in image_data:
                merged_data[product_id]['images'] = image_data[product_id]
            else:
                merged_data[product_id]['images'] = []
        
        logger.info(f"총 {len(merged_data)}개 상품 데이터가 통합되었습니다.")
        return merged_data
    
    def insert_products(self, merged_data):
        """상품 데이터 삽입"""
        try:
            with self.conn.cursor() as cursor:
                for product_id, product_info in merged_data.items():
                    cursor.execute("""
                        INSERT INTO products (
                            product_id, category, category_code, brand_en, brand_kr,
                            price, original_price, discount_rate, product_url,
                            image_url, image_path, product_name, description, tags
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                            product_name = EXCLUDED.product_name,
                            description = EXCLUDED.description,
                            tags = EXCLUDED.tags
                    """, (
                        product_info['product_id'],
                        product_info['category'],
                        product_info['category_code'],
                        product_info['brand_en'],
                        product_info['brand_kr'],
                        product_info['price'],
                        product_info['original_price'],
                        product_info['discount_rate'],
                        product_info['product_url'],
                        product_info['image_url'],
                        product_info['image_path'],
                        product_info['product_name'],
                        product_info['description'],
                        product_info['tags']
                    ))
            
            logger.info(f"{len(merged_data)}개 상품이 데이터베이스에 삽입되었습니다.")
            
        except Exception as e:
            logger.error(f"상품 데이터 삽입 실패: {e}")
            raise
    
    def insert_sizes(self, json_data):
        """사이즈 데이터 삽입"""
        try:
            with self.conn.cursor() as cursor:
                for product_id, product_info in json_data.items():
                    if 'sizes' in product_info:
                        for size_info in product_info['sizes']:
                            cursor.execute("""
                                INSERT INTO product_sizes (product_id, size_name, size_value, stock_status)
                                VALUES (%s, %s, %s, %s)
                            """, (
                                product_id,
                                size_info.get('name', ''),
                                size_info.get('value', ''),
                                size_info.get('stock_status', 'available')
                            ))
            
            logger.info("사이즈 데이터가 성공적으로 삽입되었습니다.")
            
        except Exception as e:
            logger.error(f"사이즈 데이터 삽입 실패: {e}")
            raise
    
    def insert_reviews(self, json_data):
        """리뷰 데이터 삽입"""
        try:
            with self.conn.cursor() as cursor:
                for product_id, product_info in json_data.items():
                    if 'reviews' in product_info:
                        for review in product_info['reviews']:
                            cursor.execute("""
                                INSERT INTO product_reviews (product_id, review_text, rating, review_date)
                                VALUES (%s, %s, %s, %s)
                            """, (
                                product_id,
                                review.get('text', ''),
                                review.get('rating', 0),
                                review.get('date', None)
                            ))
            
            logger.info("리뷰 데이터가 성공적으로 삽입되었습니다.")
            
        except Exception as e:
            logger.error(f"리뷰 데이터 삽입 실패: {e}")
            raise
    
    def insert_style_keywords(self, json_data):
        """스타일 키워드 데이터 삽입"""
        try:
            with self.conn.cursor() as cursor:
                for product_id, product_info in json_data.items():
                    keywords = []
                    if 'tags' in product_info:
                        keywords.extend(product_info['tags'])
                    if 'style_keywords' in product_info:
                        keywords.extend(product_info['style_keywords'])
                    
                    for keyword in set(keywords):  # 중복 제거
                        cursor.execute("""
                            INSERT INTO product_style_keywords (product_id, keyword)
                            VALUES (%s, %s)
                        """, (product_id, keyword))
            
            logger.info("스타일 키워드 데이터가 성공적으로 삽입되었습니다.")
            
        except Exception as e:
            logger.error(f"스타일 키워드 데이터 삽입 실패: {e}")
            raise
    
    def insert_images(self, merged_data):
        """이미지 데이터 삽입"""
        try:
            with self.conn.cursor() as cursor:
                for product_id, product_info in merged_data.items():
                    # CSV의 이미지 정보
                    if product_info.get('image_url') and product_info.get('image_path'):
                        cursor.execute("""
                            INSERT INTO product_images (product_id, image_filename, image_path, image_url)
                            VALUES (%s, %s, %s, %s)
                        """, (
                            product_id,
                            os.path.basename(product_info['image_path']),
                            product_info['image_path'],
                            product_info['image_url']
                        ))
                    
                    # 이미지 폴더의 추가 이미지들
                    for image_info in product_info.get('images', []):
                        cursor.execute("""
                            INSERT INTO product_images (product_id, image_filename, image_path)
                            VALUES (%s, %s, %s)
                        """, (
                            product_id,
                            image_info['filename'],
                            image_info['path']
                        ))
            
            logger.info("이미지 데이터가 성공적으로 삽입되었습니다.")
            
        except Exception as e:
            logger.error(f"이미지 데이터 삽입 실패: {e}")
            raise
    
    def initialize_database(self):
        """전체 데이터베이스 초기화"""
        try:
            logger.info("=== 완전한 PostgreSQL 패션 추천 시스템 초기화 시작 ===")
            
            # 1. 데이터베이스 연결
            if not self.connect():
                return False
            
            # 2. 테이블 생성
            self.create_tables()
            
            # 3. 데이터 로드
            logger.info("데이터 소스 로딩 중...")
            csv_data = self.load_csv_data()
            json_data = self.load_json_data()
            image_data = self.scan_image_files()
            
            # 4. 데이터 통합
            logger.info("데이터 통합 중...")
            merged_data = self.merge_data(csv_data, json_data, image_data)
            
            # 5. 데이터 삽입
            logger.info("데이터베이스에 데이터 삽입 중...")
            self.insert_products(merged_data)
            self.insert_sizes(json_data)
            self.insert_reviews(json_data)
            self.insert_style_keywords(json_data)
            self.insert_images(merged_data)
            
            logger.info("=== 완전한 PostgreSQL 패션 추천 시스템 초기화 완료 ===")
            return True
            
        except Exception as e:
            logger.error(f"데이터베이스 초기화 실패: {e}")
            return False
        finally:
            if self.conn:
                self.conn.close()

def main():
    """메인 실행 함수"""
    # 데이터베이스 설정
    db_config = {
        'host': 'localhost',
        'port': 5432,
        'database': 'fashion_recommendation',
        'user': 'postgres',
        'password': 'postgres'
    }
    
    # 초기화 실행
    initializer = CompletePostgreSQLInitializer(db_config)
    success = initializer.initialize_database()
    
    if success:
        print("\n✅ 완전한 PostgreSQL 패션 추천 시스템이 성공적으로 초기화되었습니다!")
        print("📊 데이터 소스:")
        print("   - CSV: 상품 기본 정보 (가격, 브랜드, 카테고리)")
        print("   - JSON: 상품 상세 정보 (리뷰, 사이즈, 스타일 키워드)")
        print("   - 이미지: 상품 이미지 파일들")
        print("\n🔍 데이터 확인을 위해 check_complete_data.py를 실행하세요.")
    else:
        print("\n❌ 데이터베이스 초기화에 실패했습니다.")

if __name__ == "__main__":
    main() 