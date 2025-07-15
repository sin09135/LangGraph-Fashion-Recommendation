import json

def check_style_keywords_structure():
    """JSON 데이터에서 스타일 키워드(tags) 정보 구조를 확인합니다."""
    
    print("스타일 키워드 데이터 구조 확인 중...")
    
    try:
        with open('data/merged_all_data.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        print(f"총 {len(data)} 개의 상품 데이터가 있습니다.")
        
        # tags가 있는 상품들 확인
        products_with_tags = [item for item in data if 'tags' in item and item['tags']]
        print(f"tags가 있는 상품 수: {len(products_with_tags)}")
        
        # 처음 몇 개 상품의 tags 구조 확인
        for i, product in enumerate(products_with_tags[:5]):
            print(f"\n=== 상품 {i+1} ===")
            print(f"상품명: {product.get('product_name', 'N/A')}")
            
            tags = product['tags']
            print(f"tags 타입: {type(tags)}")
            print(f"tags 개수: {len(tags) if isinstance(tags, list) else 'N/A'}")
            
            if isinstance(tags, list):
                print("태그 목록:")
                for j, tag in enumerate(tags[:10]):  # 처음 10개만 출력
                    print(f"  {j+1}: {tag}")
                
                if len(tags) > 10:
                    print(f"  ... 외 {len(tags) - 10}개 더")
        
        # 전체 데이터에서 태그 분석
        print(f"\n=== 전체 데이터 분석 ===")
        all_tags = set()
        tag_count_by_product = []
        
        for product in products_with_tags:
            if 'tags' in product and isinstance(product['tags'], list):
                tags = product['tags']
                tag_count_by_product.append(len(tags))
                all_tags.update(tags)
        
        print(f"총 고유 태그 수: {len(all_tags)}")
        print(f"상품당 평균 태그 수: {sum(tag_count_by_product) / len(tag_count_by_product):.1f}")
        print(f"최소 태그 수: {min(tag_count_by_product)}")
        print(f"최대 태그 수: {max(tag_count_by_product)}")
        
        # 가장 많이 사용된 태그들 확인
        tag_frequency = {}
        for product in products_with_tags:
            if 'tags' in product and isinstance(product['tags'], list):
                for tag in product['tags']:
                    tag_frequency[tag] = tag_frequency.get(tag, 0) + 1
        
        # 상위 20개 태그 출력
        top_tags = sorted(tag_frequency.items(), key=lambda x: x[1], reverse=True)[:20]
        print(f"\n가장 많이 사용된 태그 (상위 20개):")
        for tag, count in top_tags:
            print(f"  {tag}: {count}개 상품")
        
        # 태그 패턴 분석
        print(f"\n=== 태그 패턴 분석 ===")
        hash_tags = [tag for tag in all_tags if tag.startswith('#')]
        non_hash_tags = [tag for tag in all_tags if not tag.startswith('#')]
        
        print(f"#으로 시작하는 태그: {len(hash_tags)}개")
        print(f"일반 태그: {len(non_hash_tags)}개")
        
        if hash_tags:
            print(f"\n#태그 예시 (처음 10개):")
            for tag in hash_tags[:10]:
                print(f"  {tag}")
        
        if non_hash_tags:
            print(f"\n일반 태그 예시 (처음 10개):")
            for tag in non_hash_tags[:10]:
                print(f"  {tag}")
        
    except Exception as e:
        print(f"오류 발생: {e}")

if __name__ == "__main__":
    check_style_keywords_structure() 