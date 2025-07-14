"""
무신사 상품 리뷰 크롤러
상품별 리뷰 텍스트를 수집하여 리뷰 기반 추천 시스템을 위한 데이터를 확보합니다.
"""

import requests
import pandas as pd
import time
import json
import re
from typing import List, Dict, Any
from urllib.parse import urlparse
import os


class MusinsaReviewCrawler:
    """무신사 리뷰 크롤러"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        self.base_url = "https://www.musinsa.com"
        
    def extract_product_id(self, url: str) -> str:
        """URL에서 상품 ID 추출"""
        match = re.search(r'/products/(\d+)', url)
        return match.group(1) if match else None
    
    def get_reviews(self, product_id: str, page: int = 1, limit: int = 20) -> List[Dict[str, Any]]:
        """상품의 리뷰 데이터 수집"""
        try:
            # 무신사 리뷰 API 엔드포인트 (실제 API 구조에 맞게 수정 필요)
            review_url = f"{self.base_url}/api/reviews/{product_id}"
            params = {
                'page': page,
                'limit': limit,
                'sort': 'newest'  # 최신순
            }
            
            response = self.session.get(review_url, params=params)
            response.raise_for_status()
            
            data = response.json()
            reviews = []
            
            # 실제 응답 구조에 맞게 파싱 (예시)
            if 'data' in data and 'reviews' in data['data']:
                for review in data['data']['reviews']:
                    reviews.append({
                        'product_id': product_id,
                        'review_id': review.get('id'),
                        'user_id': review.get('user_id'),
                        'rating': review.get('rating'),
                        'content': review.get('content', '').strip(),
                        'created_at': review.get('created_at'),
                        'helpful_count': review.get('helpful_count', 0),
                        'size_info': review.get('size_info'),
                        'color_info': review.get('color_info')
                    })
            
            return reviews
            
        except Exception as e:
            print(f"리뷰 수집 실패 (상품 ID: {product_id}, 페이지: {page}): {e}")
            return []
    
    def get_all_reviews(self, product_id: str, max_pages: int = 10) -> List[Dict[str, Any]]:
        """상품의 모든 리뷰 수집 (페이지네이션)"""
        all_reviews = []
        page = 1
        
        while page <= max_pages:
            reviews = self.get_reviews(product_id, page)
            if not reviews:
                break
                
            all_reviews.extend(reviews)
            page += 1
            
            # 요청 간격 조절
            time.sleep(1)
        
        return all_reviews
    
    def crawl_reviews_from_csv(self, csv_path: str, output_path: str, max_products: int = 50):
        """CSV 파일의 상품들에서 리뷰 수집"""
        try:
            # 상품 데이터 로드
            products_df = pd.read_csv(csv_path)
            print(f"총 {len(products_df)}개 상품 발견")
            
            all_reviews = []
            processed_count = 0
            
            for _, product in products_df.head(max_products).iterrows():
                product_id = self.extract_product_id(product['url'])
                if not product_id:
                    continue
                
                print(f"리뷰 수집 중... ({processed_count + 1}/{min(max_products, len(products_df))}) - {product['product_name']}")
                
                reviews = self.get_all_reviews(product_id)
                all_reviews.extend(reviews)
                
                processed_count += 1
                
                # 진행상황 저장
                if processed_count % 10 == 0:
                    self.save_reviews(all_reviews, f"{output_path}_temp.json")
            
            # 최종 저장
            self.save_reviews(all_reviews, output_path)
            print(f"리뷰 수집 완료! 총 {len(all_reviews)}개 리뷰 수집")
            
        except Exception as e:
            print(f"리뷰 수집 중 오류 발생: {e}")
    
    def save_reviews(self, reviews: List[Dict[str, Any]], filepath: str):
        """리뷰 데이터를 JSON 파일로 저장"""
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(reviews, f, ensure_ascii=False, indent=2)
            print(f"리뷰 데이터 저장 완료: {filepath}")
        except Exception as e:
            print(f"리뷰 데이터 저장 실패: {e}")
    
    def load_reviews(self, filepath: str) -> List[Dict[str, Any]]:
        """저장된 리뷰 데이터 로드"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"리뷰 데이터 로드 실패: {e}")
            return []
    
    def analyze_reviews(self, reviews: List[Dict[str, Any]]) -> Dict[str, Any]:
        """리뷰 데이터 분석"""
        if not reviews:
            return {}
        
        # 기본 통계
        total_reviews = len(reviews)
        avg_rating = sum(r.get('rating', 0) for r in reviews) / total_reviews
        
        # 리뷰 길이 분석
        review_lengths = [len(r.get('content', '')) for r in reviews]
        avg_length = sum(review_lengths) / len(review_lengths)
        
        # 키워드 분석 (간단한 버전)
        all_content = ' '.join([r.get('content', '') for r in reviews])
        words = re.findall(r'\w+', all_content.lower())
        word_freq = pd.Series(words).value_counts().head(20)
        
        return {
            'total_reviews': total_reviews,
            'avg_rating': avg_rating,
            'avg_review_length': avg_length,
            'top_keywords': word_freq.to_dict()
        }


def main():
    """메인 실행 함수"""
    crawler = MusinsaReviewCrawler()
    
    # 설정
    input_csv = "data/merged_successful_data.csv"
    output_json = "data/product_reviews.json"
    max_products = 20  # 테스트용으로 적은 수
    
    print("무신사 리뷰 크롤링 시작...")
    crawler.crawl_reviews_from_csv(input_csv, output_json, max_products)
    
    # 수집된 리뷰 분석
    reviews = crawler.load_reviews(output_json)
    if reviews:
        analysis = crawler.analyze_reviews(reviews)
        print("\n=== 리뷰 분석 결과 ===")
        print(f"총 리뷰 수: {analysis.get('total_reviews', 0)}")
        print(f"평균 평점: {analysis.get('avg_rating', 0):.2f}")
        print(f"평균 리뷰 길이: {analysis.get('avg_review_length', 0):.1f}자")
        print("\n상위 키워드:")
        for word, count in list(analysis.get('top_keywords', {}).items())[:10]:
            print(f"  {word}: {count}회")


if __name__ == "__main__":
    main() 