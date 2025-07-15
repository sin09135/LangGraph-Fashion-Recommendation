"""
LLM 기반 패션 추천 시스템 메인 클래스
대화 에이전트와 추천 에이전트를 통합하여 완전한 추천 시스템 제공
LangGraph 기반 워크플로우 지원
"""
#%%
import pandas as pd
from typing import Dict, List, Optional, Any
import sys
import os
import openai
import math

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

#%%
# 상위 디렉토리 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.data_processor import MusinsaDataProcessor
from utils.query_refiner import QueryRefiner
from agents.conversation_agent import ConversationAgent
from agents.recommendation_agent import RecommendationAgent, ProductRecommendation

# 리뷰 관련 import
try:
    from utils.review_analyzer import ReviewAnalyzer
    REVIEW_FEATURES_AVAILABLE = True

except ImportError:
    REVIEW_FEATURES_AVAILABLE = False
    print("리뷰 기능을 사용할 수 없습니다.")

# LangGraph 시스템 import (선택적)
try:
    from langgraph_fashion_system import LangGraphFashionSystem
    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False
    print("LangGraph 시스템을 사용할 수 없습니다. requirements.txt에서 langgraph 패키지를 설치하세요.")

# PostgreSQL 시스템 import (선택적)
try:
    from agents.postgresql_recommendation_agent import PostgreSQLRecommendationAgent
    from database.postgresql_manager import PostgreSQLManager
    POSTGRESQL_AVAILABLE = True
except ImportError:
    POSTGRESQL_AVAILABLE = False
    print("PostgreSQL 시스템을 사용할 수 없습니다. psycopg2 패키지를 설치하세요.")


