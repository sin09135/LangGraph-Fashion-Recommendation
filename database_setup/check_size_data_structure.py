import json
import pandas as pd

def check_size_data_structure():
    """JSON 데이터에서 사이즈 정보 구조를 확인합니다."""
    
    print("JSON 데이터에서 사이즈 정보 구조 확인 중...")
    
    try:
        with open('data/merged_all_data.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        print(f"총 {len(data)} 개의 상품 데이터가 있습니다.")
        
        # 처음 몇 개 상품의 사이즈 정보 확인
        for i, product in enumerate(data[:5]):
            print(f"\n=== 상품 {i+1} ===")
            print(f"상품명: {product.get('name', 'N/A')}")
            
            if 'sizes' in product:
                sizes = product['sizes']
                print(f"사이즈 정보 타입: {type(sizes)}")
                print(f"사이즈 정보 길이: {len(sizes) if isinstance(sizes, list) else 'N/A'}")
                
                if isinstance(sizes, list) and len(sizes) > 0:
                    print("사이즈 목록:")
                    for j, size in enumerate(sizes[:10]):  # 처음 10개만 출력
                        print(f"  {j+1}: {size}")
                    
                    # 첫 번째 항목 확인
                    if len(sizes) > 0:
                        first_size = sizes[0]
                        print(f"\n첫 번째 사이즈 항목: '{first_size}'")
                        if isinstance(first_size, str) and ("입력" in first_size or "선택" in first_size):
                            print("⚠️  첫 번째 항목에 '입력' 또는 '선택' 텍스트가 포함되어 있습니다!")
                
            else:
                print("사이즈 정보가 없습니다.")
        
        # 사이즈 정보가 있는 상품들의 첫 번째 사이즈 항목 통계
        print("\n=== 사이즈 데이터 분석 ===")
        first_sizes = []
        for product in data:
            if 'sizes' in product and isinstance(product['sizes'], list) and len(product['sizes']) > 0:
                first_sizes.append(product['sizes'][0])
        
        if first_sizes:
            print(f"사이즈 정보가 있는 상품 수: {len(first_sizes)}")
            
            # 첫 번째 사이즈 항목들의 고유값 확인
            unique_first_sizes = set(first_sizes)
            print(f"첫 번째 사이즈 항목의 고유값 수: {len(unique_first_sizes)}")
            
            # 문제가 될 수 있는 항목들 확인
            problematic_sizes = [size for size in unique_first_sizes 
                               if isinstance(size, str) and 
                               any(keyword in size for keyword in ['입력', '선택', '사이즈를', '사이즈 선택'])]
            
            if problematic_sizes:
                print(f"\n⚠️  문제가 될 수 있는 첫 번째 사이즈 항목들:")
                for size in problematic_sizes:
                    print(f"  - '{size}'")
            else:
                print("\n✅ 첫 번째 사이즈 항목에 문제가 될 만한 텍스트가 없습니다.")
        
    except Exception as e:
        print(f"오류 발생: {e}")

if __name__ == "__main__":
    check_size_data_structure() 