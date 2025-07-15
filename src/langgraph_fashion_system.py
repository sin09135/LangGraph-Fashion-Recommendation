"""
LangGraph를 활용한 패션 추천 시스템
멀티 에이전트 협업 워크플로우
"""
#%%
import os
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from langgraph.graph import StateGraph, END
# from langgraph.prebuilt import ToolNode  # 최신 버전에서 제거됨
from langchain_core.messages import HumanMessage, AIMessage
from langchain_openai import ChatOpenAI
from langchain_core.runnables.graph import CurveStyle, MermaidDrawMethod, NodeStyles
import pandas as pd
import math

try:
    from agents.conversation_agent import ConversationAgent
    from agents.recommendation_agent import RecommendationAgent
    from agents.recommendation_evaluator import RecommendationEvaluator, RecommendationContext
    from simple_vector_db import SimpleVectorDB
    
except ImportError:
    print("기존 에이전트 모듈을 찾을 수 없습니다.")

@dataclass
class FashionState:
    """패션 추천 시스템 상태"""
    user_input: str
    conversation_result: Optional[Dict[str, Any]] = None
    recommendations: Optional[List[Dict[str, Any]]] = None
    evaluation_result: Optional[Dict[str, Any]] = None
    user_feedback: Optional[Dict[str, Any]] = None
    recommendation_adjustment: Optional[Dict[str, Any]] = None  # 추천 재조정 정보
    feedback_detection: Optional[Dict[str, Any]] = None  # 피드백 감지 결과
    final_response: Optional[str] = None
    error: Optional[str] = None
    adjustment_count: int = 0  # 재조정 횟수 (무한 루프 방지)


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
        
        # Evaluator 초기화
        self.evaluator = RecommendationEvaluator(products_df, api_key)
        
        # 벡터 DB 매니저 초기화
        self.vector_db = SimpleVectorDB()
        self.vector_db.add_products(products_df)
        
        # LangGraph 워크플로우 생성
        self.workflow = self._create_workflow()
    
    def _create_workflow(self) -> StateGraph:
        """패션 추천 워크플로우 생성"""
        
        # 상태 그래프 생성
        workflow = StateGraph(FashionState) #  로그 확인 가능       
        # 노드 추가
        workflow.add_node("conversation_agent", self._conversation_node)
        workflow.add_node("recommendation_agent", self._recommendation_node)
        workflow.add_node("evaluator", self._evaluator_node)
        workflow.add_node("recommendation_adjustment", self._recommendation_adjustment_node)  # 추천 재조정
        workflow.add_node("feedback_detection", self._feedback_detection_node)  # 피드백 감지
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
                "success": "evaluator",
                "no_results": "response_generator",
                "error": "response_generator"
            }
        )
        
        workflow.add_conditional_edges(
            "evaluator",
            self._route_evaluation,
            {
                "quality_good": "feedback_detection",  # 품질 우수시 피드백 감지로
                "needs_improvement": "recommendation_adjustment"  # 품질 개선 필요시 재조정으로
            }
        )
        
        # 추천 재조정 후 다시 추천
        workflow.add_edge("recommendation_adjustment", "recommendation_agent")
        
        # 피드백 감지 후 분기
        workflow.add_conditional_edges(
            "feedback_detection",
            self._route_feedback_detection,
            {
                "positive_feedback": "response_generator",  # 긍정 평가
                "condition_change": "recommendation_adjustment",  # 조건 변경 요청
                "negative_feedback": "recommendation_adjustment",  # 부정 평가
                "more_items": "recommendation_adjustment",  # 더 보고 싶음
                "behavior_feedback": "feedback_processor"  # 행동 기반 피드백
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
        
        self.compiled_workflow = workflow.compile()
        return self.compiled_workflow
    
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
    
    def _evaluator_node(self, state: FashionState) -> FashionState:
        """추천 품질 평가 노드"""
        try:
            print("📊 Evaluator 노드 실행...")
            
            if state.recommendations and len(state.recommendations) > 0:
                # 추천 컨텍스트 생성
                context = RecommendationContext(
                    user_query=state.user_input,
                    user_preferences=state.conversation_result.get('context', {}).get('user_preferences', {}) if state.conversation_result else {},
                    filters=state.conversation_result.get('extracted_info', {}) if state.conversation_result else {},
                    recommendation_count=3,  # 기본값
                    user_history=[]  # 실제로는 사용자 히스토리에서 가져와야 함
                )
                
                # 추천 결과를 ProductRecommendation 형태로 변환
                recommendations = []
                for rec_dict in state.recommendations:
                    class MockRecommendation:
                        def __init__(self, **kwargs):
                            for key, value in kwargs.items():
                                setattr(self, key, value)
                    
                    rec = MockRecommendation(
                        product_id=rec_dict['product_id'],
                        product_name=rec_dict['product_name'],
                        category=rec_dict['category'],
                        style_keywords=[],  # 실제로는 추출해야 함
                        confidence_score=rec_dict.get('confidence_score', 0.0),
                        rating=rec_dict.get('rating', 0.0),
                        review_count=rec_dict.get('review_count', 0),
                        price='가격 정보 없음'
                    )
                    recommendations.append(rec)
                
                # 평가 실행
                evaluation = self.evaluator.evaluate_recommendations(recommendations, context)
                
                # 평가 결과 저장
                state.evaluation_result = {
                    'overall_score': evaluation.overall_score,
                    'quality_level': evaluation.quality_level,
                    'relevance_score': evaluation.relevance_score,
                    'diversity_score': evaluation.diversity_score,
                    'novelty_score': evaluation.novelty_score,
                    'coverage_score': evaluation.coverage_score,
                    'improvement_suggestions': evaluation.improvement_suggestions
                }
                
                print(f"📊 평가 완료: {evaluation.quality_level} (점수: {evaluation.overall_score:.3f})")
            else:
                print("📊 평가할 추천 결과가 없습니다.")
                state.evaluation_result = {
                    'overall_score': 0.0,
                    'quality_level': '개선필요',
                    'improvement_suggestions': ['추천 결과가 없습니다.']
                }
                
        except Exception as e:
            print(f"📊 평가 처리 오류: {str(e)}")
            state.error = f"평가 처리 오류: {str(e)}"
            state.evaluation_result = {
                'overall_score': 0.0,
                'quality_level': '오류',
                'improvement_suggestions': [f'평가 중 오류 발생: {str(e)}']
            }
        
        return state
    
    def _recommendation_adjustment_node(self, state: FashionState) -> FashionState:
        """추천 재조정 노드"""
        try:
            print("🔄 추천 재조정 노드 실행...")
            
            # 평가 결과에 따른 재조정 전략 결정
            if state.evaluation_result:
                quality_level = state.evaluation_result.get('quality_level', '개선필요')
                suggestions = state.evaluation_result.get('improvement_suggestions', [])
                
                # 재조정 전략 설정
                adjustment_strategy = {
                    'reason': f"품질 개선 필요: {quality_level}",
                    'suggestions': suggestions,
                    'adjustment_type': 'quality_improvement',
                    'filters_adjustment': {},
                    'diversity_increase': True,
                    'confidence_threshold_adjustment': 0.1
                }
                
                state.recommendation_adjustment = adjustment_strategy
                print(f"🔄 재조정 전략: {adjustment_strategy['reason']}")
            else:
                # 기본 재조정
                state.recommendation_adjustment = {
                    'reason': '기본 재조정',
                    'adjustment_type': 'default',
                    'filters_adjustment': {},
                    'diversity_increase': True
                }
                
        except Exception as e:
            print(f"🔄 재조정 처리 오류: {str(e)}")
            state.error = f"재조정 처리 오류: {str(e)}"
        
        return state
    
    def _feedback_detection_node(self, state: FashionState) -> FashionState:
        """사용자 피드백 감지 노드"""
        try:
            print("🗣 피드백 감지 노드 실행...")
            
            # 사용자 입력에서 피드백 유형 감지
            user_input = state.user_input.lower()
            
            feedback_type = "positive_feedback"  # 기본값
            
            # 피드백 유형 분류
            if any(word in user_input for word in ['좋아', '맘에 들어', '괜찮아', '좋은데', '예쁘다']):
                feedback_type = "positive_feedback"
            elif any(word in user_input for word in ['다른', '바꿔', '변경', '조건']):
                feedback_type = "condition_change"
            elif any(word in user_input for word in ['싫어', '별로', '안좋아', '마음에 안들어']):
                feedback_type = "negative_feedback"
            elif any(word in user_input for word in ['더', '추가', '다른 것도', '더 보여줘']):
                feedback_type = "more_items"
            elif any(word in user_input for word in ['클릭', '구매', '장바구니', '좋아요']):
                feedback_type = "behavior_feedback"
            
            state.feedback_detection = {
                'feedback_type': feedback_type,
                'user_input': state.user_input,
                'confidence': 0.8
            }
            
            print(f"🗣 감지된 피드백 유형: {feedback_type}")
            
        except Exception as e:
            print(f"🗣 피드백 감지 오류: {str(e)}")
            state.error = f"피드백 감지 오류: {str(e)}"
        
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
                
                # 평가 결과 추가
                if state.evaluation_result:
                    evaluation_text = f"\n📊 추천 품질 평가: {state.evaluation_result['quality_level']} (점수: {state.evaluation_result['overall_score']:.3f})\n"
                    if state.evaluation_result.get('improvement_suggestions'):
                        evaluation_text += "💡 개선 제안:\n"
                        for suggestion in state.evaluation_result['improvement_suggestions']:
                            evaluation_text += f"   • {suggestion}\n"
                    recommendation_text += evaluation_text
                
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
    
    def _route_evaluation(self, state: FashionState) -> str:
        """평가 결과에 따른 분기 결정"""
        if state.error:
            return "quality_good"  # 오류가 있어도 일단 진행
        
        if not state.evaluation_result:
            return "quality_good"  # 평가 결과가 없으면 일단 진행
        
        quality_level = state.evaluation_result.get('quality_level', '개선필요')
        overall_score = state.evaluation_result.get('overall_score', 0.0)
        
        # 재조정 횟수 확인 (무한 루프 방지)
        adjustment_count = getattr(state, 'adjustment_count', 0)
        if adjustment_count >= 2:  # 최대 2번까지만 재조정
            print(f"📊 최대 재조정 횟수 도달: {adjustment_count}회")
            return "quality_good"
        
        # 품질이 우수하거나 보통이면 진행, 개선필요면 재조정
        if quality_level in ['우수', '보통'] or overall_score >= 0.6:
            return "quality_good"
        else:
            print(f"📊 품질 개선 필요: {quality_level} (점수: {overall_score:.3f})")
            # 재조정 횟수 증가
            state.adjustment_count = adjustment_count + 1
            return "needs_improvement"
    
    def _route_feedback_detection(self, state: FashionState) -> str:
        """피드백 감지 결과에 따른 분기 결정"""
        if state.error:
            return "positive_feedback"  # 오류시 기본값
        
        if not state.feedback_detection:
            return "positive_feedback"  # 피드백 감지 결과가 없으면 기본값
        
        feedback_type = state.feedback_detection.get('feedback_type', 'positive_feedback')
        print(f"🗣 피드백 라우팅: {feedback_type}")
        
        return feedback_type
    
    def process_user_input(self, user_input: str) -> Dict[str, Any]:
        """사용자 입력 처리"""
        # 초기 상태 생성
        initial_state = FashionState(user_input=user_input)
        
        # 워크플로우 실행
        try:
            final_state = self.compiled_workflow.invoke(initial_state)
            
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
            'recommendation_summary': self.recommendation_agent.get_recommendation_summary() if self.recommendation_agent else {},
            'evaluation_summary': self.evaluator.get_evaluation_summary() if self.evaluator else {}
        }
    
    def visualize_workflow(self, 
                          curve_style: CurveStyle = CurveStyle.LINEAR) -> str:
        """워크플로우를 Mermaid 다이어그램으로 시각화"""
        try:
            # Mermaid 다이어그램 생성
            mermaid_code = self.compiled_workflow.get_graph().draw_mermaid(
                curve_style=curve_style
            )
            
            return mermaid_code
            
        except Exception as e:
            print(f"워크플로우 시각화 오류: {e}")
            return f"시각화 오류: {str(e)}"
    
    def display_workflow(self, 
                        curve_style: CurveStyle = CurveStyle.LINEAR):
        """Jupyter 환경에서 워크플로우 시각화 표시"""
        try:
            from IPython.display import Image, display
            
            # LangGraph의 내장 PNG 생성 기능 사용
            png_image = self.compiled_workflow.get_graph().draw_mermaid_png(
                curve_style=curve_style
            )
            
            print("=== LangGraph 워크플로우 시각화 ===")
            display(Image(png_image))
            
            # Mermaid 코드도 함께 출력
            mermaid_code = self.visualize_workflow(curve_style)
            print("\n=== Mermaid 코드 ===")
            print(mermaid_code)
            
        except ImportError:
            print("IPython이 설치되지 않았습니다. Mermaid 코드만 출력합니다.")
            print(self.visualize_workflow(curve_style))
        except Exception as e:
            print(f"워크플로우 표시 오류: {e}")
            print("Mermaid 코드:")
            print(self.visualize_workflow(curve_style))
    
    def display_workflow_simple(self):
        """간단한 워크플로우 시각화 (IPython에서 바로 사용)"""
        try:
            from IPython.display import Image, display
            
            # 바로 이미지로 표시
            png_image = self.compiled_workflow.get_graph().draw_mermaid_png()
            display(Image(png_image))
            
        except ImportError:
            print("IPython이 설치되지 않았습니다.")
        except Exception as e:
            print(f"워크플로우 시각화 오류: {e}")


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
        "블랙 반팔 추천해줘",
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
    
    # 평가 요약
    eval_summary = summary.get('evaluation_summary', {})
    if 'average_score' in eval_summary:
        print(f"평균 평가 점수: {eval_summary['average_score']:.3f}")
        print(f"품질 분포: {eval_summary['quality_distribution']}")
        print(f"최근 트렌드: {eval_summary['recent_trend']}")
    
    # LangGraph 워크플로우 시각화
    print("\n=== LangGraph 워크플로우 시각화 ===")
    try:
        mermaid_code = system.visualize_workflow()
        print("Mermaid 다이어그램 코드:")
        print(mermaid_code)
        
        # Mermaid 코드를 파일로 저장
        with open("langgraph_workflow_auto.mmd", "w", encoding="utf-8") as f:
            f.write(mermaid_code)
        print("\nMermaid 코드가 'langgraph_workflow_auto.mmd' 파일로 저장되었습니다.")
        
    except Exception as e:
        print(f"워크플로우 시각화 실패: {e}")
        print("수동으로 만든 Mermaid 다이어그램을 사용하세요.")


if __name__ == "__main__":
    main() 