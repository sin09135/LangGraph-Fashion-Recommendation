#!/usr/bin/env python3
"""
LangGraph 워크플로우 시각화 스크립트
"""

import sys
import os
import pandas as pd

# 프로젝트 루트 경로 추가
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

def create_mock_data():
    """테스트용 샘플 데이터 생성"""
    sample_data = {
        'product_id': ['1', '2', '3', '4', '5'],
        'product_name': ['베이직 티셔츠', '스트릿 반팔', '꾸안꾸 무지', '캐주얼 후드', '베이직 니트'],
        'category': ['상의', '상의', '상의', '상의', '상의'],
        'style_keywords': [['베이직'], ['스트릿'], ['베이직', '꾸안꾸'], ['캐주얼'], ['베이직']],
        'rating': [4.8, 4.6, 4.9, 4.7, 4.5],
        'review_count': [1500, 800, 2200, 1200, 900],
        'description': ['베이직 티셔츠', '스트릿 반팔', '꾸안꾸 무지', '캐주얼 후드', '베이직 니트']
    }
    return pd.DataFrame(sample_data)

def visualize_langgraph_workflow():
    """LangGraph 워크플로우 시각화"""
    try:
        from langgraph_fashion_system import LangGraphFashionSystem
        
        print("🔄 LangGraph 패션 시스템 초기화 중...")
        
        # 샘플 데이터로 시스템 초기화
        df = create_mock_data()
        system = LangGraphFashionSystem(df)
        
        print("✅ 시스템 초기화 완료!")
        print("\n📊 LangGraph 워크플로우 시각화 생성 중...")
        
        # Mermaid 다이어그램 생성
        mermaid_code = system.visualize_workflow()
        
        print("✅ Mermaid 다이어그램 생성 완료!")
        print("\n" + "="*60)
        print("🎯 LangGraph 패션 추천 시스템 워크플로우")
        print("="*60)
        print(mermaid_code)
        print("="*60)
        
        # Mermaid 코드를 파일로 저장
        with open("langgraph_workflow_diagram.mmd", "w", encoding="utf-8") as f:
            f.write(mermaid_code)
        
        print(f"\n💾 Mermaid 코드가 'langgraph_workflow_diagram.mmd' 파일로 저장되었습니다.")
        print("📝 이 코드를 Mermaid Live Editor나 다른 Mermaid 지원 도구에서 사용하세요.")
        
        return mermaid_code
        
    except ImportError as e:
        print(f"❌ 모듈 임포트 오류: {e}")
        print("🔧 필요한 의존성이 설치되어 있는지 확인하세요.")
        return None
    except Exception as e:
        print(f"❌ 워크플로우 시각화 오류: {e}")
        return None

def create_simple_mermaid():
    """간단한 Mermaid 다이어그램 생성 (LangGraph 없이)"""
    mermaid_code = """graph TD
    A[사용자 입력] --> B[대화 에이전트]
    B --> C{대화 분석}
    C -->|추천 요청| D[추천 에이전트]
    C -->|일반 대화| E[응답 생성]
    C -->|피드백| F[피드백 처리]
    
    D --> G[추천 결과]
    G --> H[평가기]
    H --> I{품질 평가}
    I -->|우수/보통| J[피드백 감지]
    I -->|개선 필요| K[추천 재조정]
    
    J --> L{피드백 분석}
    L -->|긍정| E
    L -->|조건 변경| K
    L -->|부정| K
    L -->|더 보기| K
    L -->|행동 피드백| F
    
    K --> D
    F --> M{피드백 처리}
    M -->|재추천| D
    M -->|선호도 업데이트| E
    M -->|오류| E
    
    E --> N[최종 응답]
    
    style A fill:#e1f5fe
    style N fill:#c8e6c9
    style H fill:#fff3e0
    style J fill:#f3e5f5
    style K fill:#ffebee
    """
    
    print("📊 간단한 LangGraph 워크플로우 다이어그램:")
    print("="*60)
    print(mermaid_code)
    print("="*60)
    
    # 파일로 저장
    with open("simple_langgraph_workflow.mmd", "w", encoding="utf-8") as f:
        f.write(mermaid_code)
    
    print(f"\n💾 간단한 다이어그램이 'simple_langgraph_workflow.mmd' 파일로 저장되었습니다.")
    
    return mermaid_code

if __name__ == "__main__":
    print("🚀 LangGraph 워크플로우 시각화 시작")
    print("="*60)
    
    # 먼저 LangGraph 시각화 시도
    result = visualize_langgraph_workflow()
    
    if result is None:
        print("\n⚠️  LangGraph 시각화 실패, 간단한 다이어그램 생성...")
        create_simple_mermaid()
    
    print("\n✅ 시각화 완료!") 