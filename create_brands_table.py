import psycopg2
from psycopg2.extras import RealDictCursor

def get_connection():
    """PostgreSQL 연결"""
    return psycopg2.connect(
        host='localhost',
        database='fashion_recommendation',
        user='postgres',
        password='postgres'
    )

def create_brands_table():
    """브랜드 테이블 생성"""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # 브랜드 테이블 생성
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS brands (
                brand_id SERIAL PRIMARY KEY,
                brand_en VARCHAR(100) UNIQUE NOT NULL,
                brand_kr VARCHAR(100) UNIQUE NOT NULL,
                brand_popularity INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 인덱스 생성
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_brands_brand_en ON brands(brand_en)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_brands_brand_kr ON brands(brand_kr)")
        
        conn.commit()
        print("✅ 브랜드 테이블 생성 완료")
        
    except Exception as e:
        print(f"❌ 브랜드 테이블 생성 오류: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

def add_brand_id_to_products():
    """products 테이블에 brand_id 컬럼 추가"""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # brand_id 컬럼 추가 (이미 있으면 무시)
        cursor.execute("""
            ALTER TABLE products 
            ADD COLUMN IF NOT EXISTS brand_id INTEGER REFERENCES brands(brand_id)
        """)
        
        conn.commit()
        print("✅ products 테이블에 brand_id 컬럼 추가 완료")
        
    except Exception as e:
        print(f"❌ brand_id 컬럼 추가 오류: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

def populate_brands_table():
    """기존 products 테이블에서 브랜드 정보를 추출하여 brands 테이블에 적재"""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # 기존 브랜드 데이터 삭제 (재실행 시)
        cursor.execute("DELETE FROM brands")
        
        # products 테이블에서 고유한 브랜드 정보 추출
        cursor.execute("""
            SELECT DISTINCT brand_en, brand_kr, COUNT(*) as product_count
            FROM products 
            WHERE brand_en IS NOT NULL AND brand_en != ''
            GROUP BY brand_en, brand_kr
            ORDER BY product_count DESC
        """)
        
        brands_data = cursor.fetchall()
        
        # 브랜드 데이터 삽입
        for brand_en, brand_kr, product_count in brands_data:
            cursor.execute("""
                INSERT INTO brands (brand_en, brand_kr, brand_popularity)
                VALUES (%s, %s, %s)
            """, (brand_en, brand_kr, product_count))
        
        conn.commit()
        print(f"✅ 브랜드 데이터 적재 완료: {len(brands_data)}개 브랜드")
        
    except Exception as e:
        print(f"❌ 브랜드 데이터 적재 오류: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

def update_products_brand_id():
    """products 테이블의 brand_id 업데이트"""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # products 테이블의 brand_id 업데이트
        cursor.execute("""
            UPDATE products 
            SET brand_id = b.brand_id
            FROM brands b
            WHERE products.brand_en = b.brand_en
        """)
        
        updated_count = cursor.rowcount
        conn.commit()
        print(f"✅ products 테이블 brand_id 업데이트 완료: {updated_count}개 상품")
        
    except Exception as e:
        print(f"❌ brand_id 업데이트 오류: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

def verify_brands_data():
    """브랜드 데이터 확인"""
    print("\n🔍 브랜드 데이터 확인...")
    
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # 전체 브랜드 수 확인
        cursor.execute("SELECT COUNT(*) FROM brands")
        total_brands = cursor.fetchone()[0]
        print(f"총 브랜드 수: {total_brands}개")
        
        # 인기 브랜드 (상위 10개)
        cursor.execute("""
            SELECT brand_kr, brand_en, brand_popularity
            FROM brands 
            ORDER BY brand_popularity DESC 
            LIMIT 10
        """)
        
        print("\n인기 브랜드 (상위 10개):")
        for brand_kr, brand_en, popularity in cursor.fetchall():
            print(f"  {brand_kr} ({brand_en}): {popularity}개 상품")
        
        # brand_id가 설정된 상품 수 확인
        cursor.execute("""
            SELECT COUNT(*) as with_brand_id, 
                   (SELECT COUNT(*) FROM products) as total_products
            FROM products 
            WHERE brand_id IS NOT NULL
        """)
        
        with_brand_id, total_products = cursor.fetchone()
        print(f"\nbrand_id 설정된 상품: {with_brand_id}/{total_products}개")
        
        # 샘플 데이터 확인
        cursor.execute("""
            SELECT p.product_id, p.product_name, p.brand_kr, b.brand_id, b.brand_popularity
            FROM products p
            LEFT JOIN brands b ON p.brand_id = b.brand_id
            LIMIT 5
        """)
        
        print("\n샘플 데이터:")
        for row in cursor.fetchall():
            product_id, product_name, brand_kr, brand_id, popularity = row
            print(f"  상품 ID {product_id}: {product_name[:30]}...")
            print(f"    브랜드: {brand_kr}, brand_id: {brand_id}, 인기도: {popularity}")
            print()
        
    except Exception as e:
        print(f"❌ 데이터 확인 오류: {e}")
    finally:
        cursor.close()
        conn.close()

def main():
    """메인 실행 함수"""
    print("🚀 브랜드 테이블 생성 및 데이터 마이그레이션 시작...")
    
    # 1. 브랜드 테이블 생성
    create_brands_table()
    
    # 2. products 테이블에 brand_id 컬럼 추가
    add_brand_id_to_products()
    
    # 3. 브랜드 데이터 적재
    populate_brands_table()
    
    # 4. products 테이블의 brand_id 업데이트
    update_products_brand_id()
    
    # 5. 데이터 확인
    verify_brands_data()
    
    print("🎉 브랜드 테이블 생성 및 데이터 마이그레이션 완료!")

if __name__ == "__main__":
    main() 