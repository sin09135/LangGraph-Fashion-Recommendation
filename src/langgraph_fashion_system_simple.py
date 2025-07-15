#!/usr/bin/env python3
"""
LangGraph 호환성 문제를 피한 간단한 패션 추천 시스템
멀티 에이전트 협업 워크플로우 시뮬레이션
"""

import os
import sys
import pandas as pd
import math
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime

# 프로젝트 루트를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from agents.conversation_agent import ConversationAgent
    from agents.recommendation_agent import RecommendationAgent
    from simple_vector_db import SimpleVectorDB
except ImportError as e:
    print(f"에이전트 모듈 import 오류: {e}")
    # 더미 에이전트 클래스 생성
    class ConversationAgent:
        def __init__(self, api_key=None):
            self.api_key = api_key
        
        def process_user_input(self, user_input: str) -> Dict[str, Any]:
            return {
                'intent': 'recommendation_request',
                'requires_recommendation': True,
                'extracted_info': {'category': '상의', 'style': '캐주얼'},
                'context': {'user_preferences': {}}
            }
    
    class RecommendationAgent:
        def __init__(self, products_df, api_key=None, reviews_data=None):
            self.products_df = products_df
        
        def recommend_products(self, request, top_k=3):
            # 더미 추천 결과 생성
            class DummyRecommendation:
                def __init__(self, product_id, product_name, category, rating, review_count, reason, confidence, url, image_url, review):
                    self.product_id = product_id
                    self.product_name = product_name
                    self.category = category
                    self.rating = rating
                    self.review_count = review_count
                    self.recommendation_reason = reason
                    self.confidence_score = confidence
                    self.url = url
                    self.image_url = image_url
                    self.representative_review = review
            
            return [
                DummyRecommendation(
                    "1", "베이직 티셔츠", "상의", 4.8, 1500,
                    "사용자 요청에 맞는 베이직한 스타일", 0.9,
                    "https://example.com/1", "https://example.com/img1.jpg",
                    "정말 좋은 품질이에요!"
                ),
                DummyRecommendation(
                    "2", "스트릿 반팔", "상의", 4.6, 800,
                    "스트릿한 느낌의 반팔", 0.85,
                    "https://example.com/2", "https://example.com/img2.jpg",
                    "디자인이 예뻐요"
                )
            ]

