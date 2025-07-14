# LLM 기반 패션 추천 시스템

## 프로젝트 개요

기존 이커머스 추천 시스템의 한계를 극복하기 위한 LLM 기반 대화형 패션 추천 시스템입니다.

### 주요 특징
- **자연어 기반 대화형 추천**: 감성적 표현("미니멀", "힙한") 이해
- **후기 기반 신뢰 추천**: 실제 사용자 후기 중심 추천
- **실시간 피드백 반영**: 사용자 요청에 따른 재추천
- **트렌드 반영**: 최신 패션 트렌드 키워드 반영
- **LangGraph 워크플로우**: 멀티 에이전트 협업 시스템
- **조건부 분기 처리**: 복잡한 의사결정 로직 시각화
- **상태 기반 워크플로우**: FashionState를 통한 데이터 흐름 관리

## 프로젝트 구조

```
LLM/
├── data/                          # 데이터 파일들
│   ├── merged_successful_data.csv # 성공 데이터
│   ├── merged_failed_data.json    # 실패 데이터
│   └── musinsa_products_all_categories.csv # 무신사 상품 데이터
├── src/                           # 소스 코드
│   ├── agents/                    # LLM 에이전트
│   │   ├── conversation_agent.py  # 일상 대화 에이전트
│   │   └── recommendation_agent.py # 추천 에이전트
│   ├── models/                    # 모델 관련
│   │   ├── embedding_model.py     # 임베딩 모델
│   │   └── sentiment_analyzer.py  # 감성 분석
│   ├── utils/                     # 유틸리티
│   │   ├── data_processor.py      # 데이터 처리
│   │   └── query_refiner.py       # 쿼리 정제
│   ├── api/                       # API 서버
│   │   └── fastapi_server.py      # FastAPI 서버
│   ├── main_recommendation_system.py # 메인 추천 시스템
│   └── langgraph_fashion_system.py # LangGraph 워크플로우
├── notebooks/                     # Jupyter 노트북
│   └── LLM_Agent.ipynb           # 기존 노트북
├── requirements.txt               # 의존성 패키지
└── README.md                     # 프로젝트 설명
```

## 기술 스택

- **LLM**: GPT-4, ChatGPT API
- **임베딩**: SentenceTransformers, CLIP, KoCLIP
- **벡터 DB**: FAISS (Facebook AI Similarity Search)
- **감성 분석**: KoBERT, KcELECTRA
- **검색**: 하이브리드 검색 (벡터 유사도 + 평점/리뷰 스코어링)
- **백엔드**: FastAPI
- **프론트엔드**: HTML5, CSS3, JavaScript
- **데이터 처리**: Pandas, KoNLPy
- **워크플로우**: LangGraph, LangChain
- **상태 관리**: Pydantic, Dataclasses
- **에러 처리**: Try-Catch 기반 노드별 독립 처리

## 설치 및 실행

1. 의존성 설치:
```bash
pip install -r requirements.txt
```

2. 환경 변수 설정:
```bash
export OPENAI_API_KEY="your_api_key"
```

3. 서버 실행:
```bash
python src/api/fastapi_server.py
```

4. 벡터 DB 테스트:
```bash
python test_vector_db.py
```

5. 고급 벡터 DB 테스트:
```bash
python src/advanced_vector_db.py
```

6. API 서버 실행:
```bash
python src/api/vector_search_api.py
```

7. 웹 인터페이스 접속:
```bash
# 브라우저에서 http://localhost:8001/docs 접속
# 또는 web_interface/index.html 파일을 브라우저에서 열기
```

8. 시스템 비교 테스트:
```bash
# 순차 처리 vs LangGraph 워크플로우 성능 비교
python test_langgraph_system.py
```

## 사용 예시

### 기본 사용법
```python
# 대화형 추천 예시
user_input = "스트릿한 무드의 스트라이프 티 추천해줘?"
response = recommendation_system.recommend(user_input)
# 응답: "이 반팔은 꾸안꾸 무드에 딱이고, 요즘 무신사 랭킹에도 올라와 있어요!"
```

### LangGraph 워크플로우 사용법
```python
# LangGraph 기반 시스템 초기화
system = LLMFashionRecommendationSystem(use_langgraph=True)

# 사용자 입력 처리 (워크플로우 자동 실행)
response = system.process_user_input("꾸안꾸 느낌 나는 반팔 추천해줘")

# 시스템 전환
system.switch_to_langgraph()  # LangGraph로 전환
system.switch_to_sequential() # 순차 처리로 전환

# 워크플로우 요약 정보 조회
summary = system.get_workflow_summary()
print(f"총 대화 턴: {summary['conversation_summary']['total_turns']}")
print(f"총 추천 수: {summary['recommendation_summary']['total_recommendations']}")
```

### 상태 관리 (FashionState)
```python
@dataclass
class FashionState:
    user_input: str                    # 사용자 입력
    conversation_result: Dict          # 대화 에이전트 결과
    recommendations: List              # 추천 상품 목록
    user_feedback: Dict                # 사용자 피드백
    final_response: str                # 최종 응답
    error: str                         # 에러 정보
```

