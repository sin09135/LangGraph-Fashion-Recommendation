"""
대화 관리 에이전트
사용자와의 자연스러운 대화를 관리하고 추천 의도를 탐지
"""

import os
import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime

try:
    import openai
except ImportError:
    print("OpenAI 라이브러리가 설치되지 않았습니다. pip install openai를 실행하세요.")
    openai = None


@dataclass
class ConversationTurn:
    """대화 턴 데이터 클래스"""
    timestamp: str
    user_input: str
    agent_response: str
    intent: str
    confidence: float
    context: Dict[str, Any]


class ConversationAgent:
    """대화 관리 에이전트"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        if self.api_key and openai:
            openai.api_key = self.api_key
        
        self.conversation_history: List[ConversationTurn] = []
        self.user_preferences: Dict[str, Any] = {}
        self.current_context: Dict[str, Any] = {}
        
        # 시스템 프롬프트
        self.system_prompt = """당신은 친근하고 도움이 되는 패션 추천 어시스턴트입니다.

주요 역할:
1. 사용자의 패션 관련 질문에 친근하게 답변
2. 추천 요청 의도를 정확히 파악
3. 사용자의 취향과 선호도를 자연스럽게 수집
4. 대화 맥락을 유지하며 일관된 추천 제공

대화 스타일:
- 친근하고 자연스러운 톤 사용
- 이모티콘 적절히 활용 (예: 😊, 👕, 💡)
- 사용자의 감정과 의도를 공감하며 반응
- 추천 이유를 명확하고 이해하기 쉽게 설명

추천 의도 탐지:
- "추천해줘", "보여줘", "찾아줘", "없어?" 등의 키워드 감지
- 스타일, 카테고리, 색상, 가격대 등 구체적 요구사항 파악
- 피드백("저렴한", "다른 스타일") 반영

사용자 취향 수집:
- 대화를 통해 선호하는 스타일, 브랜드, 가격대 파악
- 계절, 상황별 선호도 기록
- 이전 추천에 대한 반응을 통해 취향 업데이트"""
    
    def process_user_input(self, user_input: str) -> Dict[str, Any]:
        """사용자 입력 처리 및 응답 생성"""
        # 의도 탐지
        intent_info = self._detect_intent(user_input)
        
        # 컨텍스트 업데이트
        self._update_context(user_input, intent_info)
        
        # 응답 생성
        response = self._generate_response(user_input, intent_info)
        
        # 대화 기록 저장
        turn = ConversationTurn(
            timestamp=datetime.now().isoformat(),
            user_input=user_input,
            agent_response=response['text'],
            intent=intent_info['intent'],
            confidence=intent_info['confidence'],
            context=self.current_context.copy()
        )
        self.conversation_history.append(turn)
        
        return {
            'response': response['text'],
            'intent': intent_info['intent'],
            'confidence': intent_info['confidence'],
            'requires_recommendation': response['requires_recommendation'],
            'extracted_info': intent_info['extracted_info'],
            'context': self.current_context
        }
    
    def _detect_intent(self, user_input: str) -> Dict[str, Any]:
        """사용자 입력의 의도 탐지"""
        if not openai:
            return self._rule_based_intent_detection(user_input)
        
        try:
            prompt = f"""다음 사용자 입력의 의도를 분석해주세요:

사용자 입력: "{user_input}"

