from src.database.postgresql_manager import PostgreSQLManager
import pandas as pd

def check_postgresql_data():
    """PostgreSQL에 적재된 데이터 확인"""
    
    print("=== PostgreSQL 데이터 적재 확인 ===")
    
    # PostgreSQL 매니저 초기화
    pg_manager = PostgreSQLManager(
        host="localhost",
        port=5432,
        database="fashion_recommendation",
        user="postgres",
        password="password"
    )
    
    # 1. 전체 통계 확인
    print("\n📊 전체 통계:")
    stats = pg_manager.get_statistics()
    print(f"총 상품 수: {stats.get('total_products', 0)}")
    print(f"총 리뷰 수: {stats.get('total_reviews', 0)}")
    print(f"총 스타일 키워드 수: {stats.get('total_style_keywords', 0)}")
    
    # 2. 샘플 상품 데이터 확인
    print("\n🛍️ 샘플 상품 데이터 (상위 5개):")
    with pg_manager.get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT product_id, product_name, category, brand_en, brand_kr, price, original_price, discount_rate
                FROM products 
                ORDER BY product_id 
                LIMIT 5
            """)
            products = cursor.fetchall()
            
            for product in products:
                print(f"ID: {product[0]}")
                print(f"  상품명: {product[1]}")
                print(f"  카테고리: {product[2]}")
                print(f"  브랜드: {product[3]} ({product[4]})")
                print(f"  가격: {product[5]:,}원" if product[5] else "  가격: 정보없음")
                print(f"  원가: {product[6]:,}원" if product[6] else "  원가: 정보없음")
                print(f"  할인율: {product[7]}%" if product[7] else "  할인율: 정보없음")
                print()
    
    # 3. 카테고리별 분포 확인
    print("📈 카테고리별 상품 분포:")
    with pg_manager.get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT category, COUNT(*) as count
                FROM products 
                WHERE category IS NOT NULL AND category != ''
                GROUP BY category 
                ORDER BY count DESC
                LIMIT 10
            """)
            categories = cursor.fetchall()
            
            for category in categories:
                print(f"  {category[0]}: {category[1]}개")
    
    # 4. 브랜드별 분포 확인
    print("\n🏷️ 브랜드별 상품 분포 (상위 10개):")
    with pg_manager.get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT brand_en, COUNT(*) as count
                FROM products 
                WHERE brand_en IS NOT NULL AND brand_en != ''
                GROUP BY brand_en 
                ORDER BY count DESC
                LIMIT 10
            """)
            brands = cursor.fetchall()
            
            for brand in brands:
                print(f"  {brand[0]}: {brand[1]}개")
    
    # 5. 가격대별 분포 확인
    print("\n💰 가격대별 분포:")
    with pg_manager.get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT price_group, COUNT(*) as count FROM (
                    SELECT
                        CASE
                            WHEN price < 10000 THEN '1만원 미만'
                            WHEN price < 30000 THEN '1-3만원'
                            WHEN price < 50000 THEN '3-5만원'
                            WHEN price < 100000 THEN '5-10만원'
                            ELSE '10만원 이상'
                        END as price_group
                    FROM products
                    WHERE price IS NOT NULL AND price > 0
                ) t
                GROUP BY price_group
                ORDER BY
                    CASE price_group
                        WHEN '1만원 미만' THEN 1
                        WHEN '1-3만원' THEN 2
                        WHEN '3-5만원' THEN 3
                        WHEN '5-10만원' THEN 4
                        ELSE 5
                    END
            """)
            price_ranges = cursor.fetchall()
            
            for price_range in price_ranges:
                print(f"  {price_range[0]}: {price_range[1]}개")
    
    # 6. SQL 검색 테스트
    print("\n🔍 SQL 검색 테스트:")
    
    # 가방 카테고리 검색
    print("  - '가방' 카테고리 검색 결과:")
    bags = pg_manager.search_products_sql(
        filters={'category': '가방'},
        limit=3
    )
    for product in bags:
        print(f"    • {product['product_name']} ({product['brand_en']})")
    
    # 저가 상품 검색
    print("  - 저가 상품 검색 결과 (5만원 미만):")
    cheap_products = pg_manager.search_products_sql(
        filters={'price_max': 50000},
        limit=3
    )
    for product in cheap_products:
        print(f"    • {product['product_name']} ({product['price']:,}원)")
    
    print("\n✅ PostgreSQL 데이터 확인 완료!")

if __name__ == "__main__":
    check_postgresql_data() 