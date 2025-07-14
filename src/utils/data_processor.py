"""
데이터 처리 및 전처리 유틸리티
무신사 상품 데이터를 LLM 추천 시스템에 맞게 처리
"""

import pandas as pd
import numpy as np
import json
import re
from typing import List, Dict, Any, Optional
from pathlib import Path
from src.agents.recommendation_agent import robust_style_keywords


class MusinsaDataProcessor:
    """무신사 데이터 처리 클래스"""
    
    def __init__(self, data_dir: str = "../data"):
        self.data_dir = Path(data_dir)
        self.products_df = None
        self.reviews_data = None
        
    def load_data(self) -> Dict[str, pd.DataFrame]:
        """데이터 파일들을 로드"""
        data = {}
        
        # 병합된 완전한 데이터 파일 우선 로드
        merged_complete_path = self.data_dir / "merged_complete_products.json"
        if merged_complete_path.exists():
            with open(merged_complete_path, 'r', encoding='utf-8') as f:
                merged_data = json.load(f)
            data['products'] = pd.DataFrame(merged_data)
            print(f"병합된 완전한 데이터 로드: {len(data['products'])}개 상품")
            return data
        
        # 기존 데이터 파일들 로드 (백업)
        # 성공 데이터 로드
        successful_path = self.data_dir / "merged_successful_data.csv"
        if successful_path.exists():
            data['successful'] = pd.read_csv(successful_path)
            print(f"성공 데이터 로드: {len(data['successful'])}개 상품")
            
        # 실패 데이터 로드
        failed_path = self.data_dir / "merged_failed_data.json"
        if failed_path.exists():
            with open(failed_path, 'r', encoding='utf-8') as f:
                data['failed'] = pd.DataFrame(json.load(f))
            print(f"실패 데이터 로드: {len(data['failed'])}개 상품")
            
        # 전체 상품 데이터 로드
        products_path = self.data_dir / "musinsa_products_all_categories.csv"
        if products_path.exists():
            data['products'] = pd.read_csv(products_path)
            print(f"전체 상품 데이터 로드: {len(data['products'])}개 상품")
            
        return data
    
    def preprocess_products(self, df: pd.DataFrame) -> pd.DataFrame:
        """상품 데이터 전처리"""
        processed_df = df.copy()
        
        # 태그 정제
        if 'tags' in processed_df.columns:
            processed_df['tags'] = processed_df['tags'].apply(self._clean_tags)
            
        # 카테고리 정제
        if 'categories' in processed_df.columns:
            processed_df['categories'] = processed_df['categories'].apply(self._clean_categories)
            
        # 상품명 정제
        if 'product_name' in processed_df.columns:
            processed_df['product_name'] = processed_df['product_name'].apply(self._clean_product_name)
            
        # 평점 및 리뷰 수 처리
        if 'rating' in processed_df.columns:
            processed_df['rating'] = pd.to_numeric(processed_df['rating'], errors='coerce')
            
        if 'review_count' in processed_df.columns:
            processed_df['review_count'] = pd.to_numeric(processed_df['review_count'], errors='coerce')
            
        return processed_df
    
    def _clean_tags(self, tags_input) -> List[str]:
        """태그 문자열을 정제하여 리스트로 변환"""
        try:
            # pandas Series나 numpy array인 경우
            if hasattr(tags_input, '__iter__') and not isinstance(tags_input, (str, list)):
                if len(tags_input) == 0:
                    return []
                tags_input = tags_input[0] if len(tags_input) == 1 else list(tags_input)
            
            # None이나 NaN 체크
            if tags_input is None or (hasattr(tags_input, '__bool__') and not tags_input):
                return []
            
            # 빈 문자열 체크
            if isinstance(tags_input, str) and tags_input.strip() == '':
                return []
            
            # 이미 리스트인 경우
            if isinstance(tags_input, list):
                return [str(tag).strip() for tag in tags_input if tag and str(tag).strip()]
            
            # 문자열인 경우
            if isinstance(tags_input, str):
                # 해시태그 제거 및 쉼표로 분리
                tags = re.sub(r'#', '', tags_input)
                tags = [tag.strip() for tag in tags.split(',') if tag.strip()]
                return tags
            
            return []
        except Exception:
            return []
    
    def _clean_categories(self, category_input) -> str:
        """카테고리 문자열 정제 (리스트/배열/시리즈/None/NaN/빈 문자열 모두 안전하게 처리)"""
        import numpy as np
        import pandas as pd
        # None 또는 NaN
        if category_input is None:
            return ''
        if isinstance(category_input, (list, tuple)):
            if not category_input:
                return ''
            return str(category_input[0]).strip()
        if isinstance(category_input, set):
            category_input = list(category_input)
            if not category_input:
                return ''
            return str(category_input[0]).strip()
        if hasattr(category_input, 'iloc') or hasattr(category_input, 'values'):
            # pandas Series 또는 numpy array
            arr = category_input.values if hasattr(category_input, 'values') else category_input
            if len(arr) == 0:
                return ''
            return str(arr[0]).strip()
        try:
            if pd.isna(category_input):
                return ''
        except Exception:
            pass
        if isinstance(category_input, str):
            return category_input.strip()
        return str(category_input).strip()
    
    def _clean_product_name(self, name: str) -> str:
        """상품명 정제"""
        if pd.isna(name):
            return ''
        # 특수문자 및 불필요한 공백 제거
        name = re.sub(r'[^\w\s가-힣]', ' ', name)
        name = re.sub(r'\s+', ' ', name).strip()
        return name
    
    def extract_style_keywords(self, df: pd.DataFrame) -> pd.DataFrame:
        """스타일 키워드 추출 (robust_style_keywords 사용)"""
        style_keywords = []
        for _, row in df.iterrows():
            keywords = []
            # 태그에서 스타일 키워드 추출
            if 'tags' in row and isinstance(row['tags'], list):
                for tag in row['tags']:
                    if self._is_style_keyword(tag):
                        keywords.append(tag)
            # 상품명에서 스타일 키워드 추출
            if 'product_name' in row:
                product_name = row['product_name']
                if not isinstance(product_name, str):
                    product_name = str(product_name)
                name_keywords = self._extract_style_from_name(product_name)
                keywords.extend(name_keywords)
            # robust_style_keywords로 일관 처리
            robusted = robust_style_keywords(row)
            keywords.extend([k for k in robusted if k not in keywords])
            style_keywords.append(list(set(keywords)))
        df['style_keywords'] = style_keywords
        return df
    
    def _is_style_keyword(self, keyword: str) -> bool:
        """스타일 키워드인지 판단"""
        style_patterns = [
            '오버핏', '루즈핏', '슬림핏', '머슬핏', '레귤러핏',
            '스트릿', '캐주얼', '스포티', '힙합', '빈티지',
            '꾸안꾸', '힙한', '트렌디', '베이직', '심플',
            '그래픽', '로고', '무지', '체크', '스트라이프'
        ]
        
        return any(pattern in keyword for pattern in style_patterns)
    
    def _extract_style_from_name(self, name: str) -> List[str]:
        """상품명에서 스타일 키워드 추출"""
        keywords = []
        
        # 스타일 관련 키워드 패턴
        style_patterns = {
            '오버핏': ['오버핏', '오버사이즈', '빅사이즈'],
            '루즈핏': ['루즈핏', '루즈', '릴렉스드'],
            '슬림핏': ['슬림핏', '슬림', '타이트'],
            '머슬핏': ['머슬핏', '머슬'],
            '베이직': ['베이직', '베이식', '기본'],
            '그래픽': ['그래픽', '로고', '프린팅'],
            '무지': ['무지', '무지티'],
            '체크': ['체크', '체크무늬'],
            '스트라이프': ['스트라이프', '스트라이프무늬']
        }
        
        for style, patterns in style_patterns.items():
            if any(pattern in name for pattern in patterns):
                keywords.append(style)
                
        return keywords
    
    def create_product_embeddings_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """임베딩 생성을 위한 데이터 준비 (robust_style_keywords 사용)"""
        embedding_data = []
        for _, row in df.iterrows():
            description_parts = []
            if 'product_name' in row:
                product_name = row['product_name']
                if not isinstance(product_name, str):
                    product_name = str(product_name)
                description_parts.append(product_name)
            if 'tags' in row and isinstance(row['tags'], list):
                description_parts.extend(row['tags'])
            # robust_style_keywords로 일관 처리
            style_keywords = robust_style_keywords(row)
            if isinstance(style_keywords, list):
                description_parts.extend(style_keywords)
            if 'categories' in row:
                categories = row['categories']
                if isinstance(categories, list):
                    categories_str = ','.join([str(c) for c in categories])
                else:
                    categories_str = str(categories)
                description_parts.append(categories_str)
            length = None
            chest = None
            shoulder = None
            size_info = row.get('size_info', None)
            if isinstance(size_info, dict):
                headers = size_info.get('headers', [])
                rows = size_info.get('rows', [])
                if not isinstance(headers, list):
                    headers = list(headers) if headers is not None else []
                if not isinstance(rows, list):
                    rows = list(rows) if rows is not None else []
                if len(rows) > 1 and isinstance(rows[1], list):
                    size_row = rows[1]
                    if '총장' in headers:
                        idx = headers.index('총장')
                        try:
                            length = float(size_row[idx])
                        except Exception:
                            length = None
                    if '가슴단면' in headers:
                        idx = headers.index('가슴단면')
                        try:
                            chest = float(size_row[idx])
                        except Exception:
                            chest = None
                    if '어깨너비' in headers:
                        idx = headers.index('어깨너비')
                        try:
                            shoulder = float(size_row[idx])
                        except Exception:
                            shoulder = None
            brand = ''
            if 'categories' in row:
                categories = row['categories']
                if isinstance(categories, list) and len(categories) > 0:
                    brand = str(categories[-1])
                elif isinstance(categories, str):
                    import re
                    m = re.search(r'\((.*?)\)', categories)
                    if m:
                        brand = m.group(1)
            description = ' '.join(description_parts)
            embedding_data.append({
                'product_id': str(row.get('url', '')).split('/')[-1] if row.get('url', '') else '',
                'product_name': str(row.get('product_name', '')),
                'description': description,
                'category': categories_str if 'categories' in row else '',
                'tags': row.get('tags', []),
                'style_keywords': robust_style_keywords(row),
                'rating': row.get('rating', 0),
                'review_count': row.get('review_count', 0),
                'url': str(row.get('url', '')),
                'image_url': str(row.get('image_path', '')),
                'length': length,
                'chest': chest,
                'shoulder': shoulder,
                'brand': brand
            })
        return pd.DataFrame(embedding_data)
    
    def filter_by_category(self, df: pd.DataFrame, category: str) -> pd.DataFrame:
        """카테고리별 필터링"""
        if 'categories' not in df.columns:
            return pd.DataFrame(df) if not isinstance(df, pd.DataFrame) else df
        result = df[df['categories'].str.contains(category, na=False)]
        return pd.DataFrame(result) if not isinstance(result, pd.DataFrame) else result
    
    def filter_by_rating(self, df: pd.DataFrame, min_rating: float = 4.0) -> pd.DataFrame:
        """평점 기준 필터링"""
        if 'rating' not in df.columns:
            return pd.DataFrame(df) if not isinstance(df, pd.DataFrame) else df
        result = df[df['rating'] >= min_rating]
        return pd.DataFrame(result) if not isinstance(result, pd.DataFrame) else result
    
    def get_trending_products(self, df: pd.DataFrame, top_n: int = 100) -> pd.DataFrame:
        """트렌딩 상품 추출 (평점 + 리뷰 수 기준)"""
        if 'rating' not in df.columns or 'review_count' not in df.columns:
            return df.head(top_n)
            
        # 평점과 리뷰 수를 종합한 점수 계산
        df['trend_score'] = df['rating'] * np.log1p(df['review_count'])
        
        return df.nlargest(top_n, 'trend_score')


def main():
    """데이터 처리 테스트"""
    processor = MusinsaDataProcessor()
    
    # 데이터 로드
    data = processor.load_data()
    
    if 'successful' in data:
        # 상품 데이터 전처리
        processed_df = processor.preprocess_products(data['successful'])
        
        # 스타일 키워드 추출
        processed_df = processor.extract_style_keywords(processed_df)
        
        # 임베딩 데이터 생성
        embedding_df = processor.create_product_embeddings_data(processed_df)
        
        print(f"처리된 상품 수: {len(embedding_df)}")
        print(f"스타일 키워드 예시: {embedding_df['style_keywords'].iloc[0]}")
        
        # 결과 저장
        embedding_df.to_csv('../data/processed_products.csv', index=False, encoding='utf-8')
        print("처리된 데이터가 저장되었습니다.")


if __name__ == "__main__":
    main() 