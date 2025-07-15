flowchart TD
    %% 사용자 입력
    A["🟡 사용자 발화"] --> B["🔍 의도 분석 (Intent Detection)"]

    %% Intent 분기
    B -->|추천 관련 의도| C1["🔵 추천 에이전트 전환"]
    B -->|일상대화| C2["🟢 일상대화 에이전트"]

    %% 일상대화 → 유도 분기
    C2 --> D2["맥락 기반 추천 유도 판단"]
    D2 -->|유도 타이밍| E2["유도 질문 발화: '추천해드릴까요?'"]
    E2 --> F2["사용자 응답"]
    F2 -->|긍정| C1
    F2 -->|부정| C2

    %% 추천 에이전트 시작
    C1 --> G["🎯 추천 Intent/슬롯 추출"]

    %% 추천 방식 분기
    G -->|조건 명확| H1["🟨 SQL 기반 추천"]
    G -->|유사 의미 요청| H2["🟦 Vector DB 기반 추천"]

    %% 추천 결과 제공
    H1 --> I["🔽 추천 결과 제시"]
    H2 --> I

    %% Evaluator 추가
    I --> E["📊 추천 품질 평가 (Evaluator)"]

    %% Evaluator 분기
    E -->|품질 우수| J["🗣 사용자 피드백 감지"]
    E -->|품질 개선 필요| E1["🔄 추천 재조정"]
    E1 --> G

    %% 사용자 피드백 감지
    J --> K["🗣 사용자 피드백 감지"]

    %% 피드백 유형에 따른 분기
    K -->|긍정 평가| K1["✅ 추천 종료 or 관련 추천 강화"]
    K -->|조건 변경 요청| K2["🛠 슬롯 변경 후 재추천 → G"]
    K -->|부정 평가| K3["🚫 재추천: 제외 / 쿼리 조정 → G"]
    K -->|더 보고 싶음| K4["🔁 다양성 확대 재추천 → G"]
    K -->|행동 기반(클릭, 구매)| K5["📦 피드백 로그 기록 + 개인화 강화"]

    %% 종료 조건
    K1 --> L["🏁 대화 종료 or 구매 유도"]
    K2 --> I
    K3 --> I
    K4 --> I
    K5 --> I

## 🚀 LangGraph 바로 시각화 방법

### 1. **Jupyter Notebook에서 바로 사용**
```python
from langgraph_direct_visualization import show_langgraph_directly
show_langgraph_directly()
```

### 2. **메인 시스템에서 바로 사용**
```python
# 메인 시스템 초기화 후
system = LangGraphFashionSystem(products_df)

# 바로 이미지로 표시
system.display_workflow_simple()
```

### 3. **커스텀 워크플로우에서 바로 사용**
```python
# 워크플로우 생성 후
compiled_workflow = workflow.compile()

# 바로 이미지로 표시
from IPython.display import Image, display
png_image = compiled_workflow.get_graph().draw_mermaid_png()
display(Image(png_image))
```

## ✅ 핵심 포인트

- **`draw_mermaid_png()`**: LangGraph의 내장 함수로 바로 PNG 이미지 생성
- **`display(Image(png_image))`**: IPython에서 바로 이미지 표시
- **한 줄로 실행**: 복잡한 설정 없이 바로 시각화

이제 Jupyter Notebook에서 `show_langgraph_directly()`를 호출하면 LangGraph 워크플로우가 바로 이미지로 표시됩니다! 🎯
