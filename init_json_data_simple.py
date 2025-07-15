#!/usr/bin/env python3
"""
JSON 데이터를 PostgreSQL 데이터베이스에 안전하게 적재하는 간단한 스크립트
"""

import json
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import Dict, Any, List, Optional
import re
from datetime import datetime

def get_connection():
    """데이터베이스 연결"""
    return psycopg2.connect(
        host='localhost',
        port=5432,
        database='fashion_recommendation',
        user='postgres',
        password='postgres'
    )

def safe_get_value(data: Dict[str, Any], key: str, default=''):
    """안전하게 값을 가져오는 함수"""
    try:
        value = data.get(key, default)
        if value is None or value == '' or (isinstance(value, str) and value.strip() == ''):
            return default
        return str(value).strip()
    except Exception:
        return default

def extract_product_id_from_url(url: str) -> Optional[int]:
    """URL에서 product_id 추출"""
    try:
        if not url:
            return None
        match = re.search(r'/products/(\d+)', url)
        return int(match.group(1)) if match else None
    except Exception:
        return None

def extract_main_category(categories: List[str]) -> str:
    """메인 카테고리 추출"""
    if not categories:
        return ''
    
    # 첫 번째 카테고리가 메인 카테고리
    main_category = categories[0]
    
    # 카테고리 매핑
    category_mapping = {
        '상의': '상의',
        '하의': '바지', 
        '신발': '신발',
        '가방': '가방',
        '아우터': '아우터',
        '패션소품': '패션소품'
    }
    
    return category_mapping.get(main_category, main_category)

def extract_brand_from_categories(categories: List[str]) -> tuple:
    """카테고리에서 브랜드 정보 추출"""
    brand_en = ''
    brand_kr = ''
    
    if not categories:
        return brand_en, brand_kr
    
    # 마지막 카테고리가 브랜드일 가능성이 높음
    for category in reversed(categories):
        if category.startswith('(') and category.endswith(')'):
            brand_kr = category.strip('()')
            break
    
    return brand_en, brand_kr

def insert_products_from_json(json_data: List[Dict[str, Any]]):
    """JSON에서 상품 데이터 삽입"""
    print(f"🔄 {len(json_data)}개 상품 데이터 처리 중...")
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        success_count = 0
        error_count = 0
        
        for item in json_data:
            try:
                # product_id 추출
                url = safe_get_value(item, 'url')
                product_id = extract_product_id_from_url(url)
                
                if not product_id:
                    error_count += 1
                    continue
                
                # 카테고리 정보 처리
                categories = item.get('categories', [])
                if isinstance(categories, str):
                    categories = [categories]
                
                main_category = extract_main_category(categories)
                brand_en, brand_kr = extract_brand_from_categories(categories)
                
                # 기본 정보 삽입
                cursor.execute("""
                    INSERT INTO products 
                    (product_id, category, brand_en, brand_kr, product_url, product_name)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (product_id) DO UPDATE SET
                        category = EXCLUDED.category,
                        brand_en = EXCLUDED.brand_en,
                        brand_kr = EXCLUDED.brand_kr,
                        product_url = EXCLUDED.product_url,
                        product_name = EXCLUDED.product_name,
                        updated_at = CURRENT_TIMESTAMP
                """, (
                    product_id,
                    main_category,
                    brand_en,
                    brand_kr,
                    url,
                    safe_get_value(item, 'product_name')
                ))
                
                success_count += 1
                
            except Exception as e:
                error_count += 1
                print(f"❌ 상품 처리 오류 (ID: {product_id if 'product_id' in locals() else 'unknown'}): {e}")
                continue
        
        conn.commit()
        cursor.close()
        conn.close()
        print(f"✅ 상품 데이터 삽입 완료: {success_count}개 성공, {error_count}개 실패")
        
    except Exception as e:
        print(f"❌ 데이터베이스 오류: {e}")

def insert_style_keywords_from_json(json_data: List[Dict[str, Any]]):
    """JSON에서 스타일 키워드 삽입"""
    print("🔄 스타일 키워드 처리 중...")
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        success_count = 0
        error_count = 0
        
        for item in json_data:
            try:
                url = safe_get_value(item, 'url')
                product_id = extract_product_id_from_url(url)
                
                if not product_id:
                    continue
                
                tags = item.get('tags', [])
                if isinstance(tags, str):
                    tags = [tags]
                
                if not tags:
                    continue
                
                # 기존 키워드 삭제
                cursor.execute("DELETE FROM product_style_keywords WHERE product_id = %s", (product_id,))
                
                # 새로운 키워드 삽입
                for tag in tags:
                    if tag and tag.strip():
                        # # 제거하고 키워드만 추출
                        keyword = tag.strip('#').strip()
                        if keyword:
                            cursor.execute("""
                                INSERT INTO product_style_keywords 
                                (product_id, keyword, created_at)
                                VALUES (%s, %s, %s)
                            """, (product_id, keyword, datetime.now()))
                
                success_count += 1
                
            except Exception as e:
                error_count += 1
                continue
        
        conn.commit()
        cursor.close()
        conn.close()
        print(f"✅ 스타일 키워드 삽입 완료: {success_count}개 성공, {error_count}개 실패")
        
    except Exception as e:
        print(f"❌ 스타일 키워드 처리 오류: {e}")

def main():
    """메인 실행 함수"""
    print("🚀 JSON 데이터를 PostgreSQL에 적재 시작...")
    
    try:
        # JSON 파일 로드
        print("📂 JSON 파일 로드 중...")
        with open('data/merged_all_data.json', 'r', encoding='utf-8') as f:
            json_data = json.load(f)
        
        print(f"✅ JSON 파일 로드 완료: {len(json_data)}개 항목")
        
        # 1. 상품 기본 정보 삽입
        insert_products_from_json(json_data)
        
        # 2. 스타일 키워드 삽입
        insert_style_keywords_from_json(json_data)
        
        print("🎉 JSON 데이터 적재 완료!")
        
    except Exception as e:
        print(f"❌ 오류 발생: {e}")

if __name__ == "__main__":
    main() 