"""
쿼리 정제 및 슬롯 추출 유틸리티
사용자의 자연어 쿼리를 구조화된 필터링 조건으로 변환
"""

import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class QuerySlots:
    """쿼리 슬롯 데이터 클래스"""
    category: Optional[str] = None
    style: Optional[str] = None
    price_range: Optional[str] = None
    color: Optional[str] = None
    brand: Optional[str] = None
    season: Optional[str] = None
    occasion: Optional[str] = None
    feedback_type: Optional[str] = None  # 'cheaper', 'different_style', etc.


class QueryRefiner:
    """쿼리 정제 및 슬롯 추출 클래스"""
    
    def __init__(self):
        # 카테고리 매핑
        self.category_patterns = {
            '상의': ['티','상의', '티셔츠', '셔츠', '니트', '후드', '맨투맨', '반팔', '긴팔'],
            '하의': ['하의', '바지', '청바지', '슬랙스', '트레이닝', '반바지'],
            '신발': ['신발', '운동화', '스니커즈', '로퍼', '옥스포드'],
            '아우터': ['아우터', '패딩', '코트', '자켓', '가디건'],
            '패션소품': ['패션소품', '가방', '모자', '양말', '액세서리']
        }
        
        # 스타일 매핑
        self.style_patterns = {
            '오버핏': ['오버핏', '오버사이즈', '빅사이즈', '루즈'],
            '슬림핏': ['슬림핏', '슬림', '타이트', '꽉끼는'],
            '머슬핏': ['머슬핏', '머슬', '헬스'],
            '베이직': ['베이직', '베이식', '기본', '심플', '무지'],
            '스트릿': ['스트릿', '힙합', '힙한', '캐주얼'],
            '빈티지': ['빈티지', '레트로', '올드'],
            '스포티': ['스포티', '스포츠', '운동복', '트레이닝'],
            '꾸안꾸': ['꾸안꾸', '꾸민듯안꾸민듯', '자연스러운'],
            '트렌디': ['트렌디', '유행', '인기', '핫한'],
            '미니멀': ['미니멀', '미니멀리즘', '미니멀한']
        }
        
        # 가격대 매핑
        self.price_patterns = {
            '저렴': ['저렴', '싼', '가성비', '합리적'],
            '보통': ['보통', '적당한', '중간'],
            '고급': ['고급', '비싼', '프리미엄', '럭셔리']
        }
        
        # 색상 매핑
        self.color_patterns = {
            '블랙': ['블랙', '검정', '검은'],
            '화이트': ['화이트', '흰색', '흰'],
            '네이비': ['네이비', '남색', '진한파랑'],
            '그레이': ['그레이', '회색', '회'],
            '베이지': ['베이지', '크림', '아이보리'],
            '레드': ['레드', '빨간', '빨강'],
            '블루': ['블루', '파란', '파랑']
        }
        
        # 계절 매핑
        self.season_patterns = {
            '봄': ['봄', '봄철', '봄날'],
            '여름': ['여름', '여름철', '여름날', '썸머'],
            '가을': ['가을', '가을철', '가을날', '오토'],
            '겨울': ['겨울', '겨울철', '겨울날', '윈터']
        }
        
        # 피드백 타입 매핑
        self.feedback_patterns = {
            'cheaper': ['저렴한', '싼', '가격 낮은', '비용 절약'],
            'different_style': ['다른 스타일', '다른 느낌', '변화', '새로운'],
            'better_quality': ['품질 좋은', '내구성', '오래가는'],
            'more_trendy': ['트렌디한', '유행', '인기', '핫한']
        }
    
    def extract_slots(self, query: str) -> QuerySlots:
        """쿼리에서 슬롯 추출"""
        query_lower = query.lower()
        slots = QuerySlots()
        
        # 카테고리 추출
        slots.category = self._extract_category(query_lower)
        
        # 스타일 추출
        slots.style = self._extract_style(query_lower)
        
        # 가격대 추출
        slots.price_range = self._extract_price_range(query_lower)
        
        # 색상 추출
        slots.color = self._extract_color(query_lower)
        
        # 계절 추출
        slots.season = self._extract_season(query_lower)
        
        # 피드백 타입 추출
        slots.feedback_type = self._extract_feedback_type(query_lower)
        
        return slots
    
    def _extract_category(self, query: str) -> Optional[str]:
        """카테고리 추출"""
        for category, patterns in self.category_patterns.items():
            if any(pattern in query for pattern in patterns):
                return category
        return None
    
    def _extract_style(self, query: str) -> Optional[str]:
        """스타일 추출"""
        for style, patterns in self.style_patterns.items():
            if any(pattern in query for pattern in patterns):
                return style
        return None
    
    def _extract_price_range(self, query: str) -> Optional[str]:
        """가격대 추출"""
        for price_range, patterns in self.price_patterns.items():
            if any(pattern in query for pattern in patterns):
                return price_range
        return None
    
    def _extract_color(self, query: str) -> Optional[str]:
        """색상 추출"""
        for color, patterns in self.color_patterns.items():
            if any(pattern in query for pattern in patterns):
                return color
        return None
    
    def _extract_season(self, query: str) -> Optional[str]:
        """계절 추출"""
        for season, patterns in self.season_patterns.items():
            if any(pattern in query for pattern in patterns):
                return season
        return None
    
    def _extract_feedback_type(self, query: str) -> Optional[str]:
        """피드백 타입 추출"""
        for feedback_type, patterns in self.feedback_patterns.items():
            if any(pattern in query for pattern in patterns):
                return feedback_type
        return None
    
    def _extract_size_filters(self, query: str) -> dict:
        """사이즈 조건(총장, 가슴단면, 어깨너비 등) 추출"""
        size_filters = {}
        import re
        # 총장
        m = re.search(r'총장[ ]*([0-9]+\.?[0-9]*)[ ]*cm?[ ]*(이하|이상|보다 작|보다 크)?', query)
        if m:
            value = float(m.group(1))
            op = m.group(2) or ''
            if '이하' in op or '작' in op:
                size_filters['length'] = ('<=', value)
            elif '이상' in op or '크' in op:
                size_filters['length'] = ('>=', value)
        # 가슴단면
        m = re.search(r'가슴단면[ ]*([0-9]+\.?[0-9]*)[ ]*cm?[ ]*(이하|이상|보다 작|보다 크)?', query)
        if m:
            value = float(m.group(1))
            op = m.group(2) or ''
            if '이하' in op or '작' in op:
                size_filters['chest'] = ('<=', value)
            elif '이상' in op or '크' in op:
                size_filters['chest'] = ('>=', value)
        # 어깨너비
        m = re.search(r'어깨너비[ ]*([0-9]+\.?[0-9]*)[ ]*cm?[ ]*(이하|이상|보다 작|보다 크)?', query)
        if m:
            value = float(m.group(1))
            op = m.group(2) or ''
            if '이하' in op or '작' in op:
                size_filters['shoulder'] = ('<=', value)
            elif '이상' in op or '크' in op:
                size_filters['shoulder'] = ('>=', value)
        return size_filters
    
    def refine_query(self, query: str, context: Optional[Dict] = None) -> Dict:
        """쿼리 정제 및 구조화"""
        slots = self.extract_slots(query)
        filters = {}
        if slots.category:
            filters['category'] = slots.category
        if slots.style:
            filters['style'] = slots.style
        if slots.price_range:
            filters['price_range'] = slots.price_range
        if slots.color:
            filters['color'] = slots.color
        if slots.season:
            filters['season'] = slots.season
        # 사이즈 필터 추가
        size_filters = self._extract_size_filters(query)
        filters.update(size_filters)
        # 컨텍스트가 있는 경우 이전 추천 결과와 비교
        if context and 'previous_recommendations' in context:
            filters['exclude_ids'] = context['previous_recommendations']
        # 피드백이 있는 경우 필터 조정
        if slots.feedback_type:
            filters['feedback'] = slots.feedback_type
            if slots.feedback_type == 'cheaper':
                filters['price_range'] = '저렴'
            elif slots.feedback_type == 'different_style':
                if 'style' in filters:
                    del filters['style']
            elif slots.feedback_type == 'more_trendy':
                filters['style'] = '트렌디'
        return {
            'original_query': query,
            'slots': slots,
            'filters': filters,
            'intent': self._detect_intent(query)
        }
    
    def _detect_intent(self, query: str) -> str:
        """쿼리 의도 탐지"""
        query_lower = query.lower()
        
        # 추천 요청 의도
        if any(word in query_lower for word in ['추천', '보여줘', '찾아줘', '없어']):
            return 'recommendation_request'
        
        # 피드백 의도
        if any(word in query_lower for word in ['저렴한', '다른', '더', '좀']):
            return 'feedback'
        
        # 정보 요청 의도
        if any(word in query_lower for word in ['뭐야', '어떤', '무슨']):
            return 'information_request'
        
        # 일반 대화 의도
        return 'general_conversation'
    
    def generate_search_query(self, slots: QuerySlots) -> str:
        """슬롯을 기반으로 검색 쿼리 생성"""
        search_terms = []
        
        if slots.category:
            search_terms.append(slots.category)
            
        if slots.style:
            search_terms.append(slots.style)
            
        if slots.color:
            search_terms.append(slots.color)
            
        if slots.season:
            search_terms.append(slots.season)
        
        return ' '.join(search_terms) if search_terms else ''
    
    def validate_slots(self, slots: QuerySlots) -> Tuple[bool, List[str]]:
        """슬롯 유효성 검증"""
        errors = []
        
        # 필수 슬롯 검증 (카테고리 또는 스타일 중 하나는 있어야 함)
        if not slots.category and not slots.style:
            errors.append("카테고리나 스타일 정보가 필요합니다.")
        
        # 상호 배타적 슬롯 검증
        if slots.style == '오버핏' and slots.style == '슬림핏':
            errors.append("오버핏과 슬림핏은 동시에 적용할 수 없습니다.")
        
        return len(errors) == 0, errors


def main():
    """쿼리 정제 테스트"""
    refiner = QueryRefiner()
    
    test_queries = [
        "총장 65cm 이하의 미니멀한 상의 추천해줘",
        "좀 더 저렴한 걸로 보여줘",
        "스트릿한 무드의 티셔츠 추천해줘",
        "블랙 컬러의 오버핏 상의 찾아줘",
        "여름에 입기 좋은 베이직한 옷 없어?"
    ]
    
    for query in test_queries:
        print(f"\n원본 쿼리: {query}")
        result = refiner.refine_query(query)
        
        print(f"의도: {result['intent']}")
        print(f"슬롯: {result['slots']}")
        print(f"필터: {result['filters']}")
        print(f"검색 쿼리: {refiner.generate_search_query(result['slots'])}")


if __name__ == "__main__":
    main() 