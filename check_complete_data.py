#!/usr/bin/env python3
"""
완전한 PostgreSQL 패션 추천 시스템 데이터 확인
3개 데이터 소스 통합 상태 검증
"""

import psycopg2
from psycopg2.extras import RealDictCursor
import pandas as pd
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class CompleteDataChecker:
    def __init__(self, db_config):
        self.db_config = db_config
        self.conn = None
        
    def connect(self):
        """데이터베이스 연결"""
        try:
            self.conn = psycopg2.connect(**self.db_config)
            logger.info("PostgreSQL 데이터베이스에 성공적으로 연결되었습니다.")
            return True
        except Exception as e:
            logger.error(f"데이터베이스 연결 실패: {e}")
            return False
    
    def get_basic_stats(self):
        """기본 통계 정보"""
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cursor:
                # 전체 상품 수
                cursor.execute("SELECT COUNT(*) as total_products FROM products")
                total_products = cursor.fetchone()['total_products']
                
                # 카테고리별 분포
                cursor.execute("""
                    SELECT category, COUNT(*) as count 
                    FROM products 
                    GROUP BY category 
                    ORDER BY count DESC
                """)
                category_distribution = cursor.fetchall()
                
                # 브랜드별 분포 (상위 10개)
                cursor.execute("""
                    SELECT brand_en, COUNT(*) as count 
                    FROM products 
                    GROUP BY brand_en 
                    ORDER BY count DESC 
                    LIMIT 10
                """)
                brand_distribution = cursor.fetchall()
                
                # 가격대별 분포
                cursor.execute("""
                    SELECT 
                        CASE 
                            WHEN price < 50000 THEN '5만원 미만'
                            WHEN price < 100000 THEN '5-10만원'
                            WHEN price < 200000 THEN '10-20만원'
                            WHEN price < 500000 THEN '20-50만원'
                            ELSE '50만원 이상'
                        END as price_range,
                        COUNT(*) as count
                    FROM products 
                    GROUP BY 
                        CASE 
                            WHEN price < 50000 THEN '5만원 미만'
                            WHEN price < 100000 THEN '5-10만원'
                            WHEN price < 200000 THEN '10-20만원'
                            WHEN price < 500000 THEN '20-50만원'
                            ELSE '50만원 이상'
                        END
                    ORDER BY 
                        CASE price_range
                            WHEN '5만원 미만' THEN 1
                            WHEN '5-10만원' THEN 2
                            WHEN '10-20만원' THEN 3
                            WHEN '20-50만원' THEN 4
                            ELSE 5
                        END
                """)
                price_distribution = cursor.fetchall()
                
                return {
                    'total_products': total_products,
                    'category_distribution': category_distribution,
                    'brand_distribution': brand_distribution,
                    'price_distribution': price_distribution
                }
                
        except Exception as e:
            logger.error(f"기본 통계 조회 실패: {e}")
            return None
    
    def get_detailed_stats(self):
        """상세 통계 정보"""
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cursor:
                # 사이즈 데이터 수
                cursor.execute("SELECT COUNT(*) as total_sizes FROM product_sizes")
                total_sizes = cursor.fetchone()['total_sizes']
                
                # 리뷰 데이터 수
                cursor.execute("SELECT COUNT(*) as total_reviews FROM product_reviews")
                total_reviews = cursor.fetchone()['total_reviews']
                
                # 스타일 키워드 수
                cursor.execute("SELECT COUNT(*) as total_keywords FROM product_style_keywords")
                total_keywords = cursor.fetchone()['total_keywords']
                
                # 이미지 데이터 수
                cursor.execute("SELECT COUNT(*) as total_images FROM product_images")
                total_images = cursor.fetchone()['total_images']
                
                # 태그가 있는 상품 수
                cursor.execute("SELECT COUNT(*) as products_with_tags FROM products WHERE tags IS NOT NULL AND array_length(tags, 1) > 0")
                products_with_tags = cursor.fetchone()['products_with_tags']
                
                # 이미지가 있는 상품 수
                cursor.execute("""
                    SELECT COUNT(DISTINCT p.product_id) as products_with_images 
                    FROM products p 
                    JOIN product_images pi ON p.product_id = pi.product_id
                """)
                products_with_images = cursor.fetchone()['products_with_images']
                
                return {
                    'total_sizes': total_sizes,
                    'total_reviews': total_reviews,
                    'total_keywords': total_keywords,
                    'total_images': total_images,
                    'products_with_tags': products_with_tags,
                    'products_with_images': products_with_images
                }
                
        except Exception as e:
            logger.error(f"상세 통계 조회 실패: {e}")
            return None
    
    def get_sample_products(self, limit=5):
        """샘플 상품 데이터"""
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT 
                        p.product_id,
                        p.category,
                        p.brand_en,
                        p.brand_kr,
                        p.product_name,
                        p.price,
                        p.original_price,
                        p.discount_rate,
                        p.tags,
                        COUNT(ps.id) as size_count,
                        COUNT(pr.id) as review_count,
                        COUNT(psk.id) as keyword_count,
                        COUNT(pi.id) as image_count
                    FROM products p
                    LEFT JOIN product_sizes ps ON p.product_id = ps.product_id
                    LEFT JOIN product_reviews pr ON p.product_id = pr.product_id
                    LEFT JOIN product_style_keywords psk ON p.product_id = psk.product_id
                    LEFT JOIN product_images pi ON p.product_id = pi.product_id
                    GROUP BY p.product_id, p.category, p.brand_en, p.brand_kr, p.product_name, p.price, p.original_price, p.discount_rate, p.tags
                    ORDER BY p.product_id
                    LIMIT %s
                """, (limit,))
                
                return cursor.fetchall()
                
        except Exception as e:
            logger.error(f"샘플 상품 조회 실패: {e}")
            return []
    
    def test_sql_search(self):
        """SQL 검색 테스트"""
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cursor:
                # 1. 카테고리별 검색
                cursor.execute("""
                    SELECT product_id, product_name, price, brand_en 
                    FROM products 
                    WHERE category = '가방' 
                    ORDER BY price DESC 
                    LIMIT 3
                """)
                category_search = cursor.fetchall()
                
                # 2. 브랜드별 검색
                cursor.execute("""
                    SELECT product_id, product_name, price, category 
                    FROM products 
                    WHERE brand_en = 'musinsastandard' 
                    ORDER BY price 
                    LIMIT 3
                """)
                brand_search = cursor.fetchall()
                
                # 3. 가격대별 검색
                cursor.execute("""
                    SELECT product_id, product_name, price, brand_en 
                    FROM products 
                    WHERE price BETWEEN 50000 AND 100000 
                    ORDER BY price 
                    LIMIT 3
                """)
                price_search = cursor.fetchall()
                
                # 4. 태그 검색
                cursor.execute("""
                    SELECT product_id, product_name, tags 
                    FROM products 
                    WHERE tags && ARRAY['레더', '크로스백'] 
                    LIMIT 3
                """)
                tag_search = cursor.fetchall()
                
                # 5. 할인율 검색
                cursor.execute("""
                    SELECT product_id, product_name, price, original_price, discount_rate 
                    FROM products 
                    WHERE discount_rate > 20 
                    ORDER BY discount_rate DESC 
                    LIMIT 3
                """)
                discount_search = cursor.fetchall()
                
                return {
                    'category_search': category_search,
                    'brand_search': brand_search,
                    'price_search': price_search,
                    'tag_search': tag_search,
                    'discount_search': discount_search
                }
                
        except Exception as e:
            logger.error(f"SQL 검색 테스트 실패: {e}")
            return {}
    
    def check_data_integrity(self):
        """데이터 무결성 검사"""
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cursor:
                # 1. 고아 레코드 검사
                cursor.execute("""
                    SELECT COUNT(*) as orphan_sizes 
                    FROM product_sizes ps 
                    LEFT JOIN products p ON ps.product_id = p.product_id 
                    WHERE p.product_id IS NULL
                """)
                orphan_sizes = cursor.fetchone()['orphan_sizes']
                
                cursor.execute("""
                    SELECT COUNT(*) as orphan_reviews 
                    FROM product_reviews pr 
                    LEFT JOIN products p ON pr.product_id = p.product_id 
                    WHERE p.product_id IS NULL
                """)
                orphan_reviews = cursor.fetchone()['orphan_reviews']
                
                cursor.execute("""
                    SELECT COUNT(*) as orphan_keywords 
                    FROM product_style_keywords psk 
                    LEFT JOIN products p ON psk.product_id = p.product_id 
                    WHERE p.product_id IS NULL
                """)
                orphan_keywords = cursor.fetchone()['orphan_keywords']
                
                cursor.execute("""
                    SELECT COUNT(*) as orphan_images 
                    FROM product_images pi 
                    LEFT JOIN products p ON pi.product_id = p.product_id 
                    WHERE p.product_id IS NULL
                """)
                orphan_images = cursor.fetchone()['orphan_images']
                
                # 2. 중복 데이터 검사
                cursor.execute("""
                    SELECT COUNT(*) as duplicate_keywords 
                    FROM (
                        SELECT product_id, keyword, COUNT(*) 
                        FROM product_style_keywords 
                        GROUP BY product_id, keyword 
                        HAVING COUNT(*) > 1
                    ) as duplicates
                """)
                duplicate_keywords = cursor.fetchone()['duplicate_keywords']
                
                return {
                    'orphan_sizes': orphan_sizes,
                    'orphan_reviews': orphan_reviews,
                    'orphan_keywords': orphan_keywords,
                    'orphan_images': orphan_images,
                    'duplicate_keywords': duplicate_keywords
                }
                
        except Exception as e:
            logger.error(f"데이터 무결성 검사 실패: {e}")
            return None
    
    def print_report(self):
        """전체 보고서 출력"""
        print("\n" + "="*80)
        print("🎯 완전한 PostgreSQL 패션 추천 시스템 데이터 상태 보고서")
        print("="*80)
        
        # 1. 기본 통계
        print("\n📊 1. 기본 통계")
        print("-" * 40)
        basic_stats = self.get_basic_stats()
        if basic_stats:
            print(f"📦 전체 상품 수: {basic_stats['total_products']:,}개")
            
            print("\n🏷️  카테고리별 분포:")
            for cat in basic_stats['category_distribution']:
                print(f"   {cat['category']}: {cat['count']:,}개")
            
            print("\n🏢 브랜드별 분포 (상위 10개):")
            for brand in basic_stats['brand_distribution']:
                print(f"   {brand['brand_en']}: {brand['count']:,}개")
            
            print("\n💰 가격대별 분포:")
            for price_range in basic_stats['price_distribution']:
                print(f"   {price_range['price_range']}: {price_range['count']:,}개")
        
        # 2. 상세 통계
        print("\n📈 2. 상세 통계")
        print("-" * 40)
        detailed_stats = self.get_detailed_stats()
        if detailed_stats:
            print(f"📏 사이즈 데이터: {detailed_stats['total_sizes']:,}개")
            print(f"💬 리뷰 데이터: {detailed_stats['total_reviews']:,}개")
            print(f"🏷️  스타일 키워드: {detailed_stats['total_keywords']:,}개")
            print(f"🖼️  이미지 데이터: {detailed_stats['total_images']:,}개")
            print(f"🏷️  태그가 있는 상품: {detailed_stats['products_with_tags']:,}개")
            print(f"🖼️  이미지가 있는 상품: {detailed_stats['products_with_images']:,}개")
        
        # 3. 샘플 데이터
        print("\n🔍 3. 샘플 상품 데이터")
        print("-" * 40)
        sample_products = self.get_sample_products(3)
        for i, product in enumerate(sample_products, 1):
            print(f"\n{i}. {product['product_name']}")
            print(f"   ID: {product['product_id']}")
            print(f"   카테고리: {product['category']}")
            print(f"   브랜드: {product['brand_en']} ({product['brand_kr']})")
            print(f"   가격: {product['price']:,}원 (할인율: {product['discount_rate']}%)")
            print(f"   태그: {product['tags'][:3] if product['tags'] else '없음'}")
            print(f"   사이즈: {product['size_count']}개, 리뷰: {product['review_count']}개")
            print(f"   키워드: {product['keyword_count']}개, 이미지: {product['image_count']}개")
        
        # 4. SQL 검색 테스트
        print("\n🔎 4. SQL 검색 테스트")
        print("-" * 40)
        search_results = self.test_sql_search()
        if search_results:
            print("✅ 모든 SQL 검색 테스트가 성공적으로 실행되었습니다.")
            print("   - 카테고리별 검색: 가방 카테고리")
            print("   - 브랜드별 검색: musinsastandard")
            print("   - 가격대별 검색: 5-10만원")
            print("   - 태그 검색: 레더, 크로스백")
            print("   - 할인율 검색: 20% 이상")
        
        # 5. 데이터 무결성
        print("\n🔒 5. 데이터 무결성 검사")
        print("-" * 40)
        integrity = self.check_data_integrity()
        if integrity:
            print(f"✅ 고아 레코드: 사이즈 {integrity['orphan_sizes']}개, 리뷰 {integrity['orphan_reviews']}개")
            print(f"   키워드 {integrity['orphan_keywords']}개, 이미지 {integrity['orphan_images']}개")
            print(f"✅ 중복 키워드: {integrity['duplicate_keywords']}개")
        
        print("\n" + "="*80)
        print("🎉 완전한 PostgreSQL 패션 추천 시스템이 준비되었습니다!")
        print("="*80)

def main():
    """메인 실행 함수"""
    # 데이터베이스 설정
    db_config = {
        'host': 'localhost',
        'port': 5432,
        'database': 'fashion_recommendation',
        'user': 'postgres',
        'password': 'postgres'
    }
    
    # 데이터 확인 실행
    checker = CompleteDataChecker(db_config)
    if checker.connect():
        checker.print_report()
    else:
        print("❌ 데이터베이스 연결에 실패했습니다.")

if __name__ == "__main__":
    main() 