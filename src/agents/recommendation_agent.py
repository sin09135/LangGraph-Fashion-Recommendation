"""
추천 에이전트
사용자 요청에 따른 상품 추천 및 설명 생성
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
import json
import os
import math

# 벡터 DB 임포트
# from simple_vector_db import SimpleVectorDB

try:
    import openai
except ImportError:
    print("OpenAI 라이브러리가 설치되지 않았습니다.")
    openai = None

# 리뷰 분석기 임포트
try:
    from utils.review_analyzer import ReviewAnalyzer
except ImportError:
    print("리뷰 분석기가 설치되지 않았습니다.")
    ReviewAnalyzer = None


@dataclass
class ProductRecommendation:
    """상품 추천 데이터 클래스"""
    product_id: str
    product_name: str
    category: str
    style_keywords: List[str]
    rating: float
    review_count: int
    description: str
    recommendation_reason: str
    confidence_score: float
    price: Optional[str] = None
    url: str = ''
    image_url: str = ''
    representative_review: Optional[str] = None  # 대표 리뷰 추가


def robust_style_keywords(product):
    """상품의 스타일 키워드를 안전하게 추출"""
    try:
        # dict-like
        if isinstance(product, dict):
            val = product.get('style_keywords', product.get('tags', []))
        # pandas Series, numpy.void 등
        elif hasattr(product, '__contains__'):
            if 'style_keywords' in product:
                val = product['style_keywords']
            elif 'tags' in product:
                val = product['tags']
            else:
                val = []
        else:
            val = []
        if not isinstance(val, list):
            return []
        return val
    except Exception:
        return []


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


class RecommendationAgent:
    """추천 에이전트"""
    
    def __init__(self, products_df: pd.DataFrame, api_key: Optional[str] = None, reviews_data: Optional[Dict[str, List[Dict[str, Any]]]] = None):
        try:
            from src.simple_vector_db import SimpleVectorDB
            self.vector_db = SimpleVectorDB()
            self.vector_db.add_products(products_df)
        except ImportError:
            print("벡터 DB를 사용할 수 없습니다.")
            self.vector_db = None
        
        self.products_df = products_df
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        if self.api_key and openai:
            openai.api_key = self.api_key
        
        # 리뷰 데이터 및 분석기 초기화
        self.reviews_data = reviews_data or {}
        self.review_analyzer = ReviewAnalyzer() if ReviewAnalyzer else None
        
        # 추천 히스토리
        self.recommendation_history: List[Dict[str, Any]] = []
        
        # 시스템 프롬프트
        self.system_prompt = """
        당신은 패션 상품 추천 전문가입니다.

        주요 역할:
        1. 사용자 요청에 맞는 상품 추천
        2. 추천 이유를 자연스럽고 설득력 있게 설명
        3. 사용자 취향과 선호도 반영
        4. 트렌드와 인기도 고려

        추천 설명 스타일:
        - 친근하고 자연스러운 톤 사용
        - 구체적인 스타일 특징 언급
        - 평점과 리뷰 수 활용
        - 사용자 요청과의 연관성 강조
        - 이모티콘 적절히 활용

        예시:
        "이 반팔은 꾸안꾸 무드에 딱이고, 요즘 무신사 랭킹에도 올라와 있어요! 4.8점의 높은 평점과 2000개 이상의 리뷰를 받았답니다 😊" """
            
    def recommend_products(self, 
                          user_request: Dict[str, Any], 
                          top_k: int = 5) -> List[ProductRecommendation]:
                          
        """상품 추천 수행 (상품 데이터 + 리뷰 데이터 하이브리드)"""
        filters = user_request.get('filters', {})
        user_preferences = user_request.get('user_preferences', {})
        query = user_request.get('original_query', '')

        print("🔍 하이브리드 추천 시작: 상품 데이터 + 리뷰 데이터 검색")
        
        # 1. 상품 데이터 기반 추천
        if self._should_use_sql_based(filters, query):
            print("🟨 SQL 기반 상품 추천 실행")
            product_recommendations = self._sql_based_recommendation(filters, user_preferences, top_k * 2)
        else:
            print("🟦 Vector DB 기반 상품 추천 실행")
            product_recommendations = self._vector_based_recommendation(query, filters, user_preferences, top_k * 2)
        
        # 2. 리뷰 데이터 기반 추천
        print("🟪 리뷰 데이터 기반 추천 실행")
        review_recommendations = self._review_based_recommendation(query, filters, user_preferences, top_k * 2)
        
        # 3. 두 결과를 결합하고 중복 제거
        print("🔄 상품 데이터 + 리뷰 데이터 결합")
        combined_recommendations = self._combine_recommendations(
            product_recommendations, 
            review_recommendations, 
            top_k
        )
        
        self._save_recommendation_history(user_request, combined_recommendations)
        return combined_recommendations
    
    def _should_use_sql_based(self, filters: Dict[str, Any], query: str) -> bool:
        """SQL 기반 추천 사용 여부 결정"""
        # 명확한 조건이 2개 이상이면 SQL 기반
        clear_conditions = sum([
            1 if filters.get('categories') else 0,
            1 if filters.get('tags') else 0,  # style_keywords -> tags로 수정
            1 if filters.get('color') else 0,
            1 if filters.get('brand') else 0,
            1 if filters.get('price_range') else 0
        ])
        
        print(f"🔍 SQL 분기 조건 확인: {clear_conditions}개 조건 (필터: {filters})")
        return clear_conditions >= 2
    
    def _convert_image_url(self, image_path: str) -> str:
        """이미지 경로를 웹 접근 가능한 URL로 변환"""
        if not image_path:
            return ""
        
        # 로컬 파일 경로인 경우 웹 URL로 변환
        if image_path.startswith('./') or image_path.startswith('/'):
            # 파일명만 추출
            filename = os.path.basename(image_path)
            return f"/images/{filename}"
        
        # 이미 웹 URL인 경우 그대로 반환
        if image_path.startswith('http'):
            return image_path
        
        # 상대 경로인 경우 웹 URL로 변환
        filename = os.path.basename(image_path)
        return f"/images/{filename}"
    
    def _sql_based_recommendation(self, 
                                 filters: Dict[str, Any], 
                                 user_preferences: Dict[str, Any], 
                                 top_k: int) -> List[ProductRecommendation]:
        """🟨 SQL 기반 추천 (조건 명확)"""
        print("🟨 SQL 기반 추천 실행")
        
        # 1. 조건 기반 필터링
        filtered_products = self._filter_products(filters)
        
        if filtered_products.empty:
            # 결과가 없으면 필터 완화
            filtered_products = self._relax_filters(filters)
        
        # 2. 스코어링 및 정렬
        scored_products = self._score_products(filtered_products, user_preferences)
        top_products = scored_products.sort_values('confidence_score', ascending=False)
        
        # URL에서 product_id 추출하여 중복 제거
        if 'url' in top_products.columns:
            import re
            top_products['extracted_product_id'] = top_products['url'].apply(
                lambda x: re.search(r'/products/(\d+)', str(x)).group(1) if re.search(r'/products/(\d+)', str(x)) else None
            )
            top_products = top_products.drop_duplicates(subset='extracted_product_id')
            top_products = top_products.drop(columns=['extracted_product_id'])
        
        # 충분한 상품을 확보하기 위해 더 많은 후보에서 선택
        top_products = top_products.head(max(top_k * 2, 10))  # 최소 10개, 요청된 개수의 2배
        top_products = top_products.head(top_k)
        
        # 3. 추천 결과 생성
        recommendations = []
        for _, product in top_products.iterrows():
            reason = self._generate_recommendation_reason(product, {'filters': filters})
            style_keywords = robust_style_keywords(product)
            
            # 대표 리뷰 추출
            representative_review = self._get_representative_review(product)
            
            recommendation = ProductRecommendation(
                product_id=str(product.get('product_id', '') or ''),
                product_name=str(product.get('product_name', '') or ''),
                category=str(product.get('categories', '') or ''),
                style_keywords=style_keywords,
                rating=safe_float(product.get('rating', 0.0)),
                review_count=safe_int(product.get('review_count', 0)),
                description=str(product.get('product_name', '') or ''),
                recommendation_reason=str(reason or ''),
                confidence_score=safe_float(product.get('confidence_score', 0.0)),
                price=product.get('price', '가격 정보 없음'),
                url=str(product.get('url', '') or ''),
                image_url=self._convert_image_url(str(product.get('image_url', '') or '')),
                representative_review=representative_review
            )
            recommendations.append(recommendation)
        
        return recommendations
    
    def _vector_based_recommendation(self, 
                                   query: str, 
                                   filters: Dict[str, Any], 
                                   user_preferences: Dict[str, Any], 
                                   top_k: int) -> List[ProductRecommendation]:
        """🟦 Vector DB 기반 추천 (유사 의미 요청)"""
        print("🟦 Vector DB 기반 추천 실행")
        
        # 1. 벡터 DB에서 유사 상품 후보군 추출
        vector_candidates = self.vector_db.search_similar_products(
            query=query,
            top_k=50,  # 후보군 더 넉넉히 확보 (중복 제거 고려)
            filters=filters
        )
        
        if not vector_candidates:
            # fallback: 기존 DataFrame 필터링
            filtered_products = self._filter_products(filters)
            if filtered_products.empty:
                filtered_products = self._relax_filters(filters)
            scored_products = self._score_products(filtered_products, user_preferences)
            top_products = scored_products.sort_values('confidence_score', ascending=False)
            
            # URL에서 product_id 추출하여 중복 제거
            if 'url' in top_products.columns:
                import re
                top_products['extracted_product_id'] = top_products['url'].apply(
                    lambda x: re.search(r'/products/(\d+)', str(x)).group(1) if re.search(r'/products/(\d+)', str(x)) else None
                )
                top_products = top_products.drop_duplicates(subset='extracted_product_id')
                top_products = top_products.drop(columns=['extracted_product_id'])
            
            # 충분한 상품을 확보하기 위해 더 많은 후보에서 선택
            top_products = top_products.head(max(top_k * 2, 10))  # 최소 10개, 요청된 개수의 2배
            top_products = top_products.head(top_k)
        else:
            # 2. 후보군 DataFrame 변환
            candidates_df = pd.DataFrame([c['metadata'] for c in vector_candidates])
            # 3. 기존 스코어링/선호도 반영
            scored_products = self._score_products(candidates_df, user_preferences)
            top_products = scored_products.sort_values('confidence_score', ascending=False)
            
            # URL에서 product_id 추출하여 중복 제거
            if 'url' in top_products.columns:
                import re
                top_products['extracted_product_id'] = top_products['url'].apply(
                    lambda x: re.search(r'/products/(\d+)', str(x)).group(1) if re.search(r'/products/(\d+)', str(x)) else None
                )
                top_products = top_products.drop_duplicates(subset='extracted_product_id')
                top_products = top_products.drop(columns=['extracted_product_id'])
            
            # 충분한 상품을 확보하기 위해 더 많은 후보에서 선택
            top_products = top_products.head(max(top_k * 2, 10))  # 최소 10개, 요청된 개수의 2배
            top_products = top_products.head(top_k)
        
        # 4. 추천 결과 생성
        recommendations = []
        for _, product in top_products.iterrows():
            reason = self._generate_recommendation_reason(product, {'original_query': query})
            style_keywords = robust_style_keywords(product)
            
            # 대표 리뷰 추출
            representative_review = self._get_representative_review(product)
            
            recommendation = ProductRecommendation(
                product_id=str(product.get('product_id', '') or ''),
                product_name=str(product.get('product_name', '') or ''),
                category=str(product.get('categories', '') or ''),
                style_keywords=style_keywords,
                rating=safe_float(product.get('rating', 0.0)),
                review_count=safe_int(product.get('review_count', 0)),
                description=str(product.get('product_name', '') or ''),
                recommendation_reason=str(reason or ''),
                confidence_score=safe_float(product.get('confidence_score', 0.0)),
                price=product.get('price', '가격 정보 없음'),
                url=str(product.get('url', '') or ''),
                image_url=self._convert_image_url(str(product.get('image_url', '') or '')),
                representative_review=representative_review
            )
            recommendations.append(recommendation)
        
        return recommendations
    
    def _filter_products(self, filters: Dict[str, Any]) -> pd.DataFrame:
        """상품 필터링"""
        filtered_df = self.products_df.copy()
        if not isinstance(filtered_df, pd.DataFrame):
            return pd.DataFrame()
        # 이하 모든 필터링 로직은 DataFrame임을 가정하고 동작
        
        # 카테고리 필터 (더 엄격한 필터링)
        if 'categories' in filters and filters['categories']:
            categories = filters['categories']
            if 'categories' in filtered_df.columns:
                # 카테고리가 리스트인 경우와 문자열인 경우 모두 처리
                def category_match(category_data):
                    if isinstance(category_data, list):
                        return any(categories.lower() in str(cat).lower() for cat in category_data)
                    else:
                        return categories.lower() in str(category_data).lower()
                
                filtered_df = filtered_df[filtered_df['categories'].apply(category_match)]
        
        # 스타일 필터
        if 'tags' in filters and filters['tags']:
            tags = filters['tags']
            if 'tags' in filtered_df.columns:
                filtered_df = filtered_df[
                    filtered_df.apply(
                        lambda row: (
                            (isinstance(row.get('tags', None), str) and tags in row['tags']) or
                            (isinstance(row.get('tags', None), list) and tags in row['tags'])
                        ), axis=1
                    )
                ]
        
        # 색상 필터
        if 'color' in filters and filters['color']:
            color = filters['color']
            if 'product_name' in filtered_df.columns:
                filtered_df = filtered_df[
                    filtered_df['product_name'].astype(str).str.contains(color, na=False, case=False)
                ]
        
        # 브랜드 필터
        if 'brand' in filters and filters['brand']:
            brand = filters['brand']
            if 'brand' in filtered_df.columns:
                filtered_df = filtered_df[
                    filtered_df['brand'].astype(str).str.contains(brand, na=False, case=False)
                ]
        
        # 총장(길이) 필터
        if 'length' in filters and filters['length']:
            op, value = filters['length']
            if 'length' in filtered_df.columns:
                if op == '<=':
                    filtered_df = filtered_df[filtered_df['length'].notnull() & (filtered_df['length'] <= value)]
                elif op == '>=':
                    filtered_df = filtered_df[filtered_df['length'].notnull() & (filtered_df['length'] >= value)]
                elif op == '==':
                    filtered_df = filtered_df[filtered_df['length'].notnull() & (filtered_df['length'] == value)]
        
        # 가슴단면 필터
        if 'chest' in filters and filters['chest']:
            op, value = filters['chest']
            if 'chest' in filtered_df.columns:
                if op == '<=':
                    filtered_df = filtered_df[filtered_df['chest'].notnull() & (filtered_df['chest'] <= value)]
                elif op == '>=':
                    filtered_df = filtered_df[filtered_df['chest'].notnull() & (filtered_df['chest'] >= value)]
                elif op == '==':
                    filtered_df = filtered_df[filtered_df['chest'].notnull() & (filtered_df['chest'] == value)]
        
        # 어깨너비 필터
        if 'shoulder' in filters and filters['shoulder']:
            op, value = filters['shoulder']
            if 'shoulder' in filtered_df.columns:
                if op == '<=':
                    filtered_df = filtered_df[filtered_df['shoulder'].notnull() & (filtered_df['shoulder'] <= value)]
                elif op == '>=':
                    filtered_df = filtered_df[filtered_df['shoulder'].notnull() & (filtered_df['shoulder'] >= value)]
                elif op == '==':
                    filtered_df = filtered_df[filtered_df['shoulder'].notnull() & (filtered_df['shoulder'] == value)]
        
        # 가격대 필터 (후기 기반이 아니면, 가격 정보가 있을 때만 적용)
        if 'price_range' in filters and filters['price_range']:
            price_range = filters['price_range']
            if 'price' in filtered_df.columns:
                if price_range == '저렴':
                    filtered_df = filtered_df[filtered_df['price'] <= filtered_df['price'].quantile(0.3)]
                elif price_range == '고급':
                    filtered_df = filtered_df[filtered_df['price'] >= filtered_df['price'].quantile(0.7)]
        
        # 제외할 상품 ID
        if 'exclude_ids' in filters and filters['exclude_ids']:
            exclude_ids = filters['exclude_ids']
            if 'product_id' in filtered_df.columns:
                filtered_df = filtered_df[
                    ~filtered_df['product_id'].isin(exclude_ids)
                ]
        
        # 크롭티/크롭 스타일 필터 (총장 66cm 미만, 상의)
        is_crop = False
        crop_keywords = ['크롭', '크롭티', '크롭탑']
        if 'tags' in filters and filters['tags']:
            if any(kw in str(filters['tags']) for kw in crop_keywords):
                is_crop = True
        if 'product_name' in filters and filters['product_name']:
            if any(kw in str(filters['product_name']) for kw in crop_keywords):
                is_crop = True
        if 'tags' in filters and filters['tags']:
            if any(kw in str(filters['tags']) for kw in crop_keywords):
                is_crop = True
        # 크롭 조건이 있으면 상의+총장 66cm 미만 필터 적용
        if is_crop:
            # 상의 필터
            if 'categories' in filtered_df.columns:
                filtered_df = filtered_df[
                    filtered_df['categories'].apply(
                        lambda x: ('상의' in x) if isinstance(x, list) else ('상의' in str(x))
                    )
                ]
            # 총장 66cm 미만 필터
            if 'length' in filtered_df.columns:
                filtered_df = filtered_df[
                    (filtered_df['length'].notnull()) & (filtered_df['length'] < 66)
                ]
        
        return filtered_df
    
    def _relax_filters(self, filters: Dict[str, Any]) -> pd.DataFrame:
        """필터 완화 (결과가 없을 때)"""
        relaxed_filters = filters.copy()
        
        # 스타일 필터 제거
        if 'tags' in relaxed_filters:
            del relaxed_filters['tags']
        
        # 색상 필터 제거
        if 'color' in relaxed_filters:
            del relaxed_filters['color']
        
        # 가격대 필터 제거
        if 'price_range' in relaxed_filters:
            del relaxed_filters['price_range']
        
        return self._filter_products(relaxed_filters)
    
    def _score_products(self, 
                       products: pd.DataFrame, 
                       user_preferences: Dict[str, Any]) -> pd.DataFrame:
        """상품 스코어링 (리뷰 분석 포함)"""
        scored_products = products.copy()
        
        # 기본 점수 계산
        scored_products['base_score'] = (
            scored_products['rating'] * np.log1p(scored_products['review_count'])
        )
        
        # 사용자 선호도 반영
        preference_score = np.zeros(len(scored_products))
        
        # 스타일 선호도
        if 'tags' in user_preferences:
            for style in user_preferences['tags']:
                style_match = scored_products.apply(
                    lambda row: (
                        (isinstance(row.get('tags', ''), str) and style in row['tags']) or
                        (isinstance(row.get('tags', []), list) and style in row['tags'])
                    ), axis=1
                )
                preference_score += style_match.astype(float) * 0.3
        
        # 카테고리 선호도
        if 'categories' in user_preferences:
            for category in user_preferences['categories']:
                category_match = scored_products['categories'].str.contains(
                    category, na=False, case=False
                )
                preference_score += category_match.astype(float) * 0.2
        
        # 색상 선호도
        if 'color' in user_preferences:
            for color in user_preferences['color']:
                color_match = scored_products['product_name'].str.contains(
                    color, na=False, case=False
                )
                preference_score += color_match.astype(float) * 0.1
        
        # 리뷰 기반 점수 (새로 추가)
        review_score = np.zeros(len(scored_products))
        if self.review_analyzer and self.reviews_data:
            review_score = self._calculate_review_based_score(scored_products, user_preferences)
        
        # 최종 점수 계산 (리뷰 점수 포함)
        scored_products['preference_score'] = preference_score
        scored_products['review_score'] = review_score
        scored_products['confidence_score'] = (
            scored_products['base_score'] + 
            scored_products['preference_score'] + 
            scored_products['review_score'] * 0.3  # 리뷰 점수 가중치
        )
        
        # 정렬
        scored_products = scored_products.sort_values(
            'confidence_score', ascending=False
        )
        
        return scored_products
    
    def _calculate_review_based_score(self, 
                                    products: pd.DataFrame, 
                                    user_preferences: Dict[str, Any]) -> np.ndarray:
        """리뷰 기반 점수 계산"""
        review_score = np.zeros(len(products))
        
        # DataFrame을 리셋 인덱스하여 연속적인 인덱스 보장
        products_reset = products.reset_index(drop=True)
        
        for i in range(len(products_reset)):
            try:
                product = products_reset.iloc[i]
                
                # 상품 ID 추출
                product_id = str(product.get('product_id', ''))
                if not product_id:
                    url = str(product.get('url', ''))
                    import re
                    match = re.search(r'/products/(\d+)', url)
                    if match:
                        product_id = match.group(1)
                
                if not product_id or product_id not in self.reviews_data:
                    continue
                
                # 해당 상품의 리뷰 분석
                product_reviews = self.reviews_data[product_id]
                if not product_reviews:
                    continue
                
                analysis = self.review_analyzer.analyze_product_reviews(product_reviews)
                if not analysis:
                    continue
                
                # 리뷰 점수 계산
                score = 0.0
                
                # 1. 감정 점수 (긍정적인 리뷰가 많을수록 높은 점수)
                sentiment_score = analysis.get('avg_sentiment', 0)
                score += sentiment_score * 0.4
                
                # 2. 긍정 비율 (긍정 리뷰 비율이 높을수록 높은 점수)
                positive_ratio = analysis.get('positive_ratio', 0)
                score += positive_ratio * 0.3
                
                # 3. 키워드 매칭 점수 (사용자 요청과 리뷰 키워드 매칭)
                keyword_score = self._calculate_keyword_matching_score(analysis, user_preferences)
                score += keyword_score * 0.3
                
                review_score[i] = score
                
            except Exception as e:
                print(f"리뷰 점수 계산 오류 (인덱스 {i}): {e}")
                continue
        
        return review_score
    
    def _calculate_keyword_matching_score(self, 
                                        analysis: Dict[str, Any], 
                                        user_preferences: Dict[str, Any]) -> float:
        """키워드 매칭 점수 계산"""
        score = 0.0
        keyword_summary = analysis.get('keyword_summary', {})
        
        # 사용자 요청에서 키워드 추출 (간단한 구현)
        user_query = user_preferences.get('original_query', '').lower()
        
        # 착용감 관련 키워드 매칭
        if any(word in user_query for word in ['착용감', '편안', '입기', '핏']):
            if '착용감' in keyword_summary:
                score += 0.3
        
        # 가성비 관련 키워드 매칭
        if any(word in user_query for word in ['가성비', '저렴', '비싸다', '가격']):
            if '가격' in keyword_summary:
                score += 0.3
        
        # 색상 관련 키워드 매칭
        if any(word in user_query for word in ['색상', '컬러', '블랙', '화이트', '그레이']):
            if '색상' in keyword_summary:
                score += 0.2
        
        # 소재 관련 키워드 매칭
        if any(word in user_query for word in ['소재', '면', '코튼', '린넨']):
            if '소재' in keyword_summary:
                score += 0.2
        
        return score
    
    def _get_representative_review(self, product) -> Optional[str]:
        """대표 리뷰 추출 (가장 도움된 리뷰 또는 최신 리뷰)"""
        if not self.reviews_data:
            return None
        
        try:
            # 상품 ID 추출
            product_id = str(product.get('product_id', ''))
            if not product_id:
                url = str(product.get('url', ''))
                import re
                match = re.search(r'/products/(\d+)', url)
                if match:
                    product_id = match.group(1)
            
            if not product_id or product_id not in self.reviews_data:
                return None
            
            # 해당 상품의 리뷰들
            product_reviews = self.reviews_data[product_id]
            if not product_reviews:
                return None
            
            # 가장 도움된 리뷰 선택 (helpful_count 기준)
            best_review = max(product_reviews, key=lambda x: x.get('helpful_count', 0))
            
            # 리뷰 내용이 너무 길면 자르기
            content = best_review.get('content', '').strip()
            if len(content) > 100:
                content = content[:97] + "..."
            
            return content
            
        except Exception as e:
            print(f"대표 리뷰 추출 오류: {e}")
            return None
    
    def _generate_recommendation_reason(self, 
                                      product, 
                                      user_request: Dict[str, Any]) -> str:
        """추천 이유 생성 (리뷰 분석 포함)"""
        # 리뷰 기반 추천 이유 우선 시도
        review_reason = self._generate_review_based_reason(product, user_request)
        if review_reason:
            return review_reason
        
        # 기존 방식으로 fallback
        product_name = product.get('product_name', '') if hasattr(product, 'get') else ''
        category = product.get('categories', '') if hasattr(product, 'get') else ''
        style_keywords = robust_style_keywords(product)
        rating = product.get('rating', 0) if hasattr(product, 'get') else 0
        review_count = product.get('review_count', 0) if hasattr(product, 'get') else 0
        
        reasons = []
        
        # 스타일 관련 이유
        if style_keywords:
            style_text = ', '.join(style_keywords[:2])  # 상위 2개만
            reasons.append(f"{style_text} 스타일")
        
        # 평점 관련 이유
        if rating >= 4.8:
            reasons.append("매우 높은 평점")
        elif rating >= 4.5:
            reasons.append("높은 평점")
        
        # 리뷰 수 관련 이유
        if review_count >= 1000:
            reasons.append("많은 리뷰")
        elif review_count >= 100:
            reasons.append("적당한 리뷰")
        
        # 카테고리 관련 이유
        if category:
            reasons.append(f"{category} 카테고리")
        
        # 사용자 요청과의 연관성
        original_query = user_request.get('original_query', '').lower()
        if '꾸안꾸' in original_query and '베이직' in style_keywords:
            reasons.append("꾸안꾸 무드에 딱")
        elif '스트릿' in original_query and '스트릿' in style_keywords:
            reasons.append("스트릿한 느낌")
        elif '저렴' in original_query:
            reasons.append("가성비 좋음")
        
        # 이유 조합
        if reasons:
            reason_text = f"{', '.join(reasons)}의 상품이에요!"
            if rating >= 4.5:
                reason_text += f" {rating:.1f}점의 높은 평점을 받았답니다 😊"
            if review_count >= 100:
                reason_text += f" 리뷰도 {review_count}개나 있어요!"
        else:
            reason_text = "사용자님께 딱 맞는 상품이에요! 😊"
        
        return reason_text
    
    def _generate_review_based_reason(self, 
                                    product, 
                                    user_request: Dict[str, Any]) -> str:
        """리뷰 분석 기반 추천 이유 생성"""
        if not self.review_analyzer or not self.reviews_data:
            return ""
        
        try:
            # 상품 ID 추출
            product_id = str(product.get('product_id', ''))
            if not product_id:
                # URL에서 ID 추출 시도
                url = str(product.get('url', ''))
                import re
                match = re.search(r'/products/(\d+)', url)
                if match:
                    product_id = match.group(1)
            
            if not product_id or product_id not in self.reviews_data:
                return ""
            
            # 해당 상품의 리뷰 분석
            product_reviews = self.reviews_data[product_id]
            if not product_reviews:
                return ""
            
            analysis = self.review_analyzer.analyze_product_reviews(product_reviews)
            if not analysis:
                return ""
            
            # 리뷰 기반 추천 이유 생성
            reason = self.review_analyzer.generate_review_based_recommendation_reason(
                analysis, 
                user_request.get('original_query', '')
            )
            
            return reason
            
        except Exception as e:
            print(f"리뷰 기반 추천 이유 생성 오류: {e}")
            return ""
    
    def _save_recommendation_history(self, 
                                   user_request: Dict[str, Any], 
                                   recommendations: List[ProductRecommendation]):
        """추천 히스토리 저장"""
        history_entry = {
            'timestamp': pd.Timestamp.now().isoformat(),
            'user_request': user_request,
            'recommendations': [
                {
                    'product_id': rec.product_id,
                    'product_name': rec.product_name,
                    'confidence_score': rec.confidence_score
                }
                for rec in recommendations
            ]
        }
        
        self.recommendation_history.append(history_entry)
        
        # 히스토리 크기 제한 (최근 100개만 유지)
        if len(self.recommendation_history) > 100:
            self.recommendation_history = self.recommendation_history[-100:]
    
    def get_recommendation_summary(self) -> Dict[str, Any]:
        """추천 요약 정보 반환"""
        if not self.recommendation_history:
            return {}
        
        total_recommendations = len(self.recommendation_history)
        recent_recommendations = self.recommendation_history[-10:]  # 최근 10개
        
        # 가장 많이 추천된 상품
        product_counts = {}
        for entry in recent_recommendations:
            for rec in entry['recommendations']:
                product_id = rec['product_id']
                product_counts[product_id] = product_counts.get(product_id, 0) + 1
        
        most_recommended = sorted(
            product_counts.items(), 
            key=lambda x: x[1], 
            reverse=True
        )[:5]
        
        return {
            'total_recommendations': total_recommendations,
            'recent_recommendations': len(recent_recommendations),
            'most_recommended_products': most_recommended
        }
    
    def update_user_feedback(self, 
                           product_id: str, 
                           feedback_type: str, 
                           feedback_value: float):
        """사용자 피드백 반영"""
        # 실제 구현에서는 사용자 피드백을 저장하고
        # 다음 추천에 반영하는 로직을 구현
        feedback_entry = {
            'timestamp': pd.Timestamp.now().isoformat(),
            'product_id': product_id,
            'feedback_type': feedback_type,
            'feedback_value': feedback_value
        }
        
        # 여기에 피드백 저장 로직 추가
        print(f"피드백 저장: {feedback_entry}")
    
    def _review_based_recommendation(self, 
                                   query: str, 
                                   filters: Dict[str, Any], 
                                   user_preferences: Dict[str, Any], 
                                   top_k: int) -> List[ProductRecommendation]:
        """🟪 리뷰 데이터 기반 추천"""
        print("🟪 리뷰 데이터에서 사용자 의도 검색 중...")
        
        if not self.reviews_data:
            print("리뷰 데이터가 없습니다.")
            return []
        
        # 리뷰에서 사용자 의도와 관련된 상품 찾기
        review_matches = []
        
        for product_id, reviews in self.reviews_data.items():
            # 해당 상품의 상품 정보 찾기
            product_info = self._get_product_by_id(product_id)
            if product_info is None:
                continue
            
            # 리뷰 내용에서 사용자 의도 검색
            review_score = self._calculate_review_relevance_score(query, reviews, filters)
            
            if review_score > 0:
                review_matches.append({
                    'product_id': product_id,
                    'product_info': product_info,
                    'review_score': review_score,
                    'matching_reviews': self._find_matching_reviews(query, reviews)
                })
        
        # 리뷰 점수로 정렬
        review_matches.sort(key=lambda x: x['review_score'], reverse=True)
        
        # 상위 상품들을 추천 결과로 변환
        recommendations = []
        for match in review_matches[:top_k]:
            product_info = match['product_info']
            matching_reviews = match['matching_reviews']
            
            # 리뷰 기반 추천 이유 생성
            reason = self._generate_review_based_reason(product_info, {
                'original_query': query,
                'filters': filters,
                'matching_reviews': matching_reviews
            })
            
            # 대표 리뷰 (가장 관련성 높은 리뷰)
            representative_review = matching_reviews[0]['content'] if matching_reviews else None
            
            style_keywords = robust_style_keywords(product_info)
            
            recommendation = ProductRecommendation(
                product_id=str(product_info.get('product_id', '') or ''),
                product_name=str(product_info.get('product_name', '') or ''),
                category=str(product_info.get('categories', '') or ''),
                style_keywords=style_keywords,
                rating=safe_float(product_info.get('rating', 0.0)),
                review_count=safe_int(product_info.get('review_count', 0)),
                description=str(product_info.get('product_name', '') or ''),
                recommendation_reason=str(reason or ''),
                confidence_score=safe_float(match['review_score']),
                price=product_info.get('price', '가격 정보 없음'),
                url=str(product_info.get('url', '') or ''),
                image_url=self._convert_image_url(str(product_info.get('image_url', '') or '')),
                representative_review=representative_review
            )
            recommendations.append(recommendation)
        
        print(f"🟪 리뷰 기반 추천 완료: {len(recommendations)}개 상품")
        return recommendations
    
    def _get_product_by_id(self, product_id: str) -> Optional[Dict[str, Any]]:
        """product_id로 상품 정보 찾기"""
        try:
            # URL에서 product_id 추출하여 매칭
            for _, product in self.products_df.iterrows():
                url = str(product.get('url', ''))
                if url and product_id in url:
                    return product.to_dict()
            return None
        except Exception as e:
            print(f"상품 정보 조회 오류: {e}")
            return None
    
    def _calculate_review_relevance_score(self, 
                                        query: str, 
                                        reviews: List[Dict[str, Any]], 
                                        filters: Dict[str, Any]) -> float:
        """리뷰 내용과 사용자 의도의 관련성 점수 계산"""
        if not query or not reviews:
            return 0.0
        
        total_score = 0.0
        query_lower = query.lower()
        
        # 카테고리 필터링 (카테고리가 명시된 경우)
        if 'categories' in filters and filters['categories']:
            # 카테고리 키워드가 쿼리에 포함되어 있는지 확인
            category_keywords = {
                '상의': ['상의', '티셔츠', '셔츠', '니트', '후드', '맨투맨', '반팔', '긴팔'],
                '하의': ['하의', '바지', '청바지', '슬랙스', '트레이닝', '반바지', '팬츠'],
                '신발': ['신발', '운동화', '스니커즈', '로퍼', '옥스포드'],
                '아우터': ['아우터', '패딩', '코트', '자켓', '가디건']
            }
            
            target_category = filters['categories'].lower()
            category_match = False
            
            for category, keywords in category_keywords.items():
                if target_category in category.lower():
                    # 해당 카테고리 키워드가 쿼리에 포함되어 있는지 확인
                    if any(keyword in query_lower for keyword in keywords):
                        category_match = True
                        break
            
            # 카테고리가 매칭되지 않으면 점수 감소
            if not category_match:
                return 0.0
        
        # 키워드 매칭 점수
        keyword_score = 0.0
        for review in reviews:
            content = review.get('content', '').lower()
            if query_lower in content:
                keyword_score += 1.0
            # 부분 매칭도 고려
            for word in query_lower.split():
                if word in content and len(word) > 2:
                    keyword_score += 0.5
        
        # 리뷰 평점 점수
        rating_score = 0.0
        for review in reviews:
            rating = review.get('rating', 5)
            rating_score += rating / 5.0
        
        # 도움수 점수
        helpful_score = 0.0
        for review in reviews:
            helpful_count = review.get('helpful_count', 0)
            helpful_score += min(helpful_count / 10.0, 1.0)  # 최대 1.0
        
        # 가중 평균 계산
        if reviews:
            total_score = (keyword_score * 0.5 + rating_score * 0.3 + helpful_score * 0.2) / len(reviews)
        
        return total_score
    
    def _find_matching_reviews(self, 
                             query: str, 
                             reviews: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """사용자 의도와 매칭되는 리뷰들 찾기"""
        if not query or not reviews:
            return []
        
        matching_reviews = []
        query_lower = query.lower()
        
        for review in reviews:
            content = review.get('content', '').lower()
            score = 0.0
            
            # 정확 매칭
            if query_lower in content:
                score += 2.0
            
            # 키워드 매칭
            for word in query_lower.split():
                if word in content and len(word) > 2:
                    score += 0.5
            
            # 평점과 도움수 고려
            rating = review.get('rating', 5)
            helpful_count = review.get('helpful_count', 0)
            score += (rating / 5.0) * 0.3 + min(helpful_count / 10.0, 1.0) * 0.2
            
            if score > 0.5:  # 임계값
                matching_reviews.append({
                    'content': review.get('content', ''),
                    'rating': rating,
                    'helpful_count': helpful_count,
                    'score': score
                })
        
        # 점수로 정렬
        matching_reviews.sort(key=lambda x: x['score'], reverse=True)
        return matching_reviews
    
    def _combine_recommendations(self, 
                               product_recommendations: List[ProductRecommendation], 
                               review_recommendations: List[ProductRecommendation], 
                               top_k: int) -> List[ProductRecommendation]:
        """상품 데이터와 리뷰 데이터 추천 결과 결합"""
        print("🔄 추천 결과 결합 중...")
        
        # 모든 추천 결과를 하나의 리스트로 합치기
        all_recommendations = product_recommendations + review_recommendations
        
        # 상품 ID 기준으로 중복 제거 (더 높은 신뢰도 점수 유지)
        unique_recommendations = {}
        for rec in all_recommendations:
            product_id = rec.product_id
            if product_id not in unique_recommendations or rec.confidence_score > unique_recommendations[product_id].confidence_score:
                unique_recommendations[product_id] = rec
        
        # 신뢰도 점수로 정렬
        sorted_recommendations = sorted(
            unique_recommendations.values(), 
            key=lambda x: x.confidence_score, 
            reverse=True
        )
        
        # 상위 k개 선택
        final_recommendations = sorted_recommendations[:top_k]
        
        print(f"🔄 결합 완료: {len(final_recommendations)}개 최종 추천")
        print(f"  - 상품 데이터 기반: {len(product_recommendations)}개")
        print(f"  - 리뷰 데이터 기반: {len(review_recommendations)}개")
        print(f"  - 중복 제거 후: {len(unique_recommendations)}개")
        
        return final_recommendations


def main():
    """추천 에이전트 테스트"""
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
        'tags': [
            ['베이직', '오버핏'],
            ['스트릿', '그래픽'],
            ['베이직', '무지', '꾸안꾸'],
            ['트렌디', '로고'],
            ['빈티지', '체크']
        ],
        'rating': [4.8, 4.6, 4.9, 4.7, 4.5],
        'review_count': [1500, 800, 2200, 1200, 600],
        'description': [
            '베이직 오버핏 티셔츠 블랙',
            '스트릿 그래픽 반팔 화이트',
            '꾸안꾸 무지 티셔츠 그레이',
            '트렌디 로고 반팔 네이비',
            '빈티지 체크 셔츠 베이지'
        ]
    }
    
    df = pd.DataFrame(sample_data)
    agent = RecommendationAgent(df)
    
    # 테스트 요청
    user_request = {
        'original_query': '스트릿한 무드의 상의 추천해줘',
        'filters': {
            'categories': '상의',
            'tags': '스트릿'
        },
        'user_preferences': {
            'tags': ['스트릿'],
            'categories': ['상의']
        }
    }
    
    recommendations = agent.recommend_products(user_request, top_k=3)
    
    print("추천 결과:")
    for i, rec in enumerate(recommendations, 1):
        print(f"\n{i}. {rec.product_name}")
        print(f"   평점: {rec.rating}, 리뷰: {rec.review_count}")
        print(f"   추천 이유: {rec.recommendation_reason}")


if __name__ == "__main__":
    main() 