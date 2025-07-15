#!/usr/bin/env python3
"""
RDB 기반 추천 시스템 테스트
"""

import sys
import os

# 프로젝트 루트 경로 추가
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

def test_rdb_system():
    """RDB 기반 추천 시스템 테스트"""
    try:
        from main_recommendation_system import LLMFashionRecommendationSystem
        
        print("🧪 RDB 기반 추천 시스템 테스트 시작")
        print("="*60)
        
        # RDB 시스템 초기화
        system = LLMFashionRecommendationSystem(
            data_dir="data",
            use_langgraph=False,
            use_rdb=True
        )
        
        print("✅ RDB 시스템 초기화 완료")
        print()
        
        # 테스트 케이스들
        test_inputs = [
            "안녕하세요!",
            "베이직 스타일의 상의 추천해줘",
            "스트릿한 무드의 티셔츠 추천해줘",
            "저렴한 반팔 추천해줘",
            "감사합니다!"
        ]
        
        for i, user_input in enumerate(test_inputs, 1):
            print(f"🔍 테스트 {i}: {user_input}")
            
            try:
                # 시스템 응답
                response = system.process_user_input(user_input)
                
                print(f"   응답: {response['text']}")
                
                if response.get('recommendations'):
                    print(f"   추천 상품 수: {len(response['recommendations'])}")
                    
                    for j, rec in enumerate(response['recommendations'], 1):
                        print(f"     {j}. {rec['product_name']}")
                        print(f"        평점: {rec['rating']}, 리뷰: {rec['review_count']}")
                        print(f"        추천 이유: {rec['recommendation_reason']}")
                
                if response.get('error'):
                    print(f"   ❌ 오류: {response['error']}")
                
            except Exception as e:
                print(f"   ❌ 처리 오류: {e}")
            
            print()
        
        # 시스템 요약
        print("📊 시스템 요약")
        print("="*60)
        
        # 대화 요약
        conv_summary = system.get_conversation_summary()
        print(f"총 대화 턴: {conv_summary.get('total_turns', 0)}")
        print(f"사용자 선호도: {conv_summary.get('user_preferences', {})}")
        
        # 추천 요약
        if system.rdb_agent:
            rec_summary = system.rdb_agent.get_recommendation_summary()
            print(f"총 추천 수: {rec_summary.get('total_recommendations', 0)}")
            print(f"최근 추천 수: {rec_summary.get('recent_recommendations', 0)}")
        
        print("\n✅ RDB 기반 추천 시스템 테스트 완료")
        
    except ImportError as e:
        print(f"❌ 모듈 임포트 오류: {e}")
    except Exception as e:
        print(f"❌ 테스트 실행 오류: {e}")

if __name__ == "__main__":
    test_rdb_system() 