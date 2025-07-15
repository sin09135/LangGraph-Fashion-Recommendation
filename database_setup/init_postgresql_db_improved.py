import json
import re
from src.database.postgresql_manager import PostgreSQLManager
from src.utils.data_processor import MusinsaDataProcessor

def extract_product_id_from_url(url):
    """URL에서 product_id 추출"""
    match = re.search(r'/products/(\d+)', url)
    return match.group(1) if match else None

def create_improved_tables(pg_manager):
    """개선된 테이블 구조 생성"""
    with pg_manager.get_connection() as conn:
        with conn.cursor() as cursor:
            # 기존 테이블 삭제 (재생성)
            cursor.execute("DROP TABLE IF EXISTS sizes CASCADE")
            cursor.execute("DROP TABLE IF EXISTS reviews CASCADE")
            cursor.execute("DROP TABLE IF EXISTS style_keywords CASCADE")
            cursor.execute("DROP TABLE IF EXISTS products CASCADE")
            
            # 상품 테이블 (개선된 구조)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS products (
                    product_id VARCHAR(50) PRIMARY KEY,
                    product_name TEXT NOT NULL,
                    category VARCHAR(100),
                    sub_category VARCHAR(100),
                    brand VARCHAR(100),
                    price INTEGER,
                    rating DECIMAL(3,2) DEFAULT 0.00,
                    review_count INTEGER DEFAULT 0,
                    url TEXT,
                    image_url TEXT,
                    tags TEXT[],
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 사이즈 테이블 (새로 추가)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sizes (
                    id SERIAL PRIMARY KEY,
                    product_id VARCHAR(50) REFERENCES products(product_id) ON DELETE CASCADE,
                    size_label VARCHAR(20) NOT NULL,
                    total_length DECIMAL(5,2),
                    chest_width DECIMAL(5,2),
                    shoulder_width DECIMAL(5,2),
                    UNIQUE(product_id, size_label)
                )
            """)
            
            # 리뷰 테이블 (개선된 구조)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS reviews (
                    id SERIAL PRIMARY KEY,
                    product_id VARCHAR(50) REFERENCES products(product_id) ON DELETE CASCADE,
                    review_index INTEGER,
                    content TEXT,
                    rating DECIMAL(3,2),
                    likes INTEGER DEFAULT 0,
                    comments INTEGER DEFAULT 0,
                    user_name VARCHAR(100),
                    review_date VARCHAR(20),
                    purchase_info TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(product_id, review_index)
                )
            """)
            
            # 스타일 키워드 테이블
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS style_keywords (
                    id SERIAL PRIMARY KEY,
                    product_id VARCHAR(50) REFERENCES products(product_id) ON DELETE CASCADE,
                    keyword VARCHAR(100) NOT NULL,
                    weight DECIMAL(3,2) DEFAULT 1.00,
                    UNIQUE(product_id, keyword)
                )
            """)
            
            # 인덱스 생성
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_category ON products(category)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_brand ON products(brand)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_price ON products(price)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_rating ON products(rating)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_sizes_product_id ON sizes(product_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_reviews_product_id ON reviews(product_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_style_keywords_keyword ON style_keywords(keyword)")
            
            # 풀텍스트 검색 인덱스
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_products_name_search 
                ON products USING gin(to_tsvector('english', product_name))
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_reviews_content_search 
                ON reviews USING gin(to_tsvector('english', content))
            """)
            
            conn.commit()
            print("✅ 개선된 테이블 구조 생성 완료")

