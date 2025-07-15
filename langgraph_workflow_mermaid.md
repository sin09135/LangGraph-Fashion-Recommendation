# LangGraph 패션 추천 시스템 워크플로우

## 전체 워크플로우 다이어그램

```mermaid
flowchart TD
    %% 시작점
    START([사용자 입력]) --> CONV[대화 분석가<br/>conversation_agent]
    
    %% 대화 분석 결과에 따른 분기
    CONV --> CONV_DECISION{의도 분석}
    
    %% 추천 관련 의도
    CONV_DECISION -->|추천 요청| REC[추천 전문가<br/>recommendation_agent]
    CONV_DECISION -->|피드백| FB[피드백 처리자<br/>feedback_processor]
    CONV_DECISION -->|일반 대화| RESP[응답 작성자<br/>response_generator]
    
    %% 추천 결과에 따른 분기
    REC --> REC_DECISION{추천 결과}
    REC_DECISION -->|성공| EVAL[품질 검사관<br/>evaluator]
    REC_DECISION -->|결과 없음| RESP
    REC_DECISION -->|오류| RESP
    
    %% 평가 결과에 따른 분기
    EVAL --> EVAL_DECISION{품질 평가}
    EVAL_DECISION -->|품질 우수/보통<br/>점수 ≥ 0.6| RESP
    EVAL_DECISION -->|품질 개선필요<br/>점수 < 0.6| REC
    
    %% 피드백 처리 결과에 따른 분기
    FB --> FB_DECISION{피드백 유형}
    FB_DECISION -->|재추천 필요| REC
    FB_DECISION -->|선호도 업데이트| RESP
    FB_DECISION -->|오류| RESP
    
    %% 최종 응답
    RESP --> END([최종 응답])
    
    %% 스타일 정의
    classDef startEnd fill:#e1f5fe,stroke:#01579b,stroke-width:2px
    classDef agent fill:#f3e5f5,stroke:#4a148c,stroke-width:2px
    classDef decision fill:#fff3e0,stroke:#e65100,stroke-width:2px
    
    class START,END startEnd
    class CONV,REC,EVAL,FB,RESP agent
    class CONV_DECISION,REC_DECISION,EVAL_DECISION,FB_DECISION decision
```

## 상태 변화 다이어그램

```mermaid
flowchart LR
    %% 상태 변화 과정
    S1[초기 상태<br/>user_input만 있음] --> S2[대화 분석 후<br/>conversation_result 추가]
    S2 --> S3[추천 실행 후<br/>recommendations 추가]
    S3 --> S4[평가 실행 후<br/>evaluation_result 추가]
    S4 --> S5[최종 응답 생성<br/>final_response 추가]
    
    %% 재추천 루프
    S4 --> S6[품질 낮음<br/>재추천 필요] --> S3
    
    %% 스타일
    classDef state fill:#e8f5e8,stroke:#2e7d32,stroke-width:2px
    classDef loop fill:#fff8e1,stroke:#f57f17,stroke-width:2px
    
    class S1,S2,S3,S4,S5 state
    class S6 loop
```

## 데이터 흐름 다이어그램

```mermaid
flowchart TD
    %% 데이터 흐름
    USER[사용자 입력<br/>"스트릿 반팔 추천해줘"] --> CONV
    
    CONV --> CONV_DATA[대화 분석 결과<br/>intent: recommendation_request<br/>extracted_info: {style: "스트릿", category: "상의"}]
    
    CONV_DATA --> REC
    REC --> REC_DATA[추천 결과<br/>[{product_id: "1", name: "스트릿 그래픽 반팔"},<br/>{product_id: "2", name: "오버핏 로고 반팔"}]]
    
    REC_DATA --> EVAL
    EVAL --> EVAL_DATA[평가 결과<br/>overall_score: 0.75<br/>quality_level: "보통"<br/>relevance_score: 0.8]
    
    EVAL_DATA --> RESP
    RESP --> FINAL[최종 응답<br/>"스트릿한 반팔 추천해드릴게요!<br/>1. 스트릿 그래픽 반팔<br/>2. 오버핏 로고 반팔<br/>📊 품질 평가: 보통 (점수: 0.750)"]
    
    %% 재추천 루프
    EVAL_DATA --> LOOP[품질 개선필요<br/>재추천 루프] --> REC
    
    %% 스타일
    classDef input fill:#e3f2fd,stroke:#1565c0,stroke-width:2px
    classDef data fill:#f1f8e9,stroke:#33691e,stroke-width:2px
    classDef output fill:#fff3e0,stroke:#e65100,stroke-width:2px
    
    class USER input
    class CONV_DATA,REC_DATA,EVAL_DATA data
    class FINAL output
```

## 평가 메트릭 다이어그램

```mermaid
flowchart TD
    %% 평가 과정
    REC_RESULT[추천 결과] --> EVAL_PROCESS[평가 프로세스]
    
    EVAL_PROCESS --> RELEVANCE[관련성 평가<br/>사용자 쿼리와 상품 매칭도]
    EVAL_PROCESS --> DIVERSITY[다양성 평가<br/>카테고리/스타일/가격대 다양성]
    EVAL_PROCESS --> NOVELTY[신규성 평가<br/>사용자 히스토리 대비 새로운 상품]
    EVAL_PROCESS --> COVERAGE[커버리지 평가<br/>요청 조건 대비 실제 추천 개수]
    
    RELEVANCE --> SCORE_CALC[종합 점수 계산<br/>가중치: 관련성 40% + 다양성 25% + 신규성 20% + 커버리지 15%]
    DIVERSITY --> SCORE_CALC
    NOVELTY --> SCORE_CALC
    COVERAGE --> SCORE_CALC
    
    SCORE_CALC --> QUALITY_DECISION{품질 수준 판정}
    QUALITY_DECISION -->|≥ 0.8| EXCELLENT[우수]
    QUALITY_DECISION -->|≥ 0.6| GOOD[보통]
    QUALITY_DECISION -->|< 0.6| IMPROVE[개선필요]
    
    EXCELLENT --> RESPONSE[최종 응답]
    GOOD --> RESPONSE
    IMPROVE --> RERECOMMEND[재추천]
    
    %% 스타일
    classDef process fill:#e8eaf6,stroke:#3f51b5,stroke-width:2px
    classDef metric fill:#fce4ec,stroke:#c2185b,stroke-width:2px
    classDef decision fill:#fff8e1,stroke:#f57f17,stroke-width:2px
    classDef result fill:#e0f2f1,stroke:#00695c,stroke-width:2px
    
    class EVAL_PROCESS,SCORE_CALC process
    class RELEVANCE,DIVERSITY,NOVELTY,COVERAGE metric
    class QUALITY_DECISION decision
    class EXCELLENT,GOOD,IMPROVE result
```

## 노드별 상세 기능

### 대화 분석가 (conversation_agent)
- **입력**: 사용자 원본 메시지
- **처리**: 의도 분석, 정보 추출, 컨텍스트 파악
- **출력**: 추천 필요 여부, 추출된 정보, 사용자 선호도

### 추천 전문가 (recommendation_agent)
- **입력**: 대화 분석 결과, 필터 조건, 사용자 선호도
- **처리**: SQL/Vector DB 기반 추천, 하이브리드 결합
- **출력**: 추천 상품 목록, 신뢰도 점수, 추천 이유

### 품질 검사관 (evaluator)
- **입력**: 추천 결과, 사용자 컨텍스트
- **처리**: 4가지 메트릭 평가, 종합 점수 계산
- **출력**: 품질 수준, 개선 제안사항

### 피드백 처리자 (feedback_processor)
- **입력**: 사용자 피드백, 현재 컨텍스트
- **처리**: 피드백 분석, 필터 조건 업데이트
- **출력**: 업데이트된 선호도, 재추천 필요 여부

### 응답 작성자 (response_generator)
- **입력**: 모든 상태 정보
- **처리**: 최종 응답 텍스트 생성
- **출력**: 사용자에게 보여줄 최종 메시지 