다음 JSON 형식으로 응답해주세요:
{{
    "intent": "recommendation_request|feedback|information_request|general_conversation",
    "confidence": 0.0-1.0,
    "requires_recommendation": true/false,
    "extracted_info": {{
        "category": "상의|하의|신발|아우터|패션소품",
        "style": "오버핏|슬림핏|베이직|스트릿|빈티지|꾸안꾸|트렌디",
        "color": "블랙|화이트|네이비|그레이|베이지|레드|블루",
        "price_range": "저렴|보통|고급",
        "feedback_type": "cheaper|different_style|better_quality|more_trendy"
    }}
}}"""

            response = openai.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "당신은 사용자 의도를 정확히 분석하는 AI입니다."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1
            )
            
            content = response.choices[0].message.content or "{}"
            result = json.loads(content)
            return result
            
        except Exception as e:
            print(f"OpenAI API 호출 실패: {e}")
            return self._rule_based_intent_detection(user_input)
    
    def _rule_based_intent_detection(self, user_input: str) -> Dict[str, Any]:
        """규칙 기반 의도 탐지 (OpenAI API 사용 불가 시)"""
        input_lower = user_input.lower()
        
        # 추천 요청 의도
        recommendation_keywords = ['추천', '보여줘', '찾아줘', '없어', '어떤', '뭐가']
        is_recommendation = any(keyword in input_lower for keyword in recommendation_keywords)
        
        # 피드백 의도
        feedback_keywords = ['저렴한', '다른', '더', '좀', '변화']
        is_feedback = any(keyword in input_lower for keyword in feedback_keywords)
        
        # 정보 요청 의도
        info_keywords = ['뭐야', '어떤', '무슨', '알려줘']
        is_info_request = any(keyword in input_lower for keyword in info_keywords)
        
        # 의도 결정
        if is_recommendation:
            intent = "recommendation_request"
            confidence = 0.8
            requires_recommendation = True
        elif is_feedback:
            intent = "feedback"
            confidence = 0.7
            requires_recommendation = True
        elif is_info_request:
            intent = "information_request"
            confidence = 0.6
            requires_recommendation = False
        else:
            intent = "general_conversation"
            confidence = 0.5
            requires_recommendation = False
        
        # 정보 추출
        extracted_info = self._extract_info_rule_based(input_lower)
        
        return {
            "intent": intent,
            "confidence": confidence,
            "requires_recommendation": requires_recommendation,
            "extracted_info": extracted_info
        }
    
    def _extract_info_rule_based(self, input_lower: str) -> Dict[str, str]:
        """규칙 기반 정보 추출"""
        info = {}
        
        # 카테고리 추출 (더 정확한 매칭)
        categories = {
            '상의': ['상의', '티셔츠', '셔츠', '니트', '후드', '맨투맨', '반팔', '긴팔', '블라우스', '탑'],
            '하의': ['하의', '바지', '청바지', '슬랙스', '트레이닝', '반바지', '팬츠'],
            '신발': ['신발', '운동화', '스니커즈', '로퍼', '옥스포드'],
            '아우터': ['아우터', '패딩', '코트', '자켓', '가디건'],
            '패션소품': ['패션소품', '가방', '모자', '양말', '액세서리']
        }
        
        # 카테고리 우선순위 매칭 (더 구체적인 키워드가 우선)
        matched_category = None
        for category, keywords in categories.items():
            for keyword in keywords:
                if keyword in input_lower:
                    matched_category = category
                    break
            if matched_category:
                break
        
        if matched_category:
            info['category'] = matched_category
        
        # 스타일 추출
        styles = {
            '오버핏': ['오버핏', '오버사이즈', '빅사이즈', '루즈'],
            '슬림핏': ['슬림핏', '슬림', '타이트', '꽉끼는'],
            '베이직': ['베이직', '베이식', '기본', '심플', '무지'],
            '스트릿': ['스트릿', '힙합', '힙한', '캐주얼'],
            '빈티지': ['빈티지', '레트로', '올드'],
            '꾸안꾸': ['꾸안꾸', '꾸민듯안꾸민듯', '자연스러운'],
            '트렌디': ['트렌디', '유행', '인기', '핫한']
        }
        
        for style, keywords in styles.items():
            if any(keyword in input_lower for keyword in keywords):
                info['style'] = style
                break
        
        # 색상 추출
        colors = {
            '블랙': ['블랙', '검정', '검은'],
            '화이트': ['화이트', '흰색', '흰'],
            '네이비': ['네이비', '남색', '진한파랑'],
            '그레이': ['그레이', '회색', '회'],
            '베이지': ['베이지', '크림', '아이보리'],
            '레드': ['레드', '빨간', '빨강'],
            '블루': ['블루', '파란', '파랑']
        }
        
        for color, keywords in colors.items():
            if any(keyword in input_lower for keyword in keywords):
                info['color'] = color
                break
        
        # 가격대 추출
        price_ranges = {
            '저렴': ['저렴', '싼', '가성비', '합리적'],
            '보통': ['보통', '적당한', '중간'],
            '고급': ['고급', '비싼', '프리미엄', '럭셔리']
        }
        
        for price_range, keywords in price_ranges.items():
            if any(keyword in input_lower for keyword in keywords):
                info['price_range'] = price_range
                break
        
        # 피드백 타입 추출
        feedback_types = {
            'cheaper': ['저렴한', '싼', '가격 낮은'],
            'different_style': ['다른 스타일', '다른 느낌', '변화'],
            'better_quality': ['품질 좋은', '내구성', '오래가는'],
            'more_trendy': ['트렌디한', '유행', '인기', '핫한']
        }
        
        for feedback_type, keywords in feedback_types.items():
            if any(keyword in input_lower for keyword in keywords):
                info['feedback_type'] = feedback_type
                break
        
        return info
    
    def _update_context(self, user_input: str, intent_info: Dict[str, Any]):
        """대화 컨텍스트 업데이트"""
        # 사용자 선호도 업데이트
        extracted_info = intent_info.get('extracted_info', {})
        
        for key, value in extracted_info.items():
            if value:
                if key not in self.user_preferences:
                    self.user_preferences[key] = []
                if value not in self.user_preferences[key]:
                    self.user_preferences[key].append(value)
        
        # 현재 컨텍스트 업데이트
        self.current_context.update({
            'last_intent': intent_info['intent'],
            'last_extracted_info': extracted_info,
            'conversation_length': len(self.conversation_history) + 1,
            'user_preferences': self.user_preferences.copy()
        })
    
    def _generate_response(self, user_input: str, intent_info: Dict[str, Any]) -> Dict[str, str]:
        """사용자 입력에 대한 응답 생성"""
        if not openai:
            return self._rule_based_response_generation(user_input, intent_info)
        
        try:
            # 대화 히스토리 포함
            conversation_context = ""
            if self.conversation_history:
                recent_turns = self.conversation_history[-3:]  # 최근 3턴만 포함
                for turn in recent_turns:
                    conversation_context += f"사용자: {turn.user_input}\n어시스턴트: {turn.agent_response}\n"
            
            prompt = f"""{self.system_prompt}