class LLMFashionRecommendationSystem:
    """LLM 기반 패션 추천 시스템"""
    
    def __init__(self, data_dir: str = "data", use_langgraph: bool = False, use_rdb: bool = False, use_postgresql: bool = False):
        self.data_dir = data_dir
        self.use_langgraph = use_langgraph
        self.use_rdb = use_rdb
        self.use_postgresql = use_postgresql
        
        # 데이터 프로세서 초기화
        self.data_processor = MusinsaDataProcessor(data_dir)
        
        # 리뷰 데이터 로드
        self.reviews_data = self.data_processor.load_reviews_data()
        
        # LangGraph 시스템 초기화
        self.langgraph_system = None
        if use_langgraph:
            self._init_langgraph_system()
        
        # RDB 시스템 초기화
        self.rdb_agent = None
        if use_rdb:
            self._init_rdb_system()
        
        # PostgreSQL 시스템 초기화
        self.postgresql_agent = None
        if use_postgresql:
            self._init_postgresql_system()
        
        # 기존 시스템 초기화 (RDB나 PostgreSQL을 사용하지 않는 경우)
        if not use_rdb and not use_postgresql:
            self._load_and_process_data()
        
        # 대화 에이전트 초기화
        self.conversation_agent = ConversationAgent()
        
        # 쿼리 정제기 초기화
        self.query_refiner = QueryRefiner()

    def _init_langgraph_system(self):
        """LangGraph 시스템 초기화"""
        try:
            from langgraph_fashion_system import LangGraphFashionSystem
            
            print("🚀 LangGraph 시스템 초기화 중...")
            
            # 데이터 로드 및 전처리
            data = self.data_processor.load_data()
            
            if 'products' in data:
                processed_df = self.data_processor.preprocess_products(data['products'])
                processed_df = self.data_processor.extract_style_keywords(processed_df)
                self.products_df = self.data_processor.create_product_embeddings_data(processed_df)
                print(f"CSV 데이터 로드 완료: {len(self.products_df)}개 상품")
            elif 'successful' in data:
                processed_df = self.data_processor.preprocess_products(data['successful'])
                processed_df = self.data_processor.extract_style_keywords(processed_df)
                self.products_df = self.data_processor.create_product_embeddings_data(processed_df)
                print(f"JSON 데이터 로드 완료: {len(self.products_df)}개 상품")
            
            # LangGraph 시스템 초기화
            self.langgraph_system = LangGraphFashionSystem(
                self.products_df, 
                self.data_processor.api_key, # 실제 API 키 사용
                reviews_data=self.reviews_data
            )
            print("✅ LangGraph 시스템 초기화 완료")
            
        except Exception as e:
            print(f"❌ LangGraph 시스템 초기화 실패: {e}")
            self.use_langgraph = False

    def _init_rdb_system(self):
        """RDB 시스템 초기화"""
        try:
            from agents.rdb_recommendation_agent import RDBRecommendationAgent
            from database.rdb_manager import RDBManager
            
            print("🗄️ RDB 시스템 초기화 중...")
            
            # RDB 매니저 초기화
            rdb_manager = RDBManager()
            
            # 데이터 로드 및 RDB에 삽입
            data = self.data_processor.load_data()
            
            if 'products' in data:
                processed_df = self.data_processor.preprocess_products(data['products'])
                processed_df = self.data_processor.extract_style_keywords(processed_df)
                rdb_manager.insert_products_from_dataframe(processed_df)
                print(f"RDB에 {len(processed_df)}개 상품 데이터 삽입 완료")
            elif 'successful' in data:
                processed_df = self.data_processor.preprocess_products(data['successful'])
                processed_df = self.data_processor.extract_style_keywords(processed_df)
                rdb_manager.insert_products_from_dataframe(processed_df)
                print(f"RDB에 {len(processed_df)}개 상품 데이터 삽입 완료")
            
            # RDB 추천 에이전트 초기화
            self.rdb_agent = RDBRecommendationAgent()
            
            print("✅ RDB 시스템 초기화 완료")
            
        except Exception as e:
            print(f"❌ RDB 시스템 초기화 실패: {e}")
            self.use_rdb = False

    def _init_postgresql_system(self):
        """PostgreSQL 시스템 초기화"""
        try:
            from agents.postgresql_recommendation_agent import PostgreSQLRecommendationAgent
            from database.postgresql_manager import PostgreSQLManager
            
            print("🐘 PostgreSQL 시스템 초기화 중...")
            
            # PostgreSQL 매니저 초기화
            pg_manager = PostgreSQLManager(
                host="localhost",
                port=5432,
                database="fashion_recommendation",
                user="postgres",
                password="password"
            )
            
            # 데이터 로드 및 PostgreSQL에 삽입
            data = self.data_processor.load_data()
            
            if 'products' in data:
                processed_df = self.data_processor.preprocess_products(data['products'])
                processed_df = self.data_processor.extract_style_keywords(processed_df)
                pg_manager.insert_products_from_dataframe(processed_df)
                print(f"PostgreSQL에 {len(processed_df)}개 상품 데이터 삽입 완료")
            elif 'successful' in data:
                processed_df = self.data_processor.preprocess_products(data['successful'])
                processed_df = self.data_processor.extract_style_keywords(processed_df)
                pg_manager.insert_products_from_dataframe(processed_df)
                print(f"PostgreSQL에 {len(processed_df)}개 상품 데이터 삽입 완료")
            
            # PostgreSQL 추천 에이전트 초기화
            self.postgresql_agent = PostgreSQLRecommendationAgent(
                host="localhost",
                port=5432,
                database="fashion_recommendation",
                user="postgres",
                password="password"
            )
            
            print("✅ PostgreSQL 시스템 초기화 완료")
            
        except Exception as e:
            print(f"❌ PostgreSQL 시스템 초기화 실패: {e}")
            self.use_postgresql = False

    def _load_and_process_data(self):
        """데이터 로드 및 전처리"""
        print("데이터 로드 중...")
        
        # 데이터 로드
        data = self.data_processor.load_data()
        
        # CSV 데이터 우선 사용 (이미지 경로 포함)
        if 'products' in data:
            # 상품 데이터 전처리
            processed_df = self.data_processor.preprocess_products(data['products'])
            
            # 스타일 키워드 추출
            processed_df = self.data_processor.extract_style_keywords(processed_df)
            
            # 임베딩 데이터 생성
            self.products_df = self.data_processor.create_product_embeddings_data(processed_df)
            
            # 추천 에이전트 초기화 (리뷰 데이터 포함)
            self.recommendation_agent = RecommendationAgent(
                self.products_df, 
                reviews_data=self.reviews_data
            )
            
            print(f"CSV 데이터 로드 완료: {len(self.products_df)}개 상품")
        elif 'successful' in data:
            # 기존 JSON 데이터 사용 (백업)
            processed_df = self.data_processor.preprocess_products(data['successful'])
            
            # 스타일 키워드 추출
            processed_df = self.data_processor.extract_style_keywords(processed_df)
            
            # 임베딩 데이터 생성
            self.products_df = self.data_processor.create_product_embeddings_data(processed_df)
            
            # 추천 에이전트 초기화 (리뷰 데이터 포함)
            self.recommendation_agent = RecommendationAgent(
                self.products_df, 
                reviews_data=self.reviews_data
            )
            
            print(f"JSON 데이터 로드 완료: {len(self.products_df)}개 상품")
        else:
            print("데이터 로드 실패")
    
    def process_user_input(self, user_input: str) -> Dict[str, Any]:
        """사용자 입력 처리 및 응답 생성"""
        # LangGraph 시스템 사용 시
        if self.use_langgraph and self.langgraph_system:
            result = self.langgraph_system.process_user_input(user_input)
            result['text'] = result.pop('response', '')
            # intent/confidence를 conversation_result에서 꺼내 최상위에 추가
            conv = result.get('conversation_result', {})
            result['intent'] = conv.get('intent')
            result['confidence'] = conv.get('confidence', 0.0)
            return result
        
        # PostgreSQL 시스템 사용 시
        if self.use_postgresql and self.postgresql_agent:
            return self._process_user_input_postgresql(user_input)
        
        # RDB 시스템 사용 시
        if self.use_rdb and self.rdb_agent:
            return self._process_user_input_rdb(user_input)
        
        # 기존 순차 처리 시스템
        return self._process_user_input_sequential(user_input)
    
    def _process_user_input_sequential(self, user_input: str) -> Dict[str, Any]:
        """기존 순차 처리 방식"""
        
        # 1. 대화 에이전트로 의도 탐지 및 응답 생성
        conversation_result = self.conversation_agent.process_user_input(user_input)
        
        # 2. 추천이 필요한 경우 추천 수행
        recommendations = []
        if conversation_result['requires_recommendation']:
            # 쿼리 정제
            refined_query = self.query_refiner.refine_query(
                user_input, 
                context=conversation_result['context']
            )
            
            # 추천 요청 구성
            recommendation_request = {
                'original_query': user_input,
                'filters': refined_query['filters'],
                'user_preferences': conversation_result['context'].get('user_preferences', {}),
                'intent': conversation_result['intent']
            }
            
            # 상품 추천
            if self.recommendation_agent:
                recommendations = self.recommendation_agent.recommend_products(
                    recommendation_request, 
                    top_k=3
                )
        
        # 3. 최종 응답 구성
        response = {
            'text': conversation_result['response'],
            'intent': conversation_result['intent'],
            'confidence': conversation_result['confidence'],
            'recommendations': [
                {
                    'product_id': rec.product_id,
                    'product_name': rec.product_name,
                    'category': rec.category,
                    'rating': safe_float(getattr(rec, 'rating', 0.0)),
                    'review_count': safe_int(getattr(rec, 'review_count', 0)),
                    'recommendation_reason': rec.recommendation_reason,
                    'confidence_score': safe_float(getattr(rec, 'confidence_score', 0.0)),
                    'url': getattr(rec, 'url', ''),
                    'image_url': getattr(rec, 'image_url', ''),
                    'representative_review': getattr(rec, 'representative_review', None)
                }
                for rec in recommendations
            ],
            'context': conversation_result['context']
        }
        
        return response

    def _process_user_input_postgresql(self, user_input: str) -> Dict[str, Any]:
        """PostgreSQL 기반 사용자 입력 처리"""
        
        # 1. 대화 에이전트로 의도 탐지 및 응답 생성
        conversation_result = self.conversation_agent.process_user_input(user_input)
        
        # 2. 추천이 필요한 경우 PostgreSQL 기반 추천 수행
        recommendations = []
        if conversation_result['requires_recommendation']:
            # 쿼리 정제
            refined_query = self.query_refiner.refine_query(
                user_input, 
                context=conversation_result['context']
            )
            
            # 추천 요청 구성
            recommendation_request = {
                'original_query': user_input,
                'filters': refined_query['filters'],
                'user_preferences': conversation_result['context'].get('user_preferences', {}),
                'intent': conversation_result['intent'],
                'user_id': 'anonymous'  # 실제로는 사용자 ID 사용
            }
            
            # PostgreSQL 기반 상품 추천
            if self.postgresql_agent:
                recommendations = self.postgresql_agent.recommend_products(
                    recommendation_request, 
                    top_k=3
                )
        
        # 3. 최종 응답 구성
        response = {
            'text': conversation_result['response'],
            'intent': conversation_result['intent'],
            'confidence': conversation_result['confidence'],
            'recommendations': [
                {
                    'product_id': rec.product_id,
                    'product_name': rec.product_name,
                    'category': rec.category,
                    'rating': safe_float(getattr(rec, 'rating', 0.0)),
                    'review_count': safe_int(getattr(rec, 'review_count', 0)),
                    'recommendation_reason': rec.recommendation_reason,
                    'confidence_score': safe_float(getattr(rec, 'confidence_score', 0.0)),
                    'url': getattr(rec, 'url', ''),
                    'image_url': getattr(rec, 'image_url', ''),
                    'representative_review': getattr(rec, 'representative_review', None)
                }
                for rec in recommendations
            ],
            'context': conversation_result['context']
        }
        
        return response

    def _process_user_input_rdb(self, user_input: str) -> Dict[str, Any]:
        """RDB 기반 사용자 입력 처리"""
        
        # 1. 대화 에이전트로 의도 탐지 및 응답 생성
        conversation_result = self.conversation_agent.process_user_input(user_input)
        
        # 2. 추천이 필요한 경우 RDB 기반 추천 수행
        recommendations = []
        if conversation_result['requires_recommendation']:
            # 쿼리 정제
            refined_query = self.query_refiner.refine_query(
                user_input, 
                context=conversation_result['context']
            )
            
            # 추천 요청 구성
            recommendation_request = {
                'original_query': user_input,
                'filters': refined_query['filters'],
                'user_preferences': conversation_result['context'].get('user_preferences', {}),
                'intent': conversation_result['intent'],
                'user_id': 'anonymous'  # 실제로는 사용자 ID 사용
            }
            
            # RDB 기반 상품 추천
            if self.rdb_agent:
                recommendations = self.rdb_agent.recommend_products(
                    recommendation_request, 
                    top_k=3
                )
        
        # 3. 최종 응답 구성
        response = {
            'text': conversation_result['response'],
            'intent': conversation_result['intent'],
            'confidence': conversation_result['confidence'],
            'recommendations': [
                {
                    'product_id': rec.product_id,
                    'product_name': rec.product_name,
                    'category': rec.category,
                    'rating': safe_float(getattr(rec, 'rating', 0.0)),
                    'review_count': safe_int(getattr(rec, 'review_count', 0)),
                    'recommendation_reason': rec.recommendation_reason,
                    'confidence_score': safe_float(getattr(rec, 'confidence_score', 0.0)),
                    'url': getattr(rec, 'url', ''),
                    'image_url': getattr(rec, 'image_url', ''),
                    'representative_review': getattr(rec, 'representative_review', None)
                }
                for rec in recommendations
            ],
            'context': conversation_result['context']
        }
        
        return response
    
    def get_conversation_summary(self) -> Dict[str, Any]:
        """대화 요약 정보 반환"""
        if self.use_langgraph and self.langgraph_system:
            summary = self.langgraph_system.get_workflow_summary()
            return summary.get('conversation_summary', {})
        return self.conversation_agent.get_conversation_summary()
    
    def get_recommendation_summary(self) -> Dict[str, Any]:
        """추천 요약 정보 반환"""
        if self.use_langgraph and self.langgraph_system:
            summary = self.langgraph_system.get_workflow_summary()
            return summary.get('recommendation_summary', {})
        if self.recommendation_agent:
            return self.recommendation_agent.get_recommendation_summary()
        return {}
    
    def reset_conversation(self):
        """대화 초기화"""
        self.conversation_agent.reset_conversation()
    
    def get_user_preferences(self) -> Dict[str, Any]:
        """사용자 선호도 반환"""
        return self.conversation_agent.user_preferences.copy()
    
    def switch_to_langgraph(self):
        """LangGraph 시스템으로 전환"""
        if LANGGRAPH_AVAILABLE and self.products_df is not None:
            self.langgraph_system = LangGraphFashionSystem(self.products_df, self.data_processor.api_key)
            self.use_langgraph = True
            print("LangGraph 기반 워크플로우 시스템으로 전환되었습니다.")
        else:
            print("LangGraph 시스템을 사용할 수 없습니다.")
    
    def switch_to_sequential(self):
        """순차 처리 시스템으로 전환"""
        self.use_langgraph = False
        print("기존 순차 처리 시스템으로 전환되었습니다.")


