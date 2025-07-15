#!/usr/bin/env python3
"""
SQL 기반 추천 시스템 테스트
"""

import sys
import os
import pandas as pd

# 프로젝트 루트 경로 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))

from main_recommendation_system import LLMFashionRecommendationSystem

def test_sql_based_recommendation():
    """SQL 기반 추천 테스트"""
    
    print("🟨 SQL 기반 추천 시스템 테스트")
    print("=" * 50)
    
    try:
        # 순차 처리 시스템 초기화 (SQL/벡터 분기 포함)
        system = LLMFashionRecommendationSystem(
            use_langgraph=False,
            use_rdb=False,
            use_postgresql=False
        )
        
        print("✅ 시스템 초기화 완료")
        
        # SQL 기반 추천이 될 것으로 예상되는 테스트 케이스들
        sql_test_cases = [
            {
                "query": "베이직 스타일의 상의 추천해줘",
                "expected_method": "SQL",
                "description": "카테고리(상의) + 스타일(베이직) - 2개 조건"
            },
            {
                "query": "스트릿 무드의 바지 추천해줘",
                "expected_method": "SQL", 
                "description": "카테고리(바지) + 스타일(스트릿) - 2개 조건"
            },
            {
                "query": "검은색 베이직 티셔츠 추천해줘",
                "expected_method": "SQL",
                "description": "카테고리(티셔츠) + 스타일(베이직) + 색상(검은색) - 3개 조건"
            },
            {
                "query": "꾸안꾸 스타일의 상의 추천해줘",
                "expected_method": "SQL",
                "description": "카테고리(상의) + 스타일(꾸안꾸) - 2개 조건"
            }
        ]
        
        # 벡터 기반 추천이 될 것으로 예상되는 테스트 케이스들
        vector_test_cases = [
            {
                "query": "베이직 스타일 추천해줘",
                "expected_method": "Vector",
                "description": "스타일만 - 1개 조건"
            },
            {
                "query": "상의 추천해줘",
                "expected_method": "Vector", 
                "description": "카테고리만 - 1개 조건"
            },
            {
                "query": "요즘 트렌디한 옷 추천해줘",
                "expected_method": "Vector",
                "description": "모호한 표현 - 벡터 기반"
            },
            {
                "query": "이런 느낌의 옷 추천해줘",
                "expected_method": "Vector",
                "description": "비정형 표현 - 벡터 기반"
            }
        ]
        
        all_test_cases = sql_test_cases + vector_test_cases
        
        print(f"\n총 {len(all_test_cases)}개 테스트 케이스 실행")
        print("-" * 50)
        
        correct_predictions = 0
        total_tests = len(all_test_cases)
        
        for i, test_case in enumerate(all_test_cases, 1):
            print(f"\n--- 테스트 {i}: {test_case['description']} ---")
            print(f"입력: {test_case['query']}")
            print(f"예상 방식: {test_case['expected_method']}")
            
            # 시스템 응답
            response = system.process_user_input(test_case['query'])
            
            # 추천 결과 확인
            if response.get('recommendations'):
                print(f"✅ 추천 결과: {len(response['recommendations'])}개 상품")
                
                # 첫 번째 추천 상품 정보 출력
                first_rec = response['recommendations'][0]
                print(f"  첫 번째 추천: {first_rec['product_name']}")
                print(f"  카테고리: {first_rec['category']}")
                print(f"  평점: {first_rec['rating']}, 리뷰: {first_rec['review_count']}")
                print(f"  추천 이유: {first_rec['recommendation_reason']}")
                
                # SQL/벡터 분기 확인 (로그에서 확인)
                print(f"  의도: {response.get('intent', 'N/A')}")
                print(f"  신뢰도: {response.get('confidence', 0.0):.2f}")
                
                correct_predictions += 1
            else:
                print("❌ 추천 결과 없음")
            
            print("-" * 30)
        
        # 결과 요약
        print(f"\n=== 테스트 결과 요약 ===")
        print(f"총 테스트: {total_tests}개")
        print(f"성공: {correct_predictions}개")
        print(f"실패: {total_tests - correct_predictions}개")
        print(f"성공률: {correct_predictions/total_tests*100:.1f}%")
        
        # 시스템 요약 정보
        print(f"\n=== 시스템 요약 ===")
        conv_summary = system.get_conversation_summary()
        rec_summary = system.get_recommendation_summary()
        
        print(f"총 대화 턴: {conv_summary.get('total_turns', 0)}")
        print(f"사용자 선호도: {conv_summary.get('user_preferences', {})}")
        print(f"총 추천 수: {rec_summary.get('total_recommendations', 0)}")
        
        print("\n✅ SQL 기반 추천 테스트 완료")
        
    except Exception as e:
        print(f"❌ SQL 기반 추천 테스트 실패: {e}")
        import traceback
        traceback.print_exc()

def test_sql_vs_vector_decision():
    """SQL vs 벡터 분기 결정 테스트"""
    
    print("\n🔍 SQL vs 벡터 분기 결정 테스트")
    print("=" * 50)
    
    try:
        # 순차 처리 시스템 초기화
        system = LLMFashionRecommendationSystem(
            use_langgraph=False,
            use_rdb=False,
            use_postgresql=False
        )
        
        # 추천 에이전트의 분기 함수 직접 테스트
        if hasattr(system, 'recommendation_agent'):
            agent = system.recommendation_agent
            
            test_filters = [
                # SQL 기반이어야 하는 케이스들
                {
                    'categories': '상의',
                    'tags': '베이직',
                    'description': '카테고리 + 스타일 (2개 조건)'
                },
                {
                    'categories': '바지',
                    'tags': '스트릿',
                    'color': '검은색',
                    'description': '카테고리 + 스타일 + 색상 (3개 조건)'
                },
                {
                    'categories': '상의',
                    'brand': '무신사',
                    'description': '카테고리 + 브랜드 (2개 조건)'
                },
                # 벡터 기반이어야 하는 케이스들
                {
                    'categories': '상의',
                    'description': '카테고리만 (1개 조건)'
                },
                {
                    'tags': '베이직',
                    'description': '스타일만 (1개 조건)'
                },
                {
                    'description': '조건 없음 (0개 조건)'
                }
            ]
            
            print(f"분기 결정 테스트: {len(test_filters)}개 케이스")
            print("-" * 40)
            
            for i, filters in enumerate(test_filters, 1):
                description = filters.pop('description', f'케이스 {i}')
                result = agent._should_use_sql_based(filters, "")
                expected = "SQL" if result else "Vector"
                
                print(f"{i}. {description}")
                print(f"   필터: {filters}")
                print(f"   결과: {expected}")
                print()
                
                # 필터에 description 다시 추가
                filters['description'] = description
        
        print("✅ 분기 결정 테스트 완료")
        
    except Exception as e:
        print(f"❌ 분기 결정 테스트 실패: {e}")

if __name__ == "__main__":
    print("SQL 기반 추천 시스템 테스트 시작")
    print("=" * 60)
    
    # 1. SQL vs 벡터 분기 결정 테스트
    test_sql_vs_vector_decision()
    
    print("\n" + "=" * 60)
    
    # 2. 전체 SQL 기반 추천 테스트
    test_sql_based_recommendation()
    
    print("\n" + "=" * 60)
    print("SQL 기반 추천 시스템 테스트 완료") 