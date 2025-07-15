import json
import re
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import Dict, Any, Optional, List
from datetime import datetime

def get_connection():
    """PostgreSQL 연결"""
    return psycopg2.connect(
        host='localhost',
        database='fashion_recommendation',
        user='postgres',
        password='postgres'
    )

def create_product_reviews_table():
    """정규화된 product_reviews 테이블 생성"""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # 기존 테이블 삭제 (있다면)
        cursor.execute("DROP TABLE IF EXISTS product_reviews")
        
        # 새 테이블 생성 (정규화된 구조)
        cursor.execute("""
            CREATE TABLE product_reviews (
                id SERIAL PRIMARY KEY,
                product_id INTEGER NOT NULL,
                review_index INTEGER NOT NULL,
                rating DECIMAL(3,1),  -- 평점 (예: 4.9)
                content TEXT,         -- 리뷰 내용
                likes INTEGER DEFAULT 0,  -- 좋아요 수
                comments INTEGER DEFAULT 0, -- 댓글 수
                user_name VARCHAR(100),    -- 작성자
                review_date VARCHAR(20),   -- 작성일
                purchase_info TEXT,        -- 구매 정보 (성별, 키, 몸무게)
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(product_id, review_index)
            )
        """)
        
        # 인덱스 생성
        cursor.execute("CREATE INDEX idx_product_reviews_product_id ON product_reviews(product_id)")
        cursor.execute("CREATE INDEX idx_product_reviews_rating ON product_reviews(rating)")
        cursor.execute("CREATE INDEX idx_product_reviews_user ON product_reviews(user_name)")
        
        conn.commit()
        print("✅ 정규화된 product_reviews 테이블 생성 완료")
        
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

def parse_rating(rating_str: str) -> Optional[float]:
    """평점 문자열을 float로 변환"""
    try:
        return float(rating_str)
    except (ValueError, TypeError):
        return None

def insert_review_data():
    """JSON에서 정규화된 리뷰 데이터 적재"""
    print("🔄 정규화된 리뷰 데이터 적재 시작...")
    
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # JSON 파일 로드
        with open('data/merged_all_data.json', 'r', encoding='utf-8') as f:
            json_data = json.load(f)
        
        success_count = 0
        error_count = 0
        total_review_records = 0
        
        for item in json_data:
            try:
                # product_id 추출
                url = item.get('url', '')
                product_id = extract_product_id_from_url(url)
                
                if not product_id:
                    continue
                
                # 리뷰 정보 처리
                review_info = item.get('review_info', {})
                if not review_info or not isinstance(review_info, dict):
                    continue
                
                # 평점 정보
                rating = parse_rating(review_info.get('rating', ''))
                
                # 개별 리뷰들 처리
                reviews = review_info.get('reviews', [])
                if not isinstance(reviews, list):
                    continue
                
                for review in reviews:
                    if not isinstance(review, dict):
                        continue
                    
                    try:
                        cursor.execute("""
                            INSERT INTO product_reviews (
                                product_id, review_index, rating, content, 
                                likes, comments, user_name, review_date, purchase_info
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (product_id, review_index) DO UPDATE SET
                                rating = EXCLUDED.rating,
                                content = EXCLUDED.content,
                                likes = EXCLUDED.likes,
                                comments = EXCLUDED.comments,
                                user_name = EXCLUDED.user_name,
                                review_date = EXCLUDED.review_date,
                                purchase_info = EXCLUDED.purchase_info,
                                updated_at = CURRENT_TIMESTAMP
                        """, (
                            product_id,
                            review.get('index'),
                            rating,
                            review.get('content', ''),
                            review.get('likes', 0),
                            review.get('comments', 0),
                            review.get('user', ''),
                            review.get('date', ''),
                            review.get('purchase_info', '')
                        ))
                        total_review_records += 1
                        
                    except Exception as e:
                        print(f"❌ 리뷰 {review.get('index', 'unknown')} 처리 오류: {e}")
                        continue
                
                success_count += 1
                
            except Exception as e:
                error_count += 1
                print(f"❌ 상품 {product_id if 'product_id' in locals() else 'unknown'} 처리 오류: {e}")
                continue
        
        conn.commit()
        print(f"✅ 정규화된 리뷰 데이터 적재 완료: {success_count}개 상품 성공, {error_count}개 실패")
        print(f"📊 총 {total_review_records}개의 리뷰 레코드가 저장되었습니다.")
        
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
        cursor.execute("SELECT COUNT(*) FROM product_reviews")
        total_count = cursor.fetchone()[0]
        print(f"총 리뷰 레코드: {total_count}개")
        
        # 상품별 리뷰 개수 확인
        cursor.execute("""
            SELECT product_id, COUNT(*) as review_count 
            FROM product_reviews 
            GROUP BY product_id 
            ORDER BY review_count DESC 
            LIMIT 5
        """)
        
        print("\n상품별 리뷰 개수 (상위 5개):")
        for product_id, review_count in cursor.fetchall():
            print(f"  Product ID {product_id}: {review_count}개 리뷰")
        
        # 평점 분포 확인
        cursor.execute("""
            SELECT rating, COUNT(*) as count
            FROM product_reviews 
            WHERE rating IS NOT NULL
            GROUP BY rating 
            ORDER BY rating
        """)
        
        print("\n평점 분포:")
        for rating, count in cursor.fetchall():
            print(f"  {rating}점: {count}개")
        
        # 샘플 데이터 확인
        cursor.execute("""
            SELECT product_id, review_index, rating, content, user_name, review_date, likes
            FROM product_reviews 
            WHERE product_id IN (
                SELECT DISTINCT product_id FROM product_reviews LIMIT 3
            )
            ORDER BY product_id, review_index
            LIMIT 10
        """)
        
        print("\n샘플 데이터:")
        current_product = None
        for row in cursor.fetchall():
            product_id, review_index, rating, content, user_name, review_date, likes = row
            if current_product != product_id:
                print(f"\nProduct ID {product_id}:")
                current_product = product_id
            print(f"  리뷰 {review_index}: {rating}점, 작성자: {user_name}, 좋아요: {likes}")
            print(f"    내용: {content[:100]}...")
        
    except Exception as e:
        print(f"❌ 데이터 확인 오류: {e}")
    finally:
        cursor.close()
        conn.close()

def main():
    """메인 실행 함수"""
    print("🚀 정규화된 product_reviews 테이블 생성 및 데이터 적재 시작...")
    
    # 1. 테이블 생성
    create_product_reviews_table()
    
    # 2. 데이터 적재
    insert_review_data()
    
    # 3. 데이터 확인
    verify_data()
    
    print("🎉 정규화된 product_reviews 테이블 생성 및 데이터 적재 완료!")

if __name__ == "__main__":
    main() 