def load_and_insert_merged_data(pg_manager):
    """merged_all_data.json에서 데이터 로드 및 삽입"""
    print("📊 merged_all_data.json 로드 중...")
    
    with open('data/merged_all_data.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print(f"✅ {len(data)}개 상품 데이터 로드 완료")
    
    with pg_manager.get_connection() as conn:
        with conn.cursor() as cursor:
            products_inserted = 0
            sizes_inserted = 0
            reviews_inserted = 0
            tags_inserted = 0
            
            for item in data:
                # 1. product_id 추출
                product_id = extract_product_id_from_url(item.get('url', ''))
                if not product_id:
                    continue
                
                # 2. 상품 데이터 삽입
                product_name = item.get('product_name', '')
                categories = item.get('categories', [])
                category = categories[0] if categories else ''
                sub_category = categories[1] if len(categories) > 1 else ''
                
                # 브랜드 추출 (product_name에서 [브랜드명] 형태로 추출)
                brand_match = re.search(r'\[([^\]]+)\]', product_name)
                brand = brand_match.group(1) if brand_match else ''
                
                # 태그 처리
                tags = item.get('tags', [])
                tags_array = [tag.replace('#', '') for tag in tags] if tags else []
                
                # 리뷰 정보
                review_info = item.get('review_info', {})
                rating = float(review_info.get('rating', 0)) if review_info.get('rating') else 0.0
                review_count = int(review_info.get('count', 0)) if review_info.get('count') else 0
                
                cursor.execute("""
                    INSERT INTO products 
                    (product_id, product_name, category, sub_category, brand, 
                     rating, review_count, url, tags)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (product_id) DO UPDATE SET
                        product_name = EXCLUDED.product_name,
                        category = EXCLUDED.category,
                        sub_category = EXCLUDED.sub_category,
                        brand = EXCLUDED.brand,
                        rating = EXCLUDED.rating,
                        review_count = EXCLUDED.review_count,
                        url = EXCLUDED.url,
                        tags = EXCLUDED.tags,
                        updated_at = CURRENT_TIMESTAMP
                """, (
                    product_id, product_name, category, sub_category, brand,
                    rating, review_count, item.get('url', ''), tags_array
                ))
                products_inserted += 1
                
                # 3. 사이즈 데이터 삽입
                size_info = item.get('size_info', {})
                if size_info and 'headers' in size_info and 'rows' in size_info:
                    headers = size_info['headers']
                    rows = size_info['rows']
                    
                    for i, row in enumerate(rows):
                        if len(row) > 0 and row[0] != "사이즈를 직접 입력해주세요":
                            size_label = f"사이즈_{i+1}"
                            total_length = float(row[0]) if len(row) > 0 and row[0].replace('.', '').isdigit() else None
                            chest_width = float(row[1]) if len(row) > 1 and row[1].replace('.', '').isdigit() else None
                            shoulder_width = float(row[2]) if len(row) > 2 and row[2].replace('.', '').isdigit() else None
                            
                            cursor.execute("""
                                INSERT INTO sizes 
                                (product_id, size_label, total_length, chest_width, shoulder_width)
                                VALUES (%s, %s, %s, %s, %s)
                                ON CONFLICT (product_id, size_label) DO UPDATE SET
                                    total_length = EXCLUDED.total_length,
                                    chest_width = EXCLUDED.chest_width,
                                    shoulder_width = EXCLUDED.shoulder_width
                            """, (product_id, size_label, total_length, chest_width, shoulder_width))
                            sizes_inserted += 1
                
                # 4. 리뷰 데이터 삽입
                reviews = review_info.get('reviews', [])
                for review in reviews:
                    cursor.execute("""
                        INSERT INTO reviews 
                        (product_id, review_index, content, rating, likes, comments, 
                         user_name, review_date, purchase_info)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (product_id, review_index) DO UPDATE SET
                            content = EXCLUDED.content,
                            rating = EXCLUDED.rating,
                            likes = EXCLUDED.likes,
                            comments = EXCLUDED.comments,
                            user_name = EXCLUDED.user_name,
                            review_date = EXCLUDED.review_date,
                            purchase_info = EXCLUDED.purchase_info
                    """, (
                        product_id,
                        review.get('index', 0),
                        review.get('content', ''),
                        float(review.get('rating', 0)) if review.get('rating') else None,
                        review.get('likes', 0),
                        review.get('comments', 0),
                        review.get('user', ''),
                        review.get('date', ''),
                        review.get('purchase_info', '')
                    ))
                    reviews_inserted += 1
                
                # 5. 태그를 스타일 키워드로 삽입
                for tag in tags_array:
                    cursor.execute("""
                        INSERT INTO style_keywords (product_id, keyword)
                        VALUES (%s, %s)
                        ON CONFLICT (product_id, keyword) DO NOTHING
                    """, (product_id, tag))
                    tags_inserted += 1
            
            conn.commit()
            
            print(f"✅ 데이터 삽입 완료:")
            print(f"  - 상품: {products_inserted}개")
            print(f"  - 사이즈: {sizes_inserted}개")
            print(f"  - 리뷰: {reviews_inserted}개")
            print(f"  - 스타일 키워드: {tags_inserted}개")

def main():
    """개선된 PostgreSQL 초기화 및 데이터 적재"""
    print("=== 개선된 PostgreSQL 데이터베이스 초기화 시작 ===")
    
    # PostgreSQL 매니저 초기화
    pg_manager = PostgreSQLManager(
        host="localhost",
        port=5432,
        database="fashion_recommendation",
        user="postgres",
        password="password"
    )
    
    # 1. 개선된 테이블 구조 생성
    create_improved_tables(pg_manager)
    
    # 2. merged_all_data.json에서 데이터 로드 및 삽입
    load_and_insert_merged_data(pg_manager)
    
    # 3. 통계 정보 출력
    print("\n=== 데이터베이스 통계 ===")
    stats = pg_manager.get_statistics()
    print(f"총 상품 수: {stats.get('total_products', 0)}")
    print(f"총 리뷰 수: {stats.get('total_reviews', 0)}")
    print(f"총 스타일 키워드 수: {stats.get('total_style_keywords', 0)}")
    
    print("\n🎉 개선된 PostgreSQL 데이터베이스 초기화 완료!")

if __name__ == "__main__":
    main() 