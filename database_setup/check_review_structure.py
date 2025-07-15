import json

def check_review_structure():
    """JSON 데이터에서 리뷰 정보 구조를 확인합니다."""
    
    print("리뷰 데이터 구조 확인 중...")
    
    try:
        with open('data/merged_all_data.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        print(f"총 {len(data)} 개의 상품 데이터가 있습니다.")
        
        # review_info가 있는 상품들 확인
        products_with_review = [item for item in data if 'review_info' in item and item['review_info']]
        print(f"review_info가 있는 상품 수: {len(products_with_review)}")
        
        # 처음 몇 개 상품의 review_info 구조 확인
        for i, product in enumerate(products_with_review[:3]):
            print(f"\n=== 상품 {i+1} ===")
            print(f"상품명: {product.get('product_name', 'N/A')}")
            
            review_info = product['review_info']
            print(f"review_info 타입: {type(review_info)}")
            print(f"review_info 키들: {list(review_info.keys()) if isinstance(review_info, dict) else 'N/A'}")
            
            if isinstance(review_info, dict):
                for key, value in review_info.items():
                    print(f"  {key}: {type(value)} - {str(value)[:100]}...")
                
                # reviews 리스트 확인
                if 'reviews' in review_info:
                    reviews = review_info['reviews']
                    print(f"\n리뷰 개수: {len(reviews) if isinstance(reviews, list) else 'N/A'}")
                    
                    if isinstance(reviews, list) and len(reviews) > 0:
                        print("첫 번째 리뷰 구조:")
                        first_review = reviews[0]
                        print(f"  타입: {type(first_review)}")
                        if isinstance(first_review, dict):
                            print(f"  키들: {list(first_review.keys())}")
                            for key, value in first_review.items():
                                print(f"    {key}: {type(value)} - {str(value)[:50]}...")
        
        # 전체 데이터에서 리뷰 구조 분석
        print(f"\n=== 전체 데이터 분석 ===")
        all_review_keys = set()
        total_reviews = 0
        
        for product in products_with_review:
            if 'review_info' in product and isinstance(product['review_info'], dict):
                review_info = product['review_info']
                
                # review_info 레벨 키들
                all_review_keys.update(review_info.keys())
                
                # 개별 리뷰 키들
                if 'reviews' in review_info and isinstance(review_info['reviews'], list):
                    total_reviews += len(review_info['reviews'])
                    for review in review_info['reviews']:
                        if isinstance(review, dict):
                            all_review_keys.update(review.keys())
        
        print(f"총 리뷰 개수: {total_reviews}")
        print(f"발견된 모든 리뷰 관련 키들: {sorted(all_review_keys)}")
        
    except Exception as e:
        print(f"오류 발생: {e}")

if __name__ == "__main__":
    check_review_structure() 