### 성능 비교 (실제 테스트 결과)

#### 순차 처리 vs LangGraph 워크플로우
| 항목 | 순차 처리 시스템 | LangGraph 시스템 |
|------|------------------|------------------|
| **응답 품질** | 기본적인 추천 응답 | 풍부한 이모티콘과 상세 설명 |
| **추천 정확도** | 기본 필터링 | 실제 상품 데이터 기반 정확한 추천 |
| **피드백 처리** | 단순 분기 | 복잡한 피드백 분석 및 재추천 |
| **에러 처리** | 전체 시스템 중단 | 노드별 독립적 에러 처리 |
| **확장성** | 코드 수정 필요 | 새로운 노드 추가 용이 |
| **디버깅** | 로그 분석 어려움 | 워크플로우 시각화로 쉬운 디버깅 |

#### 실제 테스트 결과
```
입력: "꾸안꾸 느낌 나는 반팔 추천해줘"

순차 처리 결과:
- 응답: 기본적인 추천 메시지
- 추천 상품: 0개 (데이터 로드 실패)

LangGraph 결과:
- 응답: "안녕하세요! 😊 꾸안꾸 느낌이 나는 반팔을 추천해드릴게요! 🌟"
- 추천 상품: 3개 (실제 무신사 상품)
- 상세한 추천 이유 및 링크 제공
```

### 벡터 DB 구조

#### 하이브리드 검색 시스템
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ 사용자 쿼리     │───▶│ 임베딩 생성     │───▶│ FAISS 벡터 검색 │
│                 │    │ (해시 기반)     │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │                        │
                                ▼                        ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ 메타데이터      │◀───│ 필터링 적용     │◀───│ 검색 결과       │
│ 필터링          │    │ (카테고리/평점) │    │ (상위 K개)      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │
                                ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ 하이브리드      │───▶│ 최종 스코어링   │───▶│ 정렬된 결과     │
│ 스코어링        │    │ (유사도+평점+   │    │ 반환            │
│                 │    │  리뷰수)        │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

#### 스코어링 공식
```
최종 스코어 = (유사도 × 0.5) + (평점 스코어 × 0.3) + (리뷰 스코어 × 0.2)

- 유사도: FAISS 벡터 유사도 점수 (0-1)
- 평점 스코어: 평점 / 5.0 (0-1 정규화)
- 리뷰 스코어: log(리뷰수 + 1) / 10.0 (로그 스케일 정규화)
```

### 워크플로우 구조

#### LangGraph 노드 구성
```
┌─────────────────┐    ┌─────────────────────┐    ┌─────────────────┐
│ conversation_   │───▶│ recommendation_     │───▶│ response_       │
│ agent           │    │ agent               │    │ generator       │
│                 │    │                     │    │                 │
│ • 의도 탐지     │    │ • 상품 필터링       │    │ • 최종 응답 생성 │
│ • 대화 관리     │    │ • 스코어링          │    │ • 추천 결과 정리 │
│ • 컨텍스트 저장 │    │ • 추천 이유 생성    │    │ • 에러 처리      │
└─────────────────┘    └─────────────────────┘    └─────────────────┘
         │                        ▲                        │
         │                        │                        │
         ▼                        │                        │
┌─────────────────┐              │                        │
│ feedback_       │──────────────┘                        │
│ processor       │                                       │
│                 │                                       │
│ • 피드백 분석   │                                       │
│ • 필터 조정     │                                       │
│ • 재추천 트리거 │                                       │
└─────────────────┘                                       │
                                                          ▼
                                                   ┌─────────────┐
                                                   │     END     │
                                                   └─────────────┘
```

#### 조건부 분기 로직
1. **conversation_agent → recommendation_agent**
   - `requires_recommendation = True`인 경우
   - 의도가 "recommendation_request"인 경우

2. **conversation_agent → feedback_processor**
   - 의도가 "feedback"인 경우
   - 피드백 키워드 감지 시

3. **feedback_processor → recommendation_agent**
   - 피드백 타입이 "cheaper", "different_style"인 경우
   - 필터 조정 후 재추천

4. **모든 노드 → response_generator**
   - 최종 응답 생성 및 에러 처리

## 개발 로드맵

- [x] 프로젝트 구조 설계
- [x] 데이터 전처리 및 분석
- [x] LLM 에이전트 구현
- [x] 임베딩 모델 통합
- [x] 추천 알고리즘 개발
- [x] LangGraph 워크플로우 구현
- [x] 멀티 에이전트 협업 시스템
- [x] 조건부 분기 및 피드백 처리
- [x] 벡터 DB 구현 (FAISS)
- [x] 하이브리드 검색 시스템
- [x] API 서버 구축 (FastAPI)
- [x] 웹 인터페이스 구현
- [ ] 성능 평가 및 최적화
- [ ] 실시간 학습 및 개선
- [ ] A/B 테스트 자동화
- [ ] 모바일 앱 개발
- [ ] 실시간 채팅 기능