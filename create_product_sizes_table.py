#!/usr/bin/env python3
"""
product_sizes 테이블 생성 및 JSON 사이즈 데이터 적재
"""

import psycopg2
import json
import re
from typing import Dict, Any, List, Optional

def get_connection():
    return psycopg2.connect(
        host='localhost',
        port=5432,
        database='fashion_recommendation',
        user='postgres',
        password='postgres'
    )

def create_product_sizes_table():
    """product_sizes 테이블 생성"""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # 기존 테이블 삭제 (있다면)
        cursor.execute("DROP TABLE IF EXISTS product_sizes")
        
        # 새 테이블 생성
        cursor.execute("""
            CREATE TABLE product_sizes (
                id SERIAL PRIMARY KEY,
                product_id INTEGER NOT NULL,
                size_data JSONB NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(product_id)
            )
        """)
        
        # 인덱스 생성
        cursor.execute("CREATE INDEX idx_product_sizes_product_id ON product_sizes(product_id)")
        
        conn.commit()
        print("✅ product_sizes 테이블 생성 완료")
        
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

def process_size_data(size_info: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """사이즈 데이터 처리"""
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
        
        # 사이즈 데이터 구성
        size_data = {
            'headers': headers,
            'sizes': []
        }
        
        for row in valid_rows:
            if len(row) >= len(headers):
                size_row = {}
                for i, header in enumerate(headers):
                    if i < len(row):
                        value = row[i]
                        # "-" 값은 None으로 처리
                        if value == "-":
                            size_row[header] = None
                        else:
                            size_row[header] = value
                size_data['sizes'].append(size_row)
        
        return size_data if size_data['sizes'] else None
        
    except Exception as e:
        print(f"사이즈 데이터 처리 오류: {e}")
        return None

def insert_size_data():
    """JSON에서 사이즈 데이터 적재"""
    print("🔄 사이즈 데이터 적재 시작...")
    
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # JSON 파일 로드
        with open('data/merged_all_data.json', 'r', encoding='utf-8') as f:
            json_data = json.load(f)
        
        success_count = 0
        error_count = 0
        
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
                
                processed_size_data = process_size_data(size_info)
                if not processed_size_data:
                    continue
                
                # 데이터베이스에 삽입
                cursor.execute("""
                    INSERT INTO product_sizes (product_id, size_data)
                    VALUES (%s, %s)
                    ON CONFLICT (product_id) DO UPDATE SET
                        size_data = EXCLUDED.size_data,
                        updated_at = CURRENT_TIMESTAMP
                """, (product_id, json.dumps(processed_size_data, ensure_ascii=False)))
                
                success_count += 1
                
            except Exception as e:
                error_count += 1
                print(f"❌ 상품 {product_id if 'product_id' in locals() else 'unknown'} 처리 오류: {e}")
                continue
        
        conn.commit()
        print(f"✅ 사이즈 데이터 적재 완료: {success_count}개 성공, {error_count}개 실패")
        
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
        print(f"총 사이즈 데이터: {total_count}개")
        
        # 샘플 데이터 확인
        cursor.execute("""
            SELECT product_id, size_data 
            FROM product_sizes 
            LIMIT 3
        """)
        
        samples = cursor.fetchall()
        for i, (product_id, size_data) in enumerate(samples, 1):
            print(f"\n샘플 {i} - Product ID: {product_id}")
            if size_data:
                print(f"사이즈 데이터: {json.dumps(size_data, indent=2, ensure_ascii=False)}")
            else:
                print("사이즈 데이터: None")
        
    except Exception as e:
        print(f"❌ 데이터 확인 오류: {e}")
    finally:
        cursor.close()
        conn.close()

def main():
    """메인 실행 함수"""
    print("🚀 product_sizes 테이블 생성 및 데이터 적재 시작...")
    
    # 1. 테이블 생성
    create_product_sizes_table()
    
    # 2. 데이터 적재
    insert_size_data()
    
    # 3. 데이터 확인
    verify_data()
    
    print("🎉 product_sizes 테이블 생성 및 데이터 적재 완료!")

if __name__ == "__main__":
    main() 