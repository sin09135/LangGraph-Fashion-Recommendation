import json

def check_json_structure():
    """JSON 데이터의 실제 구조를 확인합니다."""
    
    print("JSON 데이터 구조 확인 중...")
    
    try:
        with open('data/merged_all_data.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        print(f"총 {len(data)} 개의 데이터가 있습니다.")
        
        # 첫 번째 항목의 구조 확인
        if len(data) > 0:
            first_item = data[0]
            print(f"\n첫 번째 항목의 키들: {list(first_item.keys())}")
            print(f"첫 번째 항목의 타입: {type(first_item)}")
            
            # 각 키의 값 타입 확인
            for key, value in first_item.items():
                print(f"  {key}: {type(value)} - {str(value)[:100]}...")
        
        # 처음 몇 개 항목의 키들 확인
        print(f"\n=== 처음 5개 항목의 키들 ===")
        for i, item in enumerate(data[:5]):
            print(f"항목 {i+1}: {list(item.keys())}")
        
        # 모든 항목에서 사용되는 키들 수집
        all_keys = set()
        for item in data:
            all_keys.update(item.keys())
        
        print(f"\n=== 전체 데이터에서 사용되는 모든 키들 ===")
        for key in sorted(all_keys):
            print(f"  - {key}")
        
    except Exception as e:
        print(f"오류 발생: {e}")

if __name__ == "__main__":
    check_json_structure() 