#!/usr/bin/env python3
"""
JSON 상세 데이터(사이즈, 리뷰, 스타일 키워드)를 PostgreSQL 상세 테이블에 안전하게 적재하는 스크립트
"""

import json
import psycopg2
from typing import Dict, Any, List, Optional
from datetime import datetime
import re

def get_connection():
    return psycopg2.connect(
        host='localhost',
        port=5432,
        database='fashion_recommendation',
        user='postgres',
        password='postgres'
    )

def safe_get(d: dict, key: str, default=None):
    v = d.get(key, default)
    if v is None:
        return default
    if isinstance(v, str) and v.strip() == '':
        return default
    return v

def extract_product_id_from_url(url: str) -> Optional[int]:
    try:
        if not url:
            return None
        match = re.search(r'/products/(\d+)', url)
        return int(match.group(1)) if match else None
    except Exception:
        return None

def insert_product_sizes(json_data: List[Dict[str, Any]]):
    print("🔄 사이즈 정보 적재 중...")
    conn = get_connection()
    cursor = conn.cursor()
    success, fail = 0, 0
    for item in json_data:
        try:
            url = safe_get(item, 'url', '')
            product_id = extract_product_id_from_url(str(url))
            if not product_id:
                continue
            size_info = item.get('size_info', {})
            headers = size_info.get('headers', [])
            rows = size_info.get('rows', [])
            if not headers or not rows:
                continue
            for row in rows:
                if len(row) >= len(headers):
                    size_data = {headers[i]: row[i] for i in range(len(headers)) if i < len(row)}
                    cursor.execute(
                        """
                        INSERT INTO product_sizes (product_id, size_data)
                        VALUES (%s, %s)
                        ON CONFLICT (product_id) DO UPDATE SET size_data = EXCLUDED.size_data
                        """,
                        (product_id, json.dumps(size_data, ensure_ascii=False))
                    )
                    success += 1
                    break  # 첫 번째 유효한 사이즈만 저장
        except Exception as e:
            fail += 1
            continue
    conn.commit()
    cursor.close()
    conn.close()
    print(f"✅ 사이즈 정보: {success}개 성공, {fail}개 실패")

def insert_product_reviews(json_data: List[Dict[str, Any]]):
    print("🔄 리뷰 정보 적재 중...")
    conn = get_connection()
    cursor = conn.cursor()
    success, fail = 0, 0
    for item in json_data:
        try:
            url = safe_get(item, 'url', '')
            product_id = extract_product_id_from_url(str(url))
            if not product_id:
                continue
            review_info = item.get('review_info', {})
            reviews = review_info.get('reviews', [])
            for review in reviews[:10]:  # 최대 10개만
                if isinstance(review, dict):
                    review_text = safe_get(review, 'text', '')
                    review_rating = safe_get(review, 'rating', None)
                    if review_text:
                        cursor.execute(
                            """
                            INSERT INTO product_reviews (product_id, review_text, rating, created_at)
                            VALUES (%s, %s, %s, %s)
                            """,
                            (product_id, review_text, float(review_rating) if review_rating else None, datetime.now())
                        )
                        success += 1
        except Exception as e:
            fail += 1
            continue
    conn.commit()
    cursor.close()
    conn.close()
    print(f"✅ 리뷰 정보: {success}개 성공, {fail}개 실패")

def insert_product_style_keywords(json_data: List[Dict[str, Any]]):
    print("🔄 스타일 키워드 적재 중...")
    conn = get_connection()
    cursor = conn.cursor()
    success, fail = 0, 0
    for item in json_data:
        try:
            url = safe_get(item, 'url', '')
            product_id = extract_product_id_from_url(str(url))
            if not product_id:
                continue
            tags = item.get('tags', [])
            if isinstance(tags, str):
                tags = [tags]
            if not tags:
                continue
            cursor.execute("DELETE FROM product_style_keywords WHERE product_id = %s", (product_id,))
            for tag in tags:
                if tag and tag.strip():
                    keyword = tag.strip('#').strip()
                    if keyword:
                        cursor.execute(
                            """
                            INSERT INTO product_style_keywords (product_id, keyword, created_at)
                            VALUES (%s, %s, %s)
                            """,
                            (product_id, keyword, datetime.now())
                        )
                        success += 1
        except Exception as e:
            fail += 1
            continue
    conn.commit()
    cursor.close()
    conn.close()
    print(f"✅ 스타일 키워드: {success}개 성공, {fail}개 실패")

def main():
    print("🚀 JSON 상세 데이터 적재 시작...")
    with open('data/merged_all_data.json', 'r', encoding='utf-8') as f:
        json_data = json.load(f)
    insert_product_sizes(json_data)
    insert_product_reviews(json_data)
    insert_product_style_keywords(json_data)
    print("🎉 상세 데이터 적재 완료!")

if __name__ == "__main__":
    main() 