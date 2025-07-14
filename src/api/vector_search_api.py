"""
벡터 검색 API 서버
FastAPI 기반 벡터 DB 검색 API
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import uvicorn
import sys
import os

# 프로젝트 루트 경로 추가
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from advanced_vector_db import AdvancedVectorDB
from utils.data_processor import MusinsaDataProcessor

# FastAPI 앱 생성
app = FastAPI(
    title="패션 추천 벡터 검색 API",
    description="LLM 기반 패션 추천 시스템의 벡터 검색 API",
    version="1.0.0"
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 전역 변수
vector_db = None
data_processor = None

# Pydantic 모델
class SearchRequest(BaseModel):
    query: str
    top_k: int = 10
    use_hybrid: bool = True
    category: Optional[str] = None
    min_rating: Optional[float] = None

class SearchResponse(BaseModel):
    query: str
    results: List[Dict[str, Any]]
    total_results: int
    search_time: float
    performance_stats: Dict[str, Any]

class TrendingRequest(BaseModel):
    top_k: int = 10
    category: Optional[str] = None

class RecommendationRequest(BaseModel):
    user_query: str
    top_k: int = 5

@app.on_event("startup")
async def startup_event():
    """서버 시작 시 벡터 DB 초기화"""
    global vector_db, data_processor
    
    try:
        print("벡터 DB 초기화 중...")
        
        # 데이터 로드 및 전처리
        data_processor = MusinsaDataProcessor(data_dir="../../data")
        data = data_processor.load_data()
        
        if 'successful' not in data:
            raise Exception("성공 데이터를 찾을 수 없습니다.")
        
        # 데이터 전처리
        processed_df = data_processor.preprocess_products(data['successful'])
        processed_df = data_processor.extract_style_keywords(processed_df)
        embedding_df = data_processor.create_product_embeddings_data(processed_df)
        
        # 벡터 DB 초기화
        vector_db = AdvancedVectorDB()
        vector_db.add_products(embedding_df)
        
        print(f"벡터 DB 초기화 완료: {len(embedding_df)}개 상품")
        
    except Exception as e:
        print(f"벡터 DB 초기화 실패: {e}")
        raise e

@app.get("/")
async def root():
    """루트 엔드포인트"""
    return {
        "message": "패션 추천 벡터 검색 API",
        "version": "1.0.0",
        "status": "running"
    }

@app.get("/health")
async def health_check():
    """헬스 체크"""
    if vector_db is None:
        raise HTTPException(status_code=503, detail="벡터 DB가 초기화되지 않았습니다.")
    
    stats = vector_db.get_statistics()
    return {
        "status": "healthy",
        "vector_db_stats": stats
    }

@app.post("/search", response_model=SearchResponse)
async def search_products(request: SearchRequest):
    """상품 검색 API"""
    if vector_db is None:
        raise HTTPException(status_code=503, detail="벡터 DB가 초기화되지 않았습니다.")
    
    try:
        import time
        start_time = time.time()
        
        # 필터 구성
        filters = {}
        if request.category:
            filters['category'] = request.category
        if request.min_rating:
            filters['min_rating'] = request.min_rating
        
        # 하이브리드 검색 수행
        results = vector_db.hybrid_search(
            query=request.query,
            top_k=request.top_k,
            filters=filters,
            use_hybrid=request.use_hybrid
        )
        
        # 결과 변환
        search_results = []
        for result in results:
            search_results.append({
                'product_id': result.product_id,
                'product_name': result.product_name,
                'similarity_score': result.similarity_score,
                'rating_score': result.rating_score,
                'review_score': result.review_score,
                'final_score': result.final_score,
                'rating': result.metadata.get('rating', 0),
                'review_count': result.metadata.get('review_count', 0),
                'category': result.metadata.get('category', ''),
                'style_keywords': result.metadata.get('style_keywords', []),
                'url': result.metadata.get('url', ''),
                'image_url': result.metadata.get('image_url', '')
            })
        
        search_time = time.time() - start_time
        
        return SearchResponse(
            query=request.query,
            results=search_results,
            total_results=len(search_results),
            search_time=search_time,
            performance_stats=vector_db.get_performance_stats()
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"검색 중 오류 발생: {str(e)}")

@app.post("/trending")
async def get_trending_products(request: TrendingRequest):
    """트렌딩 상품 조회 API"""
    if vector_db is None:
        raise HTTPException(status_code=503, detail="벡터 DB가 초기화되지 않았습니다.")
    
    try:
        results = vector_db.search_trending_products(
            top_k=request.top_k,
            category=request.category
        )
        
        trending_results = []
        for result in results:
            trending_results.append({
                'product_id': result.product_id,
                'product_name': result.product_name,
                'trending_score': result.final_score,
                'rating': result.metadata.get('rating', 0),
                'review_count': result.metadata.get('review_count', 0),
                'category': result.metadata.get('category', ''),
                'url': result.metadata.get('url', ''),
                'image_url': result.metadata.get('image_url', '')
            })
        
        return {
            'trending_products': trending_results,
            'total_results': len(trending_results)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"트렌딩 상품 조회 중 오류 발생: {str(e)}")

@app.post("/recommendations")
async def get_search_recommendations(request: RecommendationRequest):
    """검색어 추천 API"""
    if vector_db is None:
        raise HTTPException(status_code=503, detail="벡터 DB가 초기화되지 않았습니다.")
    
    try:
        recommendations = vector_db.get_search_recommendations(
            user_query=request.user_query,
            top_k=request.top_k
        )
        
        return {
            'user_query': request.user_query,
            'recommendations': recommendations
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"검색어 추천 중 오류 발생: {str(e)}")

@app.get("/categories")
async def get_categories():
    """카테고리 목록 조회"""
    if vector_db is None:
        raise HTTPException(status_code=503, detail="벡터 DB가 초기화되지 않았습니다.")
    
    try:
        categories = set()
        for metadata in vector_db.metadata:
            category = metadata.get('category', '')
            if category:
                categories.add(category)
        
        return {
            'categories': sorted(list(categories)),
            'total_categories': len(categories)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"카테고리 조회 중 오류 발생: {str(e)}")

@app.get("/stats")
async def get_statistics():
    """통계 정보 조회"""
    if vector_db is None:
        raise HTTPException(status_code=503, detail="벡터 DB가 초기화되지 않았습니다.")
    
    try:
        stats = vector_db.get_performance_stats()
        return stats
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"통계 조회 중 오류 발생: {str(e)}")

if __name__ == "__main__":
    uvicorn.run(
        "vector_search_api:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
        log_level="info"
    ) 