import json
import re
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import Dict, Any, Optional, List

def get_connection():
    """PostgreSQL 연결"""
    return psycopg2.connect(
        host='localhost',
        database='fashion_recommendation',
        user='postgres',
        password='postgres'
    )

def create_product_style_keywords_table():
    """정규화된 product_style_keywords 테이블 생성"""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # 기존 테이블 삭제 (있다면)
        cursor.execute("DROP TABLE IF EXISTS product_style_keywords")
        
        # 새 테이블 생성 (정규화된 구조)
        cursor.execute("""
            CREATE TABLE product_style_keywords (
                id SERIAL PRIMARY KEY,
                product_id INTEGER NOT NULL,
                keyword VARCHAR(100) NOT NULL,
                keyword_order INTEGER,  -- 태그 순서
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(product_id, keyword)
            )
        """)
        
        # 인덱스 생성
        cursor.execute("CREATE INDEX idx_product_style_keywords_product_id ON product_style_keywords(product_id)")
        cursor.execute("CREATE INDEX idx_product_style_keywords_keyword ON product_style_keywords(keyword)")
        cursor.execute("CREATE INDEX idx_product_style_keywords_order ON product_style_keywords(keyword_order)")
        
        conn.commit()
        print("✅ 정규화된 product_style_keywords 테이블 생성 완료")
        
    except Exception as e:
        print(f"❌ 테이블 생성 오류: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

def extract_product_id_from_url(url: str) -> Optional[int]:
    """URL에서 product_id 추출"""
    try:
        if not url:
            return None
        match = re.search(r'/products/(\d+)', url)
        return int(match.group(1)) if match else None
    except Exception:
        return None

def clean_keyword(keyword: str) -> str:
    """키워드 정리 (공백 제거, 길이 제한 등)"""
    if not keyword:
        return ""
    
    # 공백 제거 및 길이 제한
    cleaned = keyword.strip()
    if len(cleaned) > 100:
        cleaned = cleaned[:100]
    
    return cleaned

def insert_style_keywords_data():
    """JSON에서 정규화된 스타일 키워드 데이터 적재"""
    print("🔄 정규화된 스타일 키워드 데이터 적재 시작...")
    
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # JSON 파일 로드
        with open('data/merged_all_data.json', 'r', encoding='utf-8') as f:
            json_data = json.load(f)
        
        success_count = 0
        error_count = 0
        total_keyword_records = 0
        
        for item in json_data:
            try:
                # product_id 추출
                url = item.get('url', '')
                product_id = extract_product_id_from_url(url)
                
                if not product_id:
                    continue
                
                # 태그 정보 처리
                tags = item.get('tags', [])
                if not tags or not isinstance(tags, list):
                    continue
                
                # 각 태그를 개별 행으로 삽입
                for order, tag in enumerate(tags, 1):
                    if not tag or not isinstance(tag, str):
                        continue
                    
                    cleaned_keyword = clean_keyword(tag)
                    if not cleaned_keyword:
                        continue
                    
                    try:
                        cursor.execute("""
                            INSERT INTO product_style_keywords (
                                product_id, keyword, keyword_order
                            ) VALUES (%s, %s, %s)
                            ON CONFLICT (product_id, keyword) DO UPDATE SET
                                keyword_order = EXCLUDED.keyword_order,
                                created_at = CURRENT_TIMESTAMP
                        """, (
                            product_id,
                            cleaned_keyword,
                            order
                        ))
                        total_keyword_records += 1
                        
                    except Exception as e:
                        print(f"❌ 키워드 '{cleaned_keyword}' 처리 오류: {e}")
                        continue
                
                success_count += 1
                
            except Exception as e:
                error_count += 1
                print(f"❌ 상품 {product_id if 'product_id' in locals() else 'unknown'} 처리 오류: {e}")
                continue
        
        conn.commit()
        print(f"✅ 정규화된 스타일 키워드 데이터 적재 완료: {success_count}개 상품 성공, {error_count}개 실패")
        print(f"📊 총 {total_keyword_records}개의 키워드 레코드가 저장되었습니다.")
        
    except Exception as e:
        print(f"❌ 데이터 적재 오류: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

def verify_data():
    """적재된 데이터 확인"""
    print("\n🔍 적재된 데이터 확인...")
    
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # 전체 개수 확인
        cursor.execute("SELECT COUNT(*) FROM product_style_keywords")
        total_count = cursor.fetchone()[0]
        print(f"총 키워드 레코드: {total_count}개")
        
        # 상품별 키워드 개수 확인
        cursor.execute("""
            SELECT product_id, COUNT(*) as keyword_count 
            FROM product_style_keywords 
            GROUP BY product_id 
            ORDER BY keyword_count DESC 
            LIMIT 5
        """)
        
        print("\n상품별 키워드 개수 (상위 5개):")
        for product_id, keyword_count in cursor.fetchall():
            print(f"  Product ID {product_id}: {keyword_count}개 키워드")
        
        # 가장 많이 사용된 키워드 확인
        cursor.execute("""
            SELECT keyword, COUNT(*) as usage_count
            FROM product_style_keywords 
            GROUP BY keyword 
            ORDER BY usage_count DESC 
            LIMIT 10
        """)
        
        print("\n가장 많이 사용된 키워드 (상위 10개):")
        for keyword, usage_count in cursor.fetchall():
            print(f"  {keyword}: {usage_count}개 상품")
        
        # 샘플 데이터 확인
        cursor.execute("""
            SELECT product_id, keyword, keyword_order
            FROM product_style_keywords 
            WHERE product_id IN (
                SELECT DISTINCT product_id FROM product_style_keywords LIMIT 3
            )
            ORDER BY product_id, keyword_order
        """)
        
        print("\n샘플 데이터:")
        current_product = None
        for row in cursor.fetchall():
            product_id, keyword, keyword_order = row
            if current_product != product_id:
                print(f"\nProduct ID {product_id}:")
                current_product = product_id
            print(f"  {keyword_order}. {keyword}")
        
    except Exception as e:
        print(f"❌ 데이터 확인 오류: {e}")
    finally:
        cursor.close()
        conn.close()

def main():
    """메인 실행 함수"""
    print("🚀 정규화된 product_style_keywords 테이블 생성 및 데이터 적재 시작...")
    
    # 1. 테이블 생성
    create_product_style_keywords_table()
    
    # 2. 데이터 적재
    insert_style_keywords_data()
    
    # 3. 데이터 확인
    verify_data()
    
    print("🎉 정규화된 product_style_keywords 테이블 생성 및 데이터 적재 완료!")

if __name__ == "__main__":
    main() 