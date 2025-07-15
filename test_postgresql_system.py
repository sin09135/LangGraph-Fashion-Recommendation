"""
PostgreSQL 기반 추천 시스템 테스트
"""

import sys
import os
import pandas as pd

# 프로젝트 루트 경로 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))

from main_recommendation_system import LLMFashionRecommendationSystem

def test_postgresql_system():
    """PostgreSQL 시스템 테스트"""
    
    print("🐘 PostgreSQL 기반 추천 시스템 테스트")
    print("=" * 50)
    
    try:
        # PostgreSQL 시스템 초기화
        system = LLMFashionRecommendationSystem(
            use_langgraph=False,
            use_rdb=False,
            use_postgresql=True
        )
        
        print("✅ PostgreSQL 시스템 초기화 완료")
        
        # 테스트 대화
        test_conversations = [
            "베이직 스타일의 상의 추천해줘",
            "스트릿 패션의 바지 추천해줘",
            "꾸안꾸 스타일의 신발 추천해줘"
        ]
        
        for i, user_input in enumerate(test_conversations, 1):
            print(f"\n--- 테스트 {i} ---")
            print(f"사용자: {user_input}")
            
            # 시스템 응답
            response = system.process_user_input(user_input)
            
            print(f"시스템: {response['text']}")
            print(f"의도: {response['intent']} (신뢰도: {response['confidence']:.2f})")
            
            # 추천 결과 출력
            if response.get('recommendations'):
                print(f"\n추천 상품 ({len(response['recommendations'])}개):")
                for j, rec in enumerate(response['recommendations'], 1):
                    print(f"  {j}. {rec['product_name']}")
                    print(f"     평점: {rec['rating']}, 리뷰: {rec['review_count']}")
                    print(f"     추천 이유: {rec['recommendation_reason']}")
                    if rec.get('representative_review'):
                        print(f"     대표 리뷰: {rec['representative_review']}")
                    print()
            else:
                print("추천 결과가 없습니다.")
            
            print("-" * 30)
        
        # 시스템 요약 정보
        print("\n=== 시스템 요약 ===")
        conv_summary = system.get_conversation_summary()
        rec_summary = system.get_recommendation_summary()
        
        print(f"총 대화 턴: {conv_summary.get('total_turns', 0)}")
        print(f"사용자 선호도: {conv_summary.get('user_preferences', {})}")
        print(f"총 추천 수: {rec_summary.get('total_recommendations', 0)}")
        
        # PostgreSQL 성능 메트릭
        if hasattr(system, 'postgresql_agent') and system.postgresql_agent:
            metrics = system.postgresql_agent.get_performance_metrics()
            print(f"\nPostgreSQL 성능 메트릭:")
            print(f"데이터베이스 통계: {metrics.get('database_stats', {})}")
        
        print("\n✅ PostgreSQL 시스템 테스트 완료")
        
    except Exception as e:
        print(f"❌ PostgreSQL 시스템 테스트 실패: {e}")
        print("PostgreSQL 서버가 실행 중이고 연결 정보가 올바른지 확인하세요.")
        print("필요한 패키지 설치: pip install psycopg2-binary")

def test_postgresql_connection():
    """PostgreSQL 연결 테스트"""
    
    print("🔌 PostgreSQL 연결 테스트")
    print("=" * 30)
    
    try:
        from database.postgresql_manager import PostgreSQLManager
        
        # PostgreSQL 매니저 초기화
        pg_manager = PostgreSQLManager(
            host="localhost",
            port=5432,
            database="fashion_recommendation",
            user="postgres",
            password="password"
        )
        
        # 연결 테스트
        with pg_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT version();")
                version = cursor.fetchone()
                print(f"✅ PostgreSQL 연결 성공")
                print(f"버전: {version[0]}")
        
        # 테이블 존재 확인
        with pg_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public'
                """)
                tables = cursor.fetchall()
                print(f"테이블 목록: {[table[0] for table in tables]}")
        
        print("✅ PostgreSQL 연결 테스트 완료")
        
    except Exception as e:
        print(f"❌ PostgreSQL 연결 실패: {e}")
        print("다음을 확인하세요:")
        print("1. PostgreSQL 서버가 실행 중인지")
        print("2. 데이터베이스 'fashion_recommendation'이 존재하는지")
        print("3. 사용자 'postgres'와 비밀번호가 올바른지")
        print("4. psycopg2 패키지가 설치되어 있는지")

def test_postgresql_agent():
    """PostgreSQL 추천 에이전트 테스트"""
    
    print("🤖 PostgreSQL 추천 에이전트 테스트")
    print("=" * 40)
    
    try:
        from agents.postgresql_recommendation_agent import PostgreSQLRecommendationAgent
        
        # 에이전트 초기화
        agent = PostgreSQLRecommendationAgent(
            host="localhost",
            port=5432,
            database="fashion_recommendation",
            user="postgres",
            password="password"
        )
        
        print("✅ PostgreSQL 추천 에이전트 초기화 완료")
        
        # 테스트 요청
        test_request = {
            'original_query': '베이직 스타일의 상의 추천해줘',
            'filters': {
                'categories': '상의',
                'tags': '베이직'
            },
            'user_preferences': {
                'tags': ['베이직'],
                'categories': ['상의']
            },
            'user_id': 'test_user'
        }
        
        # 추천 수행
        recommendations = agent.recommend_products(test_request, top_k=3)
        
        print(f"\n추천 결과 ({len(recommendations)}개):")
        for i, rec in enumerate(recommendations, 1):
            print(f"\n{i}. {rec.product_name}")
            print(f"   카테고리: {rec.category}")
            print(f"   평점: {rec.rating}, 리뷰: {rec.review_count}")
            print(f"   스타일: {rec.style_keywords}")
            print(f"   추천 이유: {rec.recommendation_reason}")
            print(f"   신뢰도: {rec.confidence_score:.3f}")
        
        # 요약 정보
        summary = agent.get_recommendation_summary()
        print(f"\n추천 요약: {summary}")
        
        print("✅ PostgreSQL 추천 에이전트 테스트 완료")
        
    except Exception as e:
        print(f"❌ PostgreSQL 추천 에이전트 테스트 실패: {e}")

if __name__ == "__main__":
    print("PostgreSQL 시스템 테스트 시작")
    print("=" * 60)
    
    # 1. 연결 테스트
    test_postgresql_connection()
    
    print("\n" + "=" * 60)
    
    # 2. 추천 에이전트 테스트
    test_postgresql_agent()
    
    print("\n" + "=" * 60)
    
    # 3. 전체 시스템 테스트
    test_postgresql_system()
    
    print("\n" + "=" * 60)
    print("PostgreSQL 시스템 테스트 완료") 