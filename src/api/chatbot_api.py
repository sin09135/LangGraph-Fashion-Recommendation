"""
패션 추천 챗봇 API
FastAPI 기반 대화형 추천 시스템
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import uvicorn
import sys
import os
import json
import pandas as pd
from datetime import datetime
import uuid

# 프로젝트 루트 경로 추가
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

# FastAPI 앱 생성
app = FastAPI(
    title="패션 추천 챗봇 API",
    description="LLM 기반 대화형 패션 추천 시스템",
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
recommendation_system = None
sessions = {}  # 세션 관리

# 이미지 서빙 제외

# Pydantic 모델
class ChatMessage(BaseModel):
    message: str
    session_id: Optional[str] = None

class ChatResponse(BaseModel):
    response: str
    recommendations: Optional[List[Dict[str, Any]]] = []
    session_id: str
    intent: Optional[str] = None
    confidence: Optional[float] = None

class SessionInfo(BaseModel):
    session_id: str
    created_at: str
    message_count: int
    user_preferences: Dict[str, Any]

class ChatHistoryRequest(BaseModel):
    session_id: str

@app.on_event("startup")
async def startup_event():
    """서버 시작 시 추천 시스템 초기화"""
    global recommendation_system
    
    try:
        print("패션 추천 시스템 초기화 중...")
        
        # 메인 추천 시스템 임포트 및 초기화
        from main_recommendation_system import LLMFashionRecommendationSystem
        
        recommendation_system = LLMFashionRecommendationSystem(
            data_dir="/Users/kimsinwoo/Desktop/LLM/data",
            use_langgraph=True  # LangGraph 모드 사용
        )
        
        print("패션 추천 시스템 초기화 완료")
        
    except Exception as e:
        print(f"시스템 초기화 실패: {e}")
        raise e

@app.get("/")
async def root():
    """루트 엔드포인트"""
    return {
        "message": "패션 추천 챗봇 API",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "chat": "/chat - 대화형 추천",
            "session": "/session/{session_id} - 세션 정보",
            "history": "/history/{session_id} - 대화 히스토리",
            "reset": "/reset/{session_id} - 세션 리셋"
        }
    }

@app.get("/health")
async def health_check():
    """헬스 체크"""
    if recommendation_system is None:
        raise HTTPException(status_code=503, detail="추천 시스템이 초기화되지 않았습니다.")
    
    return {
        "status": "healthy",
        "system_ready": True,
        "timestamp": datetime.now().isoformat()
    }

@app.post("/chat", response_model=ChatResponse)
async def chat_with_bot(request: ChatMessage):
    """대화형 추천 API"""
    if recommendation_system is None:
        raise HTTPException(status_code=503, detail="추천 시스템이 초기화되지 않았습니다.")
    
    try:
        # 세션 ID 생성 또는 기존 세션 사용
        session_id = request.session_id or str(uuid.uuid4())
        
        # 세션 초기화 (없는 경우)
        if session_id not in sessions:
            sessions[session_id] = {
                'created_at': datetime.now().isoformat(),
                'messages': [],
                'user_preferences': {},
                'recommendation_history': []
            }
        
        # 사용자 메시지 저장
        sessions[session_id]['messages'].append({
            'role': 'user',
            'content': request.message,
            'timestamp': datetime.now().isoformat()
        })
        
        # 추천 시스템에 메시지 전달
        result = recommendation_system.process_user_input(request.message)
        
        # 응답 생성
        response_text = result.get('text', '죄송합니다. 응답을 생성할 수 없습니다.')
        recommendations = result.get('recommendations', [])
        
        # 추천 결과를 세션에 저장
        if recommendations:
            sessions[session_id]['recommendation_history'].extend([
                {
                    'product_id': rec.get('product_id'),
                    'product_name': rec.get('product_name'),
                    'timestamp': datetime.now().isoformat()
                }
                for rec in recommendations
            ])
        
        # 봇 응답 저장
        sessions[session_id]['messages'].append({
            'role': 'assistant',
            'content': response_text,
            'recommendations': recommendations,
            'timestamp': datetime.now().isoformat()
        })
        
        # 사용자 선호도 업데이트 (대화 컨텍스트에서)
        conversation_summary = recommendation_system.get_conversation_summary()
        if conversation_summary:
            sessions[session_id]['user_preferences'].update(
                conversation_summary.get('user_preferences', {})
            )
        
        return ChatResponse(
            response=response_text,
            recommendations=recommendations,
            session_id=session_id,
            intent=result.get('intent'),
            confidence=result.get('confidence', 0.0)
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"챗봇 처리 중 오류 발생: {str(e)}")

@app.get("/session/{session_id}", response_model=SessionInfo)
async def get_session_info(session_id: str):
    """세션 정보 조회"""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")
    
    session = sessions[session_id]
    return SessionInfo(
        session_id=session_id,
        created_at=session['created_at'],
        message_count=len(session['messages']),
        user_preferences=session['user_preferences']
    )

@app.get("/history/{session_id}")
async def get_chat_history(session_id: str):
    """대화 히스토리 조회"""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")
    
    return {
        "session_id": session_id,
        "messages": sessions[session_id]['messages'],
        "recommendation_history": sessions[session_id]['recommendation_history']
    }

@app.post("/reset/{session_id}")
async def reset_session(session_id: str):
    """세션 리셋"""
    if session_id in sessions:
        del sessions[session_id]
    
    # 추천 시스템의 대화 상태도 리셋
    if recommendation_system:
        recommendation_system.reset_conversation()
    
    return {"message": "세션이 리셋되었습니다.", "session_id": session_id}

@app.get("/sessions")
async def list_sessions():
    """활성 세션 목록 조회"""
    return {
        "active_sessions": len(sessions),
        "sessions": [
            {
                "session_id": session_id,
                "created_at": session['created_at'],
                "message_count": len(session['messages']),
                "last_activity": session['messages'][-1]['timestamp'] if session['messages'] else session['created_at']
            }
            for session_id, session in sessions.items()
        ]
    }

@app.get("/stats")
async def get_system_stats():
    """시스템 통계 조회"""
    if recommendation_system is None:
        raise HTTPException(status_code=503, detail="시스템이 초기화되지 않았습니다.")
    
    # 추천 시스템 통계
    recommendation_summary = recommendation_system.get_recommendation_summary()
    
    return {
        "system_stats": {
            "active_sessions": len(sessions),
            "total_recommendations": recommendation_summary.get('total_recommendations', 0),
            "recent_recommendations": recommendation_summary.get('recent_recommendations', 0),
            "most_recommended_products": recommendation_summary.get('most_recommended_products', [])
        },
        "timestamp": datetime.now().isoformat()
    }

@app.post("/feedback")
async def submit_feedback(session_id: str, product_id: str, feedback_type: str, feedback_value: float):
    """사용자 피드백 제출"""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")
    
    # 피드백 저장
    if 'feedback' not in sessions[session_id]:
        sessions[session_id]['feedback'] = []
    
    sessions[session_id]['feedback'].append({
        'product_id': product_id,
        'feedback_type': feedback_type,
        'feedback_value': feedback_value,
        'timestamp': datetime.now().isoformat()
    })
    
    # 추천 시스템에 피드백 전달
    if recommendation_system:
        recommendation_system.recommendation_agent.update_user_feedback(
            product_id, feedback_type, feedback_value
        )
    
    return {"message": "피드백이 저장되었습니다."}

if __name__ == "__main__":
    uvicorn.run(
        "chatbot_api:app",
        host="0.0.0.0",
        port=8002,
        reload=True,
        log_level="info"
    ) 