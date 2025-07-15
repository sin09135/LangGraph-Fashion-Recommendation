"""
추천 품질 평가기 (Recommendation Evaluator)
추천 결과의 품질을 다양한 메트릭으로 평가하고 개선 방향을 제시합니다.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
import json
import os
from datetime import datetime, timedelta

try:
    import openai
except ImportError:
    print("OpenAI 라이브러리가 설치되지 않았습니다.")
    openai = None


@dataclass
class EvaluationMetrics:
    """평가 메트릭 데이터 클래스"""
    relevance_score: float  # 관련성 점수 (0-1)
    diversity_score: float  # 다양성 점수 (0-1)
    novelty_score: float    # 신규성 점수 (0-1)
    coverage_score: float   # 커버리지 점수 (0-1)
    overall_score: float    # 종합 점수 (0-1)
    quality_level: str      # 품질 수준 (우수/보통/개선필요)
    improvement_suggestions: List[str]  # 개선 제안사항


@dataclass
class RecommendationContext:
    """추천 컨텍스트 정보"""
    user_query: str
    user_preferences: Dict[str, Any]
    filters: Dict[str, Any]
    recommendation_count: int
    user_history: Optional[List[Dict[str, Any]]] = None


class RecommendationEvaluator:
    """추천 품질 평가기"""
    
    def __init__(self, products_df: pd.DataFrame, api_key: Optional[str] = None):
        self.products_df = products_df
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        if self.api_key and openai:
            openai.api_key = self.api_key
        
        # 평가 기준 설정
        self.evaluation_thresholds = {
            'excellent': 0.8,
            'good': 0.6,
            'needs_improvement': 0.4
        }
        
        # 평가 히스토리
        self.evaluation_history: List[Dict[str, Any]] = []
    
    def evaluate_recommendations(self, 
                               recommendations: List[Any], 
                               context: RecommendationContext) -> EvaluationMetrics:
        """추천 결과 품질 평가"""
        print("📊 추천 품질 평가 시작...")
        
        if not recommendations:
            return self._create_empty_evaluation()
        
        # 1. 관련성 평가
        relevance_score = self._evaluate_relevance(recommendations, context)
        
        # 2. 다양성 평가
        diversity_score = self._evaluate_diversity(recommendations)
        
        # 3. 신규성 평가
        novelty_score = self._evaluate_novelty(recommendations, context)
        
        # 4. 커버리지 평가
        coverage_score = self._evaluate_coverage(recommendations, context)
        
        # 5. 종합 점수 계산
        overall_score = self._calculate_overall_score(
            relevance_score, diversity_score, novelty_score, coverage_score
        )
        
        # 6. 품질 수준 판정
        quality_level = self._determine_quality_level(overall_score)
        
        # 7. 개선 제안사항 생성
        improvement_suggestions = self._generate_improvement_suggestions(
            relevance_score, diversity_score, novelty_score, coverage_score, context
        )
        
        # 평가 결과 생성
        evaluation = EvaluationMetrics(
            relevance_score=relevance_score,
            diversity_score=diversity_score,
            novelty_score=novelty_score,
            coverage_score=coverage_score,
            overall_score=overall_score,
            quality_level=quality_level,
            improvement_suggestions=improvement_suggestions
        )
        
        # 평가 히스토리 저장
        self._save_evaluation_history(evaluation, context)
        
        print(f"📊 평가 완료: {quality_level} (종합점수: {overall_score:.3f})")
        return evaluation
    
    def _evaluate_relevance(self, 
                           recommendations: List[Any], 
                           context: RecommendationContext) -> float:
        """관련성 평가"""
        if not recommendations:
            return 0.0
        
        relevance_scores = []
        
        for rec in recommendations:
            score = 0.0
            
            # 1. 사용자 쿼리와 상품명 매칭
            query_lower = context.user_query.lower()
            product_name = getattr(rec, 'product_name', '').lower()
            
            # 키워드 매칭 점수
            query_words = set(query_lower.split())
            product_words = set(product_name.split())
            keyword_overlap = len(query_words & product_words) / max(len(query_words), 1)
            score += keyword_overlap * 0.3
            
            # 2. 사용자 선호도 매칭
            if context.user_preferences:
                preference_score = self._calculate_preference_match(rec, context.user_preferences)
                score += preference_score * 0.3
            
            # 3. 필터 조건 매칭
            if context.filters:
                filter_score = self._calculate_filter_match(rec, context.filters)
                score += filter_score * 0.2
            
            # 4. 신뢰도 점수 반영
            confidence = getattr(rec, 'confidence_score', 0.0)
            score += min(confidence, 1.0) * 0.2
            
            relevance_scores.append(score)
        
        return np.mean(relevance_scores) if relevance_scores else 0.0
    
    def _evaluate_diversity(self, recommendations: List[Any]) -> float:
        """다양성 평가"""
        if len(recommendations) < 2:
            return 0.5  # 단일 추천은 중간 점수
        
        # 1. 카테고리 다양성
        categories = [getattr(rec, 'category', '') for rec in recommendations]
        unique_categories = len(set(categories))
        category_diversity = unique_categories / len(recommendations)
        
        # 2. 스타일 키워드 다양성
        all_keywords = []
        for rec in recommendations:
            keywords = getattr(rec, 'style_keywords', [])
            if isinstance(keywords, list):
                all_keywords.extend(keywords)
        
        if all_keywords:
            unique_keywords = len(set(all_keywords))
            keyword_diversity = unique_keywords / len(all_keywords)
        else:
            keyword_diversity = 0.0
        
        # 3. 가격대 다양성 (가능한 경우)
        prices = []
        for rec in recommendations:
            price_str = getattr(rec, 'price', '')
            if isinstance(price_str, str) and '원' in price_str:
                try:
                    price = int(price_str.replace('원', '').replace(',', ''))
                    prices.append(price)
                except:
                    pass
        
        if len(prices) > 1:
            price_std = np.std(prices)
            price_mean = np.mean(prices)
            price_diversity = min(price_std / max(price_mean, 1), 1.0)
        else:
            price_diversity = 0.0
        
        # 종합 다양성 점수
        diversity_score = (category_diversity * 0.4 + 
                          keyword_diversity * 0.4 + 
                          price_diversity * 0.2)
        
        return diversity_score
    
    def _evaluate_novelty(self, 
                         recommendations: List[Any], 
                         context: RecommendationContext) -> float:
        """신규성 평가"""
        if not context.user_history:
            return 0.7  # 히스토리가 없으면 중간 점수
        
        # 사용자 히스토리에서 추천된 상품 ID들
        history_product_ids = set()
        for item in context.user_history:
            product_id = item.get('product_id', '')
            if product_id:
                history_product_ids.add(str(product_id))
        
        # 현재 추천에서 새로운 상품 비율
        current_product_ids = set()
        for rec in recommendations:
            product_id = getattr(rec, 'product_id', '')
            if product_id:
                current_product_ids.add(str(product_id))
        
        if not current_product_ids:
            return 0.0
        
        new_products = current_product_ids - history_product_ids
        novelty_ratio = len(new_products) / len(current_product_ids)
        
        return novelty_ratio
    
    def _evaluate_coverage(self, 
                          recommendations: List[Any], 
                          context: RecommendationContext) -> float:
        """커버리지 평가"""
        # 1. 요청된 개수 대비 실제 추천 개수
        requested_count = context.recommendation_count
        actual_count = len(recommendations)
        
        if requested_count == 0:
            return 1.0
        
        count_coverage = min(actual_count / requested_count, 1.0)
        
        # 2. 필터 조건 커버리지
        filter_coverage = 1.0
        if context.filters:
            covered_filters = 0
            total_filters = len(context.filters)
            
            for rec in recommendations:
                for filter_key, filter_value in context.filters.items():
                    if self._check_filter_coverage(rec, filter_key, filter_value):
                        covered_filters += 1
            
            if total_filters > 0:
                filter_coverage = covered_filters / total_filters
        
        # 3. 사용자 선호도 커버리지
        preference_coverage = 1.0
        if context.user_preferences:
            covered_preferences = 0
            total_preferences = len(context.user_preferences)
            
            for rec in recommendations:
                for pref_key, pref_value in context.user_preferences.items():
                    if self._check_preference_coverage(rec, pref_key, pref_value):
                        covered_preferences += 1
            
            if total_preferences > 0:
                preference_coverage = covered_preferences / total_preferences
        
        # 종합 커버리지 점수
        coverage_score = (count_coverage * 0.4 + 
                         filter_coverage * 0.3 + 
                         preference_coverage * 0.3)
        
        return coverage_score
    
    def _calculate_overall_score(self, 
                                relevance: float, 
                                diversity: float, 
                                novelty: float, 
                                coverage: float) -> float:
        """종합 점수 계산"""
        # 가중치 설정
        weights = {
            'relevance': 0.4,    # 관련성이 가장 중요
            'diversity': 0.25,   # 다양성
            'novelty': 0.2,      # 신규성
            'coverage': 0.15     # 커버리지
        }
        
        overall_score = (
            relevance * weights['relevance'] +
            diversity * weights['diversity'] +
            novelty * weights['novelty'] +
            coverage * weights['coverage']
        )
        
        return overall_score
    
    def _determine_quality_level(self, overall_score: float) -> str:
        """품질 수준 판정"""
        if overall_score >= self.evaluation_thresholds['excellent']:
            return "우수"
        elif overall_score >= self.evaluation_thresholds['good']:
            return "보통"
        else:
            return "개선필요"
    
    def _generate_improvement_suggestions(self, 
                                        relevance: float, 
                                        diversity: float, 
                                        novelty: float, 
                                        coverage: float,
                                        context: RecommendationContext) -> List[str]:
        """개선 제안사항 생성"""
        suggestions = []
        
        # 관련성 개선 제안
        if relevance < 0.6:
            suggestions.append("사용자 쿼리와 더 관련성 높은 상품을 추천하세요")
            suggestions.append("사용자 선호도를 더 정확히 파악하세요")
        
        # 다양성 개선 제안
        if diversity < 0.5:
            suggestions.append("다양한 카테고리와 스타일의 상품을 포함하세요")
            suggestions.append("가격대를 다양화하세요")
        
        # 신규성 개선 제안
        if novelty < 0.3:
            suggestions.append("사용자가 이전에 본 상품과 다른 새로운 상품을 추천하세요")
        
        # 커버리지 개선 제안
        if coverage < 0.7:
            suggestions.append("요청된 개수만큼 충분한 상품을 추천하세요")
            suggestions.append("사용자 선호 조건을 더 많이 반영하세요")
        
        # 일반적인 개선 제안
        if len(suggestions) == 0:
            suggestions.append("현재 추천 품질이 양호합니다")
        
        return suggestions
    
    def _calculate_preference_match(self, 
                                  recommendation: Any, 
                                  preferences: Dict[str, Any]) -> float:
        """선호도 매칭 점수 계산"""
        score = 0.0
        
        # 태그 선호도
        if 'tags' in preferences:
            user_tags = set(preferences['tags'])
            rec_tags = set(getattr(recommendation, 'style_keywords', []))
            if user_tags and rec_tags:
                tag_overlap = len(user_tags & rec_tags) / len(user_tags)
                score += tag_overlap * 0.5
        
        # 카테고리 선호도
        if 'categories' in preferences:
            user_categories = set(preferences['categories'])
            rec_category = getattr(recommendation, 'category', '')
            if user_categories and rec_category:
                category_match = any(cat in rec_category for cat in user_categories)
                score += 0.3 if category_match else 0.0
        
        # 색상 선호도
        if 'color' in preferences:
            user_colors = set(preferences['color'])
            rec_name = getattr(recommendation, 'product_name', '').lower()
            if user_colors and rec_name:
                color_match = any(color in rec_name for color in user_colors)
                score += 0.2 if color_match else 0.0
        
        return score
    
    def _calculate_filter_match(self, 
                              recommendation: Any, 
                              filters: Dict[str, Any]) -> float:
        """필터 조건 매칭 점수 계산"""
        score = 0.0
        
        # 카테고리 필터
        if 'categories' in filters:
            filter_category = filters['categories'].lower()
            rec_category = getattr(recommendation, 'category', '').lower()
            if filter_category in rec_category:
                score += 0.5
        
        # 태그 필터
        if 'tags' in filters:
            filter_tags = set(filters['tags'])
            rec_tags = set(getattr(recommendation, 'style_keywords', []))
            if filter_tags and rec_tags:
                tag_overlap = len(filter_tags & rec_tags) / len(filter_tags)
                score += tag_overlap * 0.5
        
        return score
    
    def _check_filter_coverage(self, 
                             recommendation: Any, 
                             filter_key: str, 
                             filter_value: Any) -> bool:
        """필터 조건 커버리지 확인"""
        if filter_key == 'categories':
            rec_category = getattr(recommendation, 'category', '').lower()
            return filter_value.lower() in rec_category
        elif filter_key == 'tags':
            rec_tags = set(getattr(recommendation, 'style_keywords', []))
            return filter_value in rec_tags
        return True
    
    def _check_preference_coverage(self, 
                                 recommendation: Any, 
                                 pref_key: str, 
                                 pref_value: Any) -> bool:
        """선호도 커버리지 확인"""
        if pref_key == 'categories':
            rec_category = getattr(recommendation, 'category', '').lower()
            # pref_value가 리스트인 경우 처리
            if isinstance(pref_value, list):
                return any(value.lower() in rec_category for value in pref_value)
            else:
                return pref_value.lower() in rec_category
        elif pref_key == 'tags':
            rec_tags = set(getattr(recommendation, 'style_keywords', []))
            # pref_value가 리스트인 경우 처리
            if isinstance(pref_value, list):
                return any(value in rec_tags for value in pref_value)
            else:
                return pref_value in rec_tags
        return True
    
    def _save_evaluation_history(self, 
                                evaluation: EvaluationMetrics, 
                                context: RecommendationContext):
        """평가 히스토리 저장"""
        history_entry = {
            'timestamp': datetime.now().isoformat(),
            'user_query': context.user_query,
            'recommendation_count': context.recommendation_count,
            'evaluation': {
                'relevance_score': evaluation.relevance_score,
                'diversity_score': evaluation.diversity_score,
                'novelty_score': evaluation.novelty_score,
                'coverage_score': evaluation.coverage_score,
                'overall_score': evaluation.overall_score,
                'quality_level': evaluation.quality_level
            },
            'improvement_suggestions': evaluation.improvement_suggestions
        }
        
        self.evaluation_history.append(history_entry)
    
    def _create_empty_evaluation(self) -> EvaluationMetrics:
        """빈 추천에 대한 평가"""
        return EvaluationMetrics(
            relevance_score=0.0,
            diversity_score=0.0,
            novelty_score=0.0,
            coverage_score=0.0,
            overall_score=0.0,
            quality_level="개선필요",
            improvement_suggestions=["추천 결과가 없습니다. 더 많은 상품을 검색해보세요."]
        )
    
    def get_evaluation_summary(self, days: int = 7) -> Dict[str, Any]:
        """평가 히스토리 요약"""
        if not self.evaluation_history:
            return {"message": "평가 히스토리가 없습니다."}
        
        # 최근 N일간의 평가만 필터링
        cutoff_date = datetime.now() - timedelta(days=days)
        recent_evaluations = [
            entry for entry in self.evaluation_history
            if datetime.fromisoformat(entry['timestamp']) > cutoff_date
        ]
        
        if not recent_evaluations:
            return {"message": f"최근 {days}일간의 평가 데이터가 없습니다."}
        
        # 통계 계산
        scores = [entry['evaluation']['overall_score'] for entry in recent_evaluations]
        quality_levels = [entry['evaluation']['quality_level'] for entry in recent_evaluations]
        
        summary = {
            'total_evaluations': len(recent_evaluations),
            'average_score': np.mean(scores),
            'score_std': np.std(scores),
            'quality_distribution': {
                '우수': quality_levels.count('우수'),
                '보통': quality_levels.count('보통'),
                '개선필요': quality_levels.count('개선필요')
            },
            'recent_trend': '개선' if len(scores) >= 2 and scores[-1] > scores[0] else '유지'
        }
        
        return summary


def main():
    """평가기 테스트"""
    # 샘플 데이터 생성
    sample_data = {
        'product_id': ['1', '2', '3', '4', '5'],
        'product_name': [
            '베이직 오버핏 티셔츠',
            '스트릿 그래픽 반팔',
            '꾸안꾸 무지 티셔츠',
            '트렌디 로고 반팔',
            '빈티지 체크 셔츠'
        ],
        'categories': ['상의', '상의', '상의', '상의', '상의'],
        'rating': [4.8, 4.6, 4.9, 4.7, 4.5],
        'review_count': [1500, 800, 2200, 1200, 600]
    }
    
    df = pd.DataFrame(sample_data)
    evaluator = RecommendationEvaluator(df)
    
    # 샘플 추천 결과 (ProductRecommendation 형태로 시뮬레이션)
    class MockRecommendation:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)
    
    recommendations = [
        MockRecommendation(
            product_id='1',
            product_name='베이직 오버핏 티셔츠',
            category='상의',
            style_keywords=['베이직', '오버핏'],
            confidence_score=0.85,
            rating=4.8,
            review_count=1500,
            price='29,000원'
        ),
        MockRecommendation(
            product_id='2',
            product_name='스트릿 그래픽 반팔',
            category='상의',
            style_keywords=['스트릿', '그래픽'],
            confidence_score=0.78,
            rating=4.6,
            review_count=800,
            price='35,000원'
        )
    ]
    
    # 평가 컨텍스트
    context = RecommendationContext(
        user_query='스트릿한 무드의 상의 추천해줘',
        user_preferences={'tags': ['스트릿'], 'categories': ['상의']},
        filters={'categories': '상의'},
        recommendation_count=3,
        user_history=[{'product_id': '3'}]  # 이전에 본 상품
    )
    
    # 평가 실행
    evaluation = evaluator.evaluate_recommendations(recommendations, context)
    
    print("📊 평가 결과:")
    print(f"  - 관련성: {evaluation.relevance_score:.3f}")
    print(f"  - 다양성: {evaluation.diversity_score:.3f}")
    print(f"  - 신규성: {evaluation.novelty_score:.3f}")
    print(f"  - 커버리지: {evaluation.coverage_score:.3f}")
    print(f"  - 종합점수: {evaluation.overall_score:.3f}")
    print(f"  - 품질수준: {evaluation.quality_level}")
    print(f"  - 개선제안: {evaluation.improvement_suggestions}")


if __name__ == "__main__":
    main() 