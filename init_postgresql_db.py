from src.database.postgresql_manager import PostgreSQLManager
from src.utils.data_processor import MusinsaDataProcessor

if __name__ == "__main__":
    print("=== PostgreSQL 데이터베이스 초기화 시작 ===")
    
    # 1. PostgreSQL 매니저 초기화 (DB 및 테이블 생성)
    pg_manager = PostgreSQLManager(
        host="localhost",
        port=5432,
        database="fashion_recommendation",
        user="postgres",
        password="password"
    )
    print("✅ PostgreSQL DB 및 테이블 생성 완료!")
    
    # 2. 데이터 프로세서 초기화
    data_processor = MusinsaDataProcessor("data")
    
    # 3. 상품 데이터 로드 및 전처리
    print("📊 상품 데이터 로드 중...")
    data = data_processor.load_data()
    
    if 'products' in data:
        processed_df = data_processor.preprocess_products(data['products'])
        processed_df = data_processor.extract_style_keywords(processed_df)
        # 누락 컬럼 보완
        required_cols = [
            'product_id', 'category', 'category_code', 'brand_en', 'brand_kr', 'price',
            'original_price', 'discount_rate', 'product_url', 'image_url', 'image_path', 'product_name'
        ]
        for col in required_cols:
            if col not in processed_df.columns:
                processed_df[col] = ''
        processed_df = processed_df[required_cols]
        print(f"✅ CSV 데이터 로드 완료: {len(processed_df)}개 상품")
    elif 'successful' in data:
        processed_df = data_processor.preprocess_products(data['successful'])
        processed_df = data_processor.extract_style_keywords(processed_df)
        print(f"✅ JSON 데이터 로드 완료: {len(processed_df)}개 상품")
    else:
        print("❌ 상품 데이터를 찾을 수 없습니다.")
        exit(1)
    
    # 4. PostgreSQL에 상품 데이터 삽입
    print("🗄️ PostgreSQL에 상품 데이터 삽입 중...")
    pg_manager.insert_products_from_dataframe(processed_df)
    print(f"✅ PostgreSQL에 {len(processed_df)}개 상품 데이터 삽입 완료!")
    
    # 5. 통계 정보 출력
    stats = pg_manager.get_statistics()
    print("\n=== 데이터베이스 통계 ===")
    print(f"총 상품 수: {stats.get('total_products', 0)}")
    print(f"총 리뷰 수: {stats.get('total_reviews', 0)}")
    print(f"총 스타일 키워드 수: {stats.get('total_style_keywords', 0)}")
    
    print("\n🎉 PostgreSQL 데이터베이스 초기화 및 데이터 적재 완료!") 