@dataclass
class FashionState:
    """패션 추천 시스템 상태"""
    user_input: str
    conversation_result: Optional[Dict[str, Any]] = None
    recommendations: Optional[List[Dict[str, Any]]] = None
    user_feedback: Optional[Dict[str, Any]] = None
    final_response: Optional[str] = None
    error: Optional[str] = None
    workflow_log: List[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.workflow_log is None:
            self.workflow_log = []

def safe_int(val, default=0):
    """안전한 정수 변환"""
    try:
        if val is None or (isinstance(val, float) and math.isnan(val)):
            return default
        return int(val)
    except Exception:
        return default

def safe_float(val, default=0.0):
    """안전한 실수 변환"""
    try:
        if val is None or (isinstance(val, float) and math.isnan(val)):
            return default
        return float(val)
    except Exception:
        return default

class SimpleLangGraphFashionSystem:
    """간단한 LangGraph 스타일 패션 추천 시스템"""
    
    def __init__(self, products_df: pd.DataFrame, api_key: Optional[str] = None, reviews_data: Optional[Dict[str, List[Dict[str, Any]]]] = None):
        self.products_df = products_df
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        
        # 에이전트들 초기화
        self.conversation_agent = ConversationAgent(api_key)
        self.recommendation_agent = RecommendationAgent(products_df, api_key, reviews_data)
        
        # 벡터 DB 매니저 초기화 (선택적)
        try:
            self.vector_db = SimpleVectorDB()
            self.vector_db.add_products(products_df)
        except:
            self.vector_db = None
            print("벡터 DB 초기화 실패, 기본 모드로 실행")
    
    def _log_step(self, state: FashionState, step_name: str, result: Any, duration: float = 0.0):
        """워크플로우 단계 로깅"""
        log_entry = {
            'step': step_name,
            'timestamp': datetime.now().isoformat(),
            'duration': duration,
            'result': result,
            'status': 'success' if result else 'error'
        }
        state.workflow_log.append(log_entry)
        print(f"📊 [{step_name}] 완료 - 소요시간: {duration:.2f}초")
    
    def _conversation_node(self, state: FashionState) -> FashionState:
        """대화 분석 노드"""
        import time
        start_time = time.time()
        
        try:
            print(f"💬 대화 분석 시작: {state.user_input}")
            result = self.conversation_agent.process_user_input(state.user_input)
            state.conversation_result = result
            
            duration = time.time() - start_time
            self._log_step(state, "conversation_analysis", result, duration)
            
        except Exception as e:
            duration = time.time() - start_time
            state.error = f"대화 처리 오류: {str(e)}"
            self._log_step(state, "conversation_analysis", None, duration)
        
        return state
    
    def _recommendation_node(self, state: FashionState) -> FashionState:
        """추천 처리 노드"""
        import time
        start_time = time.time()
        
        try:
            print(f"🔍 추천 처리 시작")
            
            if state.conversation_result and state.conversation_result.get('requires_recommendation'):
                # 추천 요청 구성
                recommendation_request = {
                    'original_query': state.user_input,
                    'filters': state.conversation_result.get('extracted_info', {}),
                    'user_preferences': state.conversation_result.get('context', {}).get('user_preferences', {}),
                    'intent': state.conversation_result.get('intent', '')
                }
                
                print(f"🔍 추천 요청: {recommendation_request}")
                
                # 추천 실행
                recommendations = self.recommendation_agent.recommend_products(
                    recommendation_request,
                    top_k=3
                )
                
                # 추천 결과 변환
                state.recommendations = [
                    {
                        'product_id': rec.product_id,
                        'product_name': rec.product_name,
                        'category': rec.category,
                        'rating': safe_float(getattr(rec, 'rating', 0.0)),
                        'review_count': safe_int(getattr(rec, 'review_count', 0)),
                        'recommendation_reason': rec.recommendation_reason,
                        'confidence_score': rec.confidence_score,
                        'url': getattr(rec, 'url', ''),
                        'image_url': getattr(rec, 'image_url', ''),
                        'representative_review': getattr(rec, 'representative_review', None)
                    }
                    for rec in recommendations
                ]
                
                duration = time.time() - start_time
                self._log_step(state, "recommendation_processing", state.recommendations, duration)
                
            else:
                print("🔍 추천이 필요하지 않음")
                duration = time.time() - start_time
                self._log_step(state, "recommendation_processing", "not_needed", duration)
                
        except Exception as e:
            duration = time.time() - start_time
            state.error = f"추천 처리 오류: {str(e)}"
            self._log_step(state, "recommendation_processing", None, duration)
        
        return state
    
    def _feedback_node(self, state: FashionState) -> FashionState:
        """피드백 처리 노드"""
        import time
        start_time = time.time()
        
        try:
            if state.conversation_result:
                extracted_info = state.conversation_result.get('extracted_info', {})
                feedback_type = extracted_info.get('feedback_type', '')
                
                state.user_feedback = {
                    'type': feedback_type,
                    'info': extracted_info,
                    'timestamp': datetime.now().isoformat()
                }
                
                duration = time.time() - start_time
                self._log_step(state, "feedback_processing", state.user_feedback, duration)
                
        except Exception as e:
            duration = time.time() - start_time
            state.error = f"피드백 처리 오류: {str(e)}"
            self._log_step(state, "feedback_processing", None, duration)
        
        return state
    
    def _response_generator_node(self, state: FashionState) -> FashionState:
        """응답 생성 노드"""
        import time
        start_time = time.time()
        
        try:
            response_parts = []
            
            # 기본 응답 생성
            if state.recommendations:
                response_parts.append("다음과 같은 상품들을 추천드립니다:")
                
                for i, rec in enumerate(state.recommendations[:3], 1):
                    response_parts.append(f"\n{i}. {rec['product_name']}")
                    response_parts.append(f"   - 카테고리: {rec['category']}")
                    response_parts.append(f"   - 평점: {rec['rating']}/5.0 ({rec['review_count']}개 리뷰)")
                    response_parts.append(f"   - 추천 이유: {rec['recommendation_reason']}")
                    
                    if rec.get('representative_review'):
                        response_parts.append(f"   - 대표 리뷰: \"{rec['representative_review']}\"")
            else:
                response_parts.append("죄송합니다. 요청하신 조건에 맞는 상품을 찾지 못했습니다.")
                response_parts.append("다른 조건으로 다시 검색해보시겠어요?")
            
            state.final_response = "\n".join(response_parts)
            
            duration = time.time() - start_time
            self._log_step(state, "response_generation", state.final_response, duration)
            
        except Exception as e:
            duration = time.time() - start_time
            state.error = f"응답 생성 오류: {str(e)}"
            self._log_step(state, "response_generation", None, duration)
        
        return state
    
    def _route_conversation(self, state: FashionState) -> str:
        """대화 분석 결과에 따른 라우팅"""
        if state.error:
            return "response_generator"
        
        if state.conversation_result:
            intent = state.conversation_result.get('intent', '')
            if 'feedback' in intent.lower():
                return "feedback_processor"
            elif state.conversation_result.get('requires_recommendation'):
                return "recommendation_agent"
            else:
                return "response_generator"
        
        return "response_generator"
    
    def _route_recommendation(self, state: FashionState) -> str:
        """추천 결과에 따른 라우팅"""
        if state.error:
            return "response_generator"
        
        if state.recommendations and len(state.recommendations) > 0:
            return "response_generator"
        else:
            return "response_generator"
    
    def _route_feedback(self, state: FashionState) -> str:
        """피드백 처리 결과에 따른 라우팅"""
        if state.error:
            return "response_generator"
        
        if state.user_feedback and state.user_feedback.get('type') in ['cheaper', 'different_style']:
            return "recommendation_agent"
        else:
            return "response_generator"
    
    def process_user_input(self, user_input: str) -> Dict[str, Any]:
        """사용자 입력 처리 - 워크플로우 실행"""
        print(f"\n🚀 워크플로우 시작: {user_input}")
        print("=" * 60)
        
        # 초기 상태 생성
        state = FashionState(user_input=user_input)
        
        # 워크플로우 실행
        try:
            # 1. 대화 분석
            state = self._conversation_node(state)
            
            # 2. 라우팅 결정
            next_step = self._route_conversation(state)
            print(f"🔄 라우팅: conversation → {next_step}")
            
            # 3. 추천 처리 (필요한 경우)
            if next_step == "recommendation_agent":
                state = self._recommendation_node(state)
                next_step = self._route_recommendation(state)
                print(f"🔄 라우팅: recommendation → {next_step}")
            
            # 4. 피드백 처리 (필요한 경우)
            elif next_step == "feedback_processor":
                state = self._feedback_node(state)
                next_step = self._route_feedback(state)
                print(f"🔄 라우팅: feedback → {next_step}")
                
                # 피드백 후 재추천이 필요한 경우
                if next_step == "recommendation_agent":
                    state = self._recommendation_node(state)
                    next_step = self._route_recommendation(state)
                    print(f"🔄 라우팅: re-recommendation → {next_step}")
            
            # 5. 응답 생성
            state = self._response_generator_node(state)
            
        except Exception as e:
            state.error = f"워크플로우 실행 오류: {str(e)}"
            state.final_response = "죄송합니다. 처리 중 오류가 발생했습니다."
        
        # 결과 반환
        result = {
            'response': state.final_response or "응답을 생성할 수 없습니다.",
            'recommendations': state.recommendations,
            'workflow_log': state.workflow_log,
            'error': state.error
        }
        
        print("\n" + "=" * 60)
        print("✅ 워크플로우 완료")
        print("=" * 60)
        
        return result
    
    def get_workflow_summary(self) -> Dict[str, Any]:
        """워크플로우 요약 정보"""
        return {
            'system_name': 'Simple LangGraph Fashion System',
            'version': '1.0.0',
            'nodes': [
                'conversation_agent',
                'recommendation_agent', 
                'feedback_processor',
                'response_generator'
            ],
            'features': [
                '상태 기반 워크플로우',
                '조건부 분기 로직',
                '멀티 에이전트 협업',
                '실시간 로깅'
            ]
        }

def main():
    """메인 함수 - 테스트 실행"""
    print("🎨 Simple LangGraph 패션 추천 시스템 테스트")
    
    # 샘플 데이터 생성
    sample_data = {
        'product_id': ['1', '2', '3', '4', '5'],
        'product_name': [
            '베이직 티셔츠', 
            '스트릿 반팔', 
            '꾸안꾸 무지', 
            '오버핏 후드',
            '빈티지 셔츠'
        ],
        'categories': ['상의', '상의', '상의', '상의', '상의'],
        'tags': [
            ['베이직', '캐주얼'], 
            ['스트릿', '힙합'], 
            ['베이직', '꾸안꾸'], 
            ['오버핏', '스트릿'],
            ['빈티지', '레트로']
        ],
        'rating': [4.8, 4.6, 4.9, 4.7, 4.5],
        'review_count': [1500, 800, 2200, 1200, 900],
        'description': [
            '베이직한 디자인의 티셔츠',
            '스트릿한 느낌의 반팔',
            '꾸안꾸 스타일의 무지 티',
            '오버핏 후드티',
            '빈티지한 느낌의 셔츠'
        ],
        'url': [
            'https://www.musinsa.com/products/1',
            'https://www.musinsa.com/products/2',
            'https://www.musinsa.com/products/3',
            'https://www.musinsa.com/products/4',
            'https://www.musinsa.com/products/5'
        ]
    }
    
    df = pd.DataFrame(sample_data)
    
    # 시스템 초기화
    system = SimpleLangGraphFashionSystem(df)
    
    # 테스트 쿼리들
    test_queries = [
        "안녕하세요!",
        "꾸안꾸 느낌의 반팔 추천해줘",
        "스트릿한 스타일의 티셔츠 보여줘",
        "좀 더 저렴한 걸로 보여줘",
        "빈티지한 느낌의 상의 추천해줘"
    ]
    
    print(f"\n🧪 {len(test_queries)}개 테스트 쿼리 실행")
    print("=" * 60)
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n{i}. 사용자: {query}")
        
        try:
            result = system.process_user_input(query)
            
            print(f"   응답: {result['response'][:100]}...")
            
            if result.get('recommendations'):
                print(f"   추천 상품 수: {len(result['recommendations'])}개")
            
            if result.get('error'):
                print(f"   오류: {result['error']}")
                
        except Exception as e:
            print(f"   오류 발생: {str(e)}")
    
    print("\n" + "=" * 60)
    print("✅ 테스트 완료")
    print("=" * 60)
    print("📊 워크플로우 요약:")
    summary = system.get_workflow_summary()
    for key, value in summary.items():
        print(f"   {key}: {value}")

if __name__ == "__main__":
    main() 