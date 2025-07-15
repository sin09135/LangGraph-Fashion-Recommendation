import pandas as pd
import psycopg2
from psycopg2.extras import RealDictCursor
import re
from typing import Optional

def get_connection():
    """PostgreSQL 연결"""
    return psycopg2.connect(
        host='localhost',
        database='fashion_recommendation',
        user='postgres',
        password='postgres'
    )

def extract_product_id_from_url(url: str) -> Optional[int]:
    """URL에서 product_id 추출"""
    try:
        if not url:
            return None
        match = re.search(r'/products/(\d+)', url)
        return int(match.group(1)) if match else None
    except Exception:
        return None

def load_products_from_csv():
    """CSV 파일에서 상품 데이터를 products 테이블에 적재"""
    print("🔄 CSV 파일에서 상품 데이터 적재 시작...")
    
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # CSV 파일 로드
        df = pd.read_csv('data/musinsa_products_all_categories.csv')
        print(f"CSV 파일 로드 완료: {len(df)}개 행")
        
        # 컬럼명 확인
        print(f"CSV 컬럼: {list(df.columns)}")
        
        success_count = 0
        error_count = 0
        
        for index, row in df.iterrows():
            try:
                # product_id 추출
                product_url = row.get('product_url', '')
                product_id = extract_product_id_from_url(product_url)
                
                if not product_id:
                    print(f"❌ 행 {index}: product_id 추출 실패")
                    error_count += 1
                    continue
                
                # 데이터 삽입
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
                    product_id,
                    row.get('category', ''),
                    row.get('category_code', None),
                    row.get('brand_en', ''),
                    row.get('brand_kr', ''),
                    row.get('price', None),
                    row.get('original_price', None),
                    row.get('discount_rate', None),
                    product_url,
                    row.get('image_url', ''),
                    row.get('image_path', ''),
                    row.get('product_name', ''),
                    row.get('description', ''),
                    row.get('tags', []) if pd.notna(row.get('tags')) else []
                ))
                
                success_count += 1
                
                if success_count % 100 == 0:
                    print(f"진행 상황: {success_count}개 처리 완료")
                
            except Exception as e:
                error_count += 1
                print(f"❌ 행 {index} 처리 오류: {e}")
                continue
        
        conn.commit()
        print(f"✅ 상품 데이터 적재 완료: {success_count}개 성공, {error_count}개 실패")
        
    except Exception as e:
        print(f"❌ 데이터 적재 오류: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

def verify_products_data():
    """적재된 상품 데이터 확인"""
    print("\n🔍 적재된 상품 데이터 확인...")
    
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # 전체 개수 확인
        cursor.execute("SELECT COUNT(*) FROM products")
        total_count = cursor.fetchone()[0]
        print(f"총 상품 수: {total_count}개")
        
        # 카테고리별 분포
        cursor.execute("""
            SELECT category, COUNT(*) as count
            FROM products 
            GROUP BY category 
            ORDER BY count DESC
        """)
        
        print("\n카테고리별 상품 수:")
        for category, count in cursor.fetchall():
            print(f"  {category}: {count}개")
        
        # 브랜드별 분포 (상위 10개)
        cursor.execute("""
            SELECT brand_kr, COUNT(*) as count
            FROM products 
            WHERE brand_kr IS NOT NULL AND brand_kr != ''
            GROUP BY brand_kr 
            ORDER BY count DESC 
            LIMIT 10
        """)
        
        print("\n브랜드별 상품 수 (상위 10개):")
        for brand, count in cursor.fetchall():
            print(f"  {brand}: {count}개")
        
        # 샘플 데이터 확인
        cursor.execute("""
            SELECT product_id, product_name, brand_kr, category, price, image_url
            FROM products 
            LIMIT 5
        """)
        
        print("\n샘플 데이터:")
        for row in cursor.fetchall():
            product_id, product_name, brand_kr, category, price, image_url = row
            print(f"  ID: {product_id}, 이름: {product_name[:50]}...")
            print(f"    브랜드: {brand_kr}, 카테고리: {category}, 가격: {price}")
            print(f"    이미지: {image_url[:50] if image_url else 'None'}...")
            print()
        
    except Exception as e:
        print(f"❌ 데이터 확인 오류: {e}")
    finally:
        cursor.close()
        conn.close()

def main():
    """메인 실행 함수"""
    print("🚀 CSV 파일에서 상품 데이터 적재 시작...")
    
    # 1. 데이터 적재
    load_products_from_csv()
    
    # 2. 데이터 확인
    verify_products_data()
    
    print("🎉 상품 데이터 적재 완료!")

if __name__ == "__main__":
    main() 