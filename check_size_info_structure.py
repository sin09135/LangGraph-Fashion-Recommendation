import json

def check_size_info_structure():
    """size_info 딕셔너리의 구조를 자세히 확인합니다."""
    
    print("size_info 구조 확인 중...")
    
    try:
        with open('data/merged_all_data.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        print(f"총 {len(data)} 개의 상품 데이터가 있습니다.")
        
        # size_info가 있는 상품들 확인
        products_with_size = [item for item in data if 'size_info' in item and item['size_info']]
        print(f"size_info가 있는 상품 수: {len(products_with_size)}")
        
        # 처음 몇 개 상품의 size_info 구조 확인
        for i, product in enumerate(products_with_size[:3]):
            print(f"\n=== 상품 {i+1} ===")
            print(f"상품명: {product.get('product_name', 'N/A')}")
            
            size_info = product['size_info']
            print(f"size_info 타입: {type(size_info)}")
            print(f"size_info 키들: {list(size_info.keys()) if isinstance(size_info, dict) else 'N/A'}")
            
            if isinstance(size_info, dict):
                if 'headers' in size_info:
                    print(f"헤더: {size_info['headers']}")
                
                if 'rows' in size_info:
                    rows = size_info['rows']
                    print(f"행 수: {len(rows)}")
                    print("행들:")
                    for j, row in enumerate(rows[:5]):  # 처음 5개 행만 출력
                        print(f"  행 {j+1}: {row}")
                    
                    # 첫 번째 행 확인
                    if len(rows) > 0:
                        first_row = rows[0]
                        print(f"\n첫 번째 행: {first_row}")
                        if isinstance(first_row, list) and len(first_row) > 0:
                            first_cell = first_row[0]
                            print(f"첫 번째 셀: '{first_cell}'")
                            if isinstance(first_cell, str) and ("입력" in first_cell or "선택" in first_cell):
                                print("⚠️  첫 번째 행에 '입력' 또는 '선택' 텍스트가 포함되어 있습니다!")
        
        # 전체 데이터에서 첫 번째 행의 패턴 분석
        print(f"\n=== 전체 데이터 분석 ===")
        first_rows = []
        for product in products_with_size:
            if 'size_info' in product and isinstance(product['size_info'], dict):
                size_info = product['size_info']
                if 'rows' in size_info and isinstance(size_info['rows'], list) and len(size_info['rows']) > 0:
                    first_rows.append(size_info['rows'][0])
        
        print(f"사이즈 정보가 있는 상품 수: {len(first_rows)}")
        
        # 첫 번째 행들의 고유값 확인
        unique_first_rows = set()
        for row in first_rows:
            if isinstance(row, list):
                row_str = str(row)
                unique_first_rows.add(row_str)
        
        print(f"첫 번째 행의 고유 패턴 수: {len(unique_first_rows)}")
        
        # 문제가 될 수 있는 첫 번째 행들 확인
        problematic_rows = []
        for row in first_rows:
            if isinstance(row, list) and len(row) > 0:
                first_cell = row[0]
                if isinstance(first_cell, str) and any(keyword in first_cell for keyword in ['입력', '선택', '사이즈를', '사이즈 선택']):
                    problematic_rows.append(row)
        
        if problematic_rows:
            print(f"\n⚠️  문제가 될 수 있는 첫 번째 행들:")
            for row in problematic_rows[:5]:  # 처음 5개만 출력
                print(f"  - {row}")
            print(f"총 {len(problematic_rows)} 개의 문제 행이 있습니다.")
        else:
            print("\n✅ 첫 번째 행에 문제가 될 만한 텍스트가 없습니다.")
        
    except Exception as e:
        print(f"오류 발생: {e}")

if __name__ == "__main__":
    check_size_info_structure() 