def main():
    """메인 추천 시스템 테스트"""
    
    # 기본값으로 순차 처리 시스템 사용 (무한 루프 방지)
    use_langgraph = False
    use_postgresql = False
    use_rdb = False
    
    print("=== LLM 기반 패션 추천 시스템 테스트 (순차 처리) ===")
    print("LangGraph: 비활성화 (무한 루프 방지)")
    print("PostgreSQL: 비활성화")
    print("RDB: 비활성화")
    print("순차 처리 시스템 사용\n")
    
    # 시스템 초기화
    system = LLMFashionRecommendationSystem(
        use_langgraph=use_langgraph, 
        use_rdb=use_rdb, 
        use_postgresql=use_postgresql
    )
    
    # 테스트 대화
    test_conversation = [
        "와이드핏 바지 추천해줘",
        "가격대가 낮은 걸로 보여줘"
    ]
    
    # 시스템 타입 결정
    if system.use_langgraph:
        system_type = "LangGraph"
    elif system.use_postgresql:
        system_type = "PostgreSQL"
    elif system.use_rdb:
        system_type = "RDB"
    else:
        system_type = "순차 처리"
    
    print(f"=== LLM 기반 패션 추천 시스템 테스트 ({system_type}) ===\n")
    
    for user_input in test_conversation:
        print(f"사용자: {user_input}")
        
        # 시스템 응답
        response = system.process_user_input(user_input)
        
        print(f"시스템: {response['text']}")
        print(f"의도: {response['intent']} (신뢰도: {response['confidence']:.2f})\n")
        # 추천 결과 출력
        if 'recommendations' in response and response['recommendations']:
            print("추천 상품 리스트:")
            for rec in response['recommendations']:
                print(f"- {rec.get('product_name', '')} | {rec.get('url', '')} | {rec.get('image_url', '')}")
        elif 'recommendations' in response:
            print("추천 결과가 없습니다.")
        print("\n" + "="*50 + "\n")
    
    # 요약 정보 출력
    print("=== 시스템 요약 ===")
    conv_summary = system.get_conversation_summary()
    rec_summary = system.get_recommendation_summary()
    
    print(f"총 대화 턴: {conv_summary.get('total_turns', 0)}")
    print(f"사용자 선호도: {conv_summary.get('user_preferences', {})}")
    print(f"총 추천 수: {rec_summary.get('total_recommendations', 0)}")


if __name__ == "__main__":
    main()

# 테스트용 코드
# openai.api_key = os.environ.get("OPENAI_API_KEY")
# print(openai.Model.list()) 
# # %%
# import openai

# openai.api_key = os.environ.get("OPENAI_API_KEY")

# models = openai.models.list()
# print(models)
# %%
