import json
import re
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import Dict, Any, Optional, List

def get_connection():
    """PostgreSQL 연결"""
    return psycopg2.connect(
        host='localhost',
        database='fashion_recommendation',  # 기존 DB명으로 변경
        user='postgres',
        password='postgres'
    )

def create_product_sizes_table():
    """정규화된 product_sizes 테이블 생성"""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # 기존 테이블 삭제 (있다면)
        cursor.execute("DROP TABLE IF EXISTS product_sizes")
        
        # 새 테이블 생성 (정규화된 구조)
        cursor.execute("""
            CREATE TABLE product_sizes (
                id SERIAL PRIMARY KEY,
                product_id INTEGER NOT NULL,
                size_name VARCHAR(50),  -- 사이즈명 (S, M, L, XL 등)
                total_length DECIMAL(5,2),  -- 총장
                chest_width DECIMAL(5,2),   -- 가슴단면
                shoulder_width DECIMAL(5,2), -- 어깨너비
                sleeve_length DECIMAL(5,2),  -- 소매길이
                waist_width DECIMAL(5,2),    -- 허리단면
                hip_width DECIMAL(5,2),      -- 힙단면
                thigh_width DECIMAL(5,2),    -- 허벅지단면
                hem_width DECIMAL(5,2),      -- 밑단단면
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 인덱스 생성
        cursor.execute("CREATE INDEX idx_product_sizes_product_id ON product_sizes(product_id)")
        cursor.execute("CREATE INDEX idx_product_sizes_size_name ON product_sizes(size_name)")
        
        conn.commit()
        print("✅ 정규화된 product_sizes 테이블 생성 완료")
        
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

def determine_size_name(row_index: int, total_rows: int) -> str:
    """행 인덱스를 기반으로 사이즈명 추정"""
    # 일반적인 사이즈 순서
    size_names = ['XS', 'S', 'M', 'L', 'XL', 'XXL', 'XXXL', 'XXXXL']
    
    if row_index < len(size_names):
        return size_names[row_index]
    else:
        return f"SIZE_{row_index + 1}"

def process_size_data(size_info: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
    """사이즈 데이터 처리 - 정규화된 형태로 변환"""
    try:
        headers = size_info.get('headers', [])
        rows = size_info.get('rows', [])
        
        if not headers or not rows:
            return None
        
        # 첫 번째 행이 "사이즈를 직접 입력해주세요"인 경우 제외
        valid_rows = []
        for row in rows:
            if len(row) > 0 and not row[0].startswith('사이즈를 직접 입력'):
                valid_rows.append(row)
        
        if not valid_rows:
            return None
        
        # 정규화된 사이즈 데이터 생성
        normalized_sizes = []
        
        for i, row in enumerate(valid_rows):
            if len(row) >= len(headers):
                size_data = {
                    'size_name': determine_size_name(i, len(valid_rows)),
                    'total_length': None,
                    'chest_width': None,
                    'shoulder_width': None,
                    'sleeve_length': None,
                    'waist_width': None,
                    'hip_width': None,
                    'thigh_width': None,
                    'hem_width': None
                }
                
                # 헤더에 따라 값 매핑
                for j, header in enumerate(headers):
                    if j < len(row):
                        value = row[j]
                        
                        # "-" 값은 None으로 처리
                        if value == "-" or value == "":
                            continue
                        
                        # 숫자로 변환 가능한지 확인
                        try:
                            numeric_value = float(value)
                        except (ValueError, TypeError):
                            continue
                        
                        # 헤더에 따라 적절한 컬럼에 매핑
                        if '총장' in header:
                            size_data['total_length'] = numeric_value
                        elif '가슴' in header:
                            size_data['chest_width'] = numeric_value
                        elif '어깨' in header:
                            size_data['shoulder_width'] = numeric_value
                        elif '소매' in header:
                            size_data['sleeve_length'] = numeric_value
                        elif '허리' in header:
                            size_data['waist_width'] = numeric_value
                        elif '힙' in header:
                            size_data['hip_width'] = numeric_value
                        elif '허벅지' in header:
                            size_data['thigh_width'] = numeric_value
                        elif '밑단' in header:
                            size_data['hem_width'] = numeric_value
                
                normalized_sizes.append(size_data)
        
        return normalized_sizes if normalized_sizes else None
        
    except Exception as e:
        print(f"사이즈 데이터 처리 오류: {e}")
        return None

def insert_size_data():
    """JSON에서 정규화된 사이즈 데이터 적재"""
    print("🔄 정규화된 사이즈 데이터 적재 시작...")
    
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # JSON 파일 로드
        with open('data/merged_all_data.json', 'r', encoding='utf-8') as f:
            json_data = json.load(f)
        
        success_count = 0
        error_count = 0
        total_size_records = 0
        
        for item in json_data:
            try:
                # product_id 추출
                url = item.get('url', '')
                product_id = extract_product_id_from_url(url)
                
                if not product_id:
                    continue
                
                # 사이즈 정보 처리
                size_info = item.get('size_info', {})
                if not size_info:
                    continue
                
                normalized_sizes = process_size_data(size_info)
                if not normalized_sizes:
                    continue
                
                # 각 사이즈별로 개별 행 삽입
                for size_data in normalized_sizes:
                    cursor.execute("""
                        INSERT INTO product_sizes (
                            product_id, size_name, total_length, chest_width, 
                            shoulder_width, sleeve_length, waist_width, hip_width, 
                            thigh_width, hem_width
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        product_id,
                        size_data['size_name'],
                        size_data['total_length'],
                        size_data['chest_width'],
                        size_data['shoulder_width'],
                        size_data['sleeve_length'],
                        size_data['waist_width'],
                        size_data['hip_width'],
                        size_data['thigh_width'],
                        size_data['hem_width']
                    ))
                    total_size_records += 1
                
                success_count += 1
                
            except Exception as e:
                error_count += 1
                print(f"❌ 상품 {product_id if 'product_id' in locals() else 'unknown'} 처리 오류: {e}")
                continue
        
        conn.commit()
        print(f"✅ 정규화된 사이즈 데이터 적재 완료: {success_count}개 상품 성공, {error_count}개 실패")
        print(f"📊 총 {total_size_records}개의 사이즈 레코드가 저장되었습니다.")
        
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
        cursor.execute("SELECT COUNT(*) FROM product_sizes")
        total_count = cursor.fetchone()[0]
        print(f"총 사이즈 레코드: {total_count}개")
        
        # 상품별 사이즈 개수 확인
        cursor.execute("""
            SELECT product_id, COUNT(*) as size_count 
            FROM product_sizes 
            GROUP BY product_id 
            ORDER BY size_count DESC 
            LIMIT 5
        """)
        
        print("\n상품별 사이즈 개수 (상위 5개):")
        for product_id, size_count in cursor.fetchall():
            print(f"  Product ID {product_id}: {size_count}개 사이즈")
        
        # 샘플 데이터 확인
        cursor.execute("""
            SELECT product_id, size_name, total_length, chest_width, shoulder_width, sleeve_length
            FROM product_sizes 
            WHERE product_id IN (
                SELECT DISTINCT product_id FROM product_sizes LIMIT 3
            )
            ORDER BY product_id, 
                CASE size_name 
                    WHEN 'XS' THEN 1 WHEN 'S' THEN 2 WHEN 'M' THEN 3 
                    WHEN 'L' THEN 4 WHEN 'XL' THEN 5 WHEN 'XXL' THEN 6 
                    WHEN 'XXXL' THEN 7 ELSE 8 END
        """)
        
        print("\n샘플 데이터:")
        current_product = None
        rows = cursor.fetchall()
        for row in rows:
            product_id, size_name, total_length, chest_width, shoulder_width, sleeve_length = row
            if current_product != product_id:
                print(f"\nProduct ID {product_id}:")
                current_product = product_id
            print(f"  {size_name}: 총장={total_length}, 가슴={chest_width}, 어깨={shoulder_width}, 소매={sleeve_length}")
        
    except Exception as e:
        print(f"❌ 데이터 확인 오류: {e}")
    finally:
        cursor.close()
        conn.close()

def main():
    """메인 실행 함수"""
    print("🚀 정규화된 product_sizes 테이블 생성 및 데이터 적재 시작...")
    
    # 1. 테이블 생성
    create_product_sizes_table()
    
    # 2. 데이터 적재
    insert_size_data()
    
    # 3. 데이터 확인
    verify_data()
    
    print("🎉 정규화된 product_sizes 테이블 생성 및 데이터 적재 완료!")

if __name__ == "__main__":
    main() 