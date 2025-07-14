"""
LangGraph를 활용한 패션 추천 시스템
멀티 에이전트 협업 워크플로우
"""

import os
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_core.messages import HumanMessage, AIMessage
from langchain_openai import ChatOpenAI
import pandas as pd
import math

try:
    from agents.conversation_agent import ConversationAgent
    from agents.recommendation_agent import RecommendationAgent
    from simple_vector_db import SimpleVectorDB
except ImportError:
    print("기존 에이전트 모듈을 찾을 수 없습니다.")

@dataclass
class FashionState:
    """패션 추천 시스템 상태"""
    user_input: str
    conversation_result: Optional[Dict[str, Any]] = None
    recommendations: Optional[List[Dict[str, Any]]] = None
    user_feedback: Optional[Dict[str, Any]] = None
    final_response: Optional[str] = None
    error: Optional[str] = None


def safe_int(val, default=0):
    try:
        if val is None or (isinstance(val, float) and math.isnan(val)):
            return default
        return int(val)
    except Exception:
        return default

def safe_float(val, default=0.0):
    try:
        if val is None or (isinstance(val, float) and math.isnan(val)):
            return default
        return float(val)
    except Exception:
        return default


class LangGraphFashionSystem:
    """LangGraph 기반 패션 추천 시스템"""
    
    def __init__(self, products_df: pd.DataFrame, api_key: Optional[str] = None, reviews_data: Optional[Dict[str, List[Dict[str, Any]]]] = None):
        self.products_df = products_df
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        
        # 기존 에이전트들 초기화
        self.conversation_agent = ConversationAgent(api_key)
        self.recommendation_agent = RecommendationAgent(products_df, api_key, reviews_data)
        
        # 벡터 DB 매니저 초기화
        self.vector_db = SimpleVectorDB()
        self.vector_db.add_products(products_df)
        
        # LangGraph 워크플로우 생성
        self.workflow = self._create_workflow()
    
    def _create_workflow(self) -> StateGraph:
        """패션 추천 워크플로우 생성"""
        
        # 상태 그래프 생성
        workflow = StateGraph(FashionState) #  로그 확인 가능 - 
        
        # 노드 추가
        workflow.add_node("conversation_agent", self._conversation_node)
        workflow.add_node("recommendation_agent", self._recommendation_node)
        workflow.add_node("feedback_processor", self._feedback_node)
        workflow.add_node("response_generator", self._response_generator_node)
        
        # 시작점 설정
        workflow.set_entry_point("conversation_agent")
        
        # 조건부 엣지 추가
        workflow.add_conditional_edges(
            "conversation_agent",
            self._route_conversation,
            {
                "recommendation_needed": "recommendation_agent",
                "feedback": "feedback_processor",
                "general_chat": "response_generator"
            }
        )
        
        workflow.add_conditional_edges(
            "recommendation_agent",
            self._route_recommendation,
            {
                "success": "response_generator",
                "no_results": "response_generator",
                "error": "response_generator"
            }
        )
        
        workflow.add_conditional_edges(
            "feedback_processor",
            self._route_feedback,
            {
                "re_recommend": "recommendation_agent",
                "update_preferences": "response_generator",
                "error": "response_generator"
            }
        )
        
        # 종료점 설정
        workflow.add_edge("response_generator", END)
        
        return workflow.compile()
    
    def _conversation_node(self, state: FashionState) -> FashionState:
        """대화 에이전트 노드"""
        try:
            result = self.conversation_agent.process_user_input(state.user_input)
            state.conversation_result = result
        except Exception as e:
            state.error = f"대화 처리 오류: {str(e)}"
        
        return state
    
    def _recommendation_node(self, state: FashionState) -> FashionState:
        """추천 에이전트 노드 (조건에 따라 SQL 기반 또는 Vector DB 기반)"""
        try:
            print(f"🔍 추천 노드 실행 - conversation_result: {state.conversation_result}")
            print(f"🔍 requires_recommendation: {state.conversation_result.get('requires_recommendation') if state.conversation_result else None}")
            
            if state.conversation_result and state.conversation_result.get('requires_recommendation'):
                # 추천 요청 구성
                recommendation_request = {
                    'original_query': state.user_input,
                    'filters': state.conversation_result.get('extracted_info', {}),
                    'user_preferences': state.conversation_result.get('context', {}).get('user_preferences', {}),
                    'intent': state.conversation_result.get('intent', '')
                }
                
                print(f"🔍 추천 요청: {recommendation_request}")
                
                # RecommendationAgent를 통한 추천 (자동으로 방식 결정)
                recommendations = self.recommendation_agent.recommend_products(
                    recommendation_request,
                    top_k=3
                )
                
                print(f"🔍 추천 결과 수: {len(recommendations) if recommendations else 0}")
                
                # 추천 결과를 딕셔너리로 변환
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
                
                print(f"🔍 변환된 추천 결과: {state.recommendations}")
            else:
                print("🔍 추천이 필요하지 않거나 conversation_result가 없음")
        except Exception as e:
            print(f"🔍 추천 처리 오류: {str(e)}")
            state.error = f"추천 처리 오류: {str(e)}"
        
        return state
    
    def _feedback_node(self, state: FashionState) -> FashionState:
        """피드백 처리 노드"""
        try:
            if state.conversation_result:
                extracted_info = state.conversation_result.get('extracted_info', {})
                feedback_type = extracted_info.get('feedback_type', '')
                
                state.user_feedback = {
                    'type': feedback_type,
                    'info': extracted_info,
                    'timestamp': pd.Timestamp.now().isoformat()
                }
                
                # 피드백 타입에 따른 처리
                if feedback_type == 'cheaper':
                    # 가격대 조정
                    if 'filters' not in state.conversation_result:
                        state.conversation_result['filters'] = {}
                    state.conversation_result['filters']['price_range'] = 'lower'
                elif feedback_type == 'different_style':
                    # 스타일 변경
                    if 'filters' not in state.conversation_result:
                        state.conversation_result['filters'] = {}
                    state.conversation_result['filters']['style'] = 'alternative'
                
        except Exception as e:
            state.error = f"피드백 처리 오류: {str(e)}"
        
        return state
    
    def _response_generator_node(self, state: FashionState) -> FashionState:
        """최종 응답 생성 노드"""
        try:
            if state.error:
                state.final_response = f"죄송합니다. 오류가 발생했습니다: {state.error}"
                return state
            
            # 기본 응답
            base_response = state.conversation_result.get('response', '') if state.conversation_result else ''
            
            # 추천 결과가 있는 경우
            if state.recommendations:
                recommendation_text = "\n\n추천 상품:\n"
                for i, rec in enumerate(state.recommendations, 1):
                    recommendation_text += f"{i}. {rec['product_name']}\n"
                    recommendation_text += f"   {rec['recommendation_reason']}\n"
                    if rec.get('representative_review'):
                        recommendation_text += f"   대표 리뷰: \"{rec['representative_review']}\"\n"
                    if rec.get('url'):
                        recommendation_text += f"   링크: {rec['url']}\n"
                    recommendation_text += "\n"
                
                state.final_response = base_response + recommendation_text
            else:
                state.final_response = base_response
                
        except Exception as e:
            state.final_response = f"응답 생성 중 오류가 발생했습니다: {str(e)}"
        
        return state
    
    def _route_conversation(self, state: FashionState) -> str:
        """대화 결과에 따른 분기 결정"""
        if state.error:
            return "general_chat"
        
        if not state.conversation_result:
            return "general_chat"
        
        intent = state.conversation_result.get('intent', '')
        requires_recommendation = state.conversation_result.get('requires_recommendation', False)
        
        if requires_recommendation:
            return "recommendation_needed"
        elif intent == "feedback":
            return "feedback"
        else:
            return "general_chat"
    
    def _route_recommendation(self, state: FashionState) -> str:
        """추천 결과에 따른 분기 결정"""
        if state.error:
            return "error"
        
        if state.recommendations and len(state.recommendations) > 0:
            return "success"
        else:
            return "no_results"
    
    def _route_feedback(self, state: FashionState) -> str:
        """피드백 처리 결과에 따른 분기 결정"""
        if state.error:
            return "error"
        
        if state.user_feedback and state.user_feedback.get('type') in ['cheaper', 'different_style']:
            return "re_recommend"
        else:
            return "update_preferences"
    
    def process_user_input(self, user_input: str) -> Dict[str, Any]:
        """사용자 입력 처리"""
        # 초기 상태 생성
        initial_state = FashionState(user_input=user_input)
        
        # 워크플로우 실행
        try:
            final_state = self.workflow.invoke(initial_state)
            
            return {
                'response': final_state['final_response'],
                'conversation_result': final_state['conversation_result'],
                'recommendations': final_state['recommendations'],
                'user_feedback': final_state['user_feedback'],
                'error': final_state['error']
            }
            
        except Exception as e:
            return {
                'response': f"시스템 오류가 발생했습니다: {str(e)}",
                'error': str(e)
            }
    
    def get_workflow_summary(self) -> Dict[str, Any]:
        """워크플로우 요약 정보"""
        return {
            'conversation_summary': self.conversation_agent.get_conversation_summary(),
            'recommendation_summary': self.recommendation_agent.get_recommendation_summary() if self.recommendation_agent else {}
        }


def main():
    """LangGraph 패션 시스템 테스트"""
    
    # 샘플 데이터 생성
    sample_data = {
        'product_id': ['1', '2', '3'],
        'product_name': ['베이직 티셔츠', '스트릿 반팔', '꾸안꾸 무지'],
        'category': ['상의', '상의', '상의'],
        'style_keywords': [['베이직'], ['스트릿'], ['베이직', '꾸안꾸']],
        'rating': [4.8, 4.6, 4.9],
        'review_count': [1500, 800, 2200],
        'description': ['베이직 티셔츠', '스트릿 반팔', '꾸안꾸 무지']
    }
    
    df = pd.DataFrame(sample_data)
    
    # LangGraph 시스템 초기화
    system = LangGraphFashionSystem(df)
    
    # 테스트 대화
    test_inputs = [
        "안녕하세요!",
        "꾸안꾸 느낌 나는 반팔 추천해줘",
        "좀 더 저렴한 걸로 보여줘",
        "스트릿한 무드의 티셔츠 추천해줘",
        "감사합니다!"
    ]
    
    print("=== LangGraph 패션 추천 시스템 테스트 ===\n")
    
    for user_input in test_inputs:
        print(f"사용자: {user_input}")
        
        # 시스템 응답
        response = system.process_user_input(user_input)
        
        print(f"시스템: {response['response']}")
        
        if response.get('recommendations'):
            print(f"추천 상품 수: {len(response['recommendations'])}")
        
        if response.get('error'):
            print(f"오류: {response['error']}")
        
        print("\n" + "="*50 + "\n")
    
    # 워크플로우 요약
    summary = system.get_workflow_summary()
    print("=== 워크플로우 요약 ===")
    print(f"총 대화 턴: {summary['conversation_summary'].get('total_turns', 0)}")
    print(f"총 추천 수: {summary['recommendation_summary'].get('total_recommendations', 0)}")


if __name__ == "__main__":
    main() 