대화 히스토리:
{conversation_context}

사용자 선호도: {self.user_preferences}

현재 사용자 입력: "{user_input}"

의도 분석 결과:
- 의도: {intent_info['intent']}
- 추천 필요: {intent_info['requires_recommendation']}
- 추출된 정보: {intent_info.get('extracted_info', {})}

자연스럽고 친근한 응답을 생성해주세요. 추천이 필요한 경우 "RECOMMENDATION_NEEDED"를 포함해주세요."""

            response = openai.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7
            )
            
            response_text = response.choices[0].message.content or ""
            
            return {
                'text': response_text,
                'requires_recommendation': 'RECOMMENDATION_NEEDED' in response_text,
            }
            
        except Exception as e:
            print(f"OpenAI API 호출 실패: {e}")
            return self._rule_based_response_generation(user_input, intent_info)
    
    def _rule_based_response_generation(self, user_input: str, intent_info: Dict[str, Any]) -> Dict[str, str]:
        """규칙 기반 응답 생성"""
        intent = intent_info['intent']
        extracted_info = intent_info.get('extracted_info', {})
        
        if intent == "recommendation_request":
            response = self._generate_recommendation_response(extracted_info)
        elif intent == "feedback":
            response = self._generate_feedback_response(extracted_info)
        elif intent == "information_request":
            response = self._generate_information_response(extracted_info)
        else:
            response = self._generate_general_response(user_input)
        
        return {
            'text': response,
            'requires_recommendation': intent in ["recommendation_request", "feedback"]
        }
    
    def _generate_recommendation_response(self, extracted_info: Dict[str, str]) -> str:
        """추천 요청에 대한 응답 생성"""
        category = extracted_info.get('category', '')
        style = extracted_info.get('style', '')
        color = extracted_info.get('color', '')
        
        if category and style:
            return f"😊 {category} 중에서 {style} 스타일을 찾아드릴게요! {color + ' 컬러로 ' if color else ''}어떤 느낌을 원하시나요?"
        elif category:
            return f"👕 {category} 추천해드릴게요! 어떤 스타일을 선호하시나요? (오버핏, 베이직, 스트릿 등)"
        elif style:
            return f"💡 {style} 스타일의 옷을 찾아드릴게요! 어떤 종류의 옷을 원하시나요?"
        else:
            return "😊 어떤 옷을 찾고 계신가요? 카테고리나 스타일을 알려주시면 추천해드릴게요!"
    
    def _generate_feedback_response(self, extracted_info: Dict[str, str]) -> str:
        """피드백에 대한 응답 생성"""
        feedback_type = extracted_info.get('feedback_type', '')
        
        if feedback_type == 'cheaper':
            return "💰 더 저렴한 옵션을 찾아드릴게요! 가성비 좋은 상품들을 추천해드릴게요."
        elif feedback_type == 'different_style':
            return "🔄 다른 스타일로 추천해드릴게요! 어떤 느낌을 원하시나요?"
        elif feedback_type == 'more_trendy':
            return "🔥 트렌디한 상품들을 찾아드릴게요! 요즘 인기 있는 스타일로 추천해드릴게요."
        else:
            return "💡 다른 옵션을 찾아드릴게요! 어떤 점을 바꿔보고 싶으신가요?"
    
    def _generate_information_response(self, extracted_info: Dict[str, str]) -> str:
        """정보 요청에 대한 응답 생성"""
        return "💡 어떤 정보를 알고 싶으신가요? 패션 트렌드나 스타일링 팁에 대해 궁금한 점이 있으시면 언제든 물어보세요!"
    
    def _generate_general_response(self, user_input: str) -> str:
        """일반 대화에 대한 응답 생성"""
        greetings = ["안녕하세요!", "반가워요!", "안녕하세요 😊"]
        import random
        return random.choice(greetings) + " 패션에 대해 궁금한 점이 있으시면 언제든 말씀해주세요!"
    
    def get_conversation_summary(self) -> Dict[str, Any]:
        """대화 요약 정보 반환"""
        return {
            'total_turns': len(self.conversation_history),
            'user_preferences': self.user_preferences,
            'current_context': self.current_context,
            'recent_intents': [turn.intent for turn in self.conversation_history[-5:]]
        }
    
    def reset_conversation(self):
        """대화 초기화"""
        self.conversation_history.clear()
        self.current_context.clear()
        # 사용자 선호도는 유지


def main():
    """대화 에이전트 테스트"""
    agent = ConversationAgent()
    
    test_inputs = [
        "안녕하세요!",
        "꾸안꾸 느낌 나는 반팔 없어?",
        "좀 더 저렴한 걸로 보여줘",
        "스트릿한 무드의 티셔츠 추천해줘",
        "감사합니다!"
    ]
    
    for user_input in test_inputs:
        print(f"\n사용자: {user_input}")
        result = agent.process_user_input(user_input)
        print(f"에이전트: {result['response']}")
        print(f"의도: {result['intent']} (신뢰도: {result['confidence']:.2f})")
        print(f"추천 필요: {result['requires_recommendation']}")


if __name__ == "__main__":
    main() 