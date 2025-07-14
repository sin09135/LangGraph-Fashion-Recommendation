"""
간단한 벡터 DB 관리 모듈 (PyTorch 없이)
상품 임베딩을 FAISS에 저장하고 유사도 검색 수행
"""

import os
import json
import numpy as np
import pandas as pd
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path
import hashlib
import re
from src.agents.recommendation_agent import robust_style_keywords

try:
    import faiss
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False
    print("FAISS를 사용할 수 없습니다. pip install faiss-cpu를 실행하세요.")


@dataclass
class ProductEmbedding:
    """상품 임베딩 데이터 클래스"""
    product_id: str
    product_name: str
    embedding: np.ndarray
    metadata: Dict[str, Any]


class SimpleVectorDB:
    """간단한 벡터 DB 관리 클래스"""
    
    def __init__(self, 
                 db_path: str = "vector_db",
                 dimension: int = 128):
        self.db_path = Path(db_path)
        self.dimension = dimension
        
        # 디렉토리 생성
        self.db_path.mkdir(exist_ok=True)
        
        # FAISS 인덱스 초기화
        self.index = None
        self.product_ids = []
        self.metadata = []
        self._load_or_create_index()
    
    def _load_or_create_index(self):
        """FAISS 인덱스 로드 또는 생성"""
        if not FAISS_AVAILABLE:
            print("FAISS를 사용할 수 없어 기본 검색을 사용합니다.")
            return
        
        index_path = self.db_path / "faiss_index.bin"
        metadata_path = self.db_path / "metadata.json"
        
        if index_path.exists() and metadata_path.exists():
            # 기존 인덱스 로드
            try:
                self.index = faiss.read_index(str(index_path))
                with open(metadata_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.product_ids = data['product_ids']
                    self.metadata = data['metadata']
                print(f"기존 벡터 DB 로드 완료: {len(self.product_ids)}개 상품")
            except Exception as e:
                print(f"기존 인덱스 로드 실패: {e}")
                self._create_new_index()
        else:
            # 새 인덱스 생성
            self._create_new_index()
    
    def _create_new_index(self):
        """새 FAISS 인덱스 생성"""
        if not FAISS_AVAILABLE:
            return
        
        # 간단한 Flat 인덱스 생성
        self.index = faiss.IndexFlatIP(self.dimension)
        print("새 FAISS 인덱스 생성 완료")
    
    def _create_simple_embedding(self, text: str) -> np.ndarray:
        """간단한 텍스트 임베딩 생성 (해시 기반)"""
        # 텍스트를 정규화
        text = re.sub(r'[^\w\s가-힣]', ' ', text.lower())
        words = text.split()
        
        # 단어별 해시값 생성
        word_hashes = []
        for word in words:
            if word.strip():
                hash_val = int(hashlib.md5(word.encode()).hexdigest()[:8], 16)
                word_hashes.append(hash_val)
        
        # 벡터 생성 (고정 크기)
        embedding = np.zeros(self.dimension, dtype=np.float32)
        
        if word_hashes:
            # 해시값들을 벡터에 분산
            for i, hash_val in enumerate(word_hashes):
                idx = hash_val % self.dimension
                embedding[idx] += 1.0
            
            # 정규화
            norm = np.linalg.norm(embedding)
            if norm > 0:
                embedding = embedding / norm
        
        return embedding
    
    def create_product_embedding(self, product_data: Dict[str, Any]) -> Optional[ProductEmbedding]:
        """상품 데이터로부터 임베딩 생성 (robust_style_keywords 사용)"""
        try:
            description_parts = []
            if 'product_name' in product_data:
                description_parts.append(str(product_data['product_name']))
            if 'description' in product_data:
                description_parts.append(str(product_data['description']))
            # robust_style_keywords로 일관 처리
            style_keywords = robust_style_keywords(product_data)
            if isinstance(style_keywords, list):
                description_parts.extend(style_keywords)
            if 'tags' in product_data and isinstance(product_data['tags'], list):
                description_parts.extend(product_data['tags'])
            description = ' '.join(description_parts)
            embedding = self._create_simple_embedding(description)
            return ProductEmbedding(
                product_id=product_data.get('product_id', ''),
                product_name=product_data.get('product_name', ''),
                embedding=embedding,
                metadata=product_data
            )
        except Exception as e:
            print(f"임베딩 생성 실패: {e}")
            return None
    
    def add_products(self, products_df: pd.DataFrame):
        """상품들을 벡터 DB에 추가"""
        if not FAISS_AVAILABLE:
            print("FAISS를 사용할 수 없습니다.")
            return
        
        print("상품 임베딩 생성 중...")
        embeddings = []
        product_ids = []
        metadata_list = []
        
        for _, row in products_df.iterrows():
            product_data = row.to_dict()
            embedding = self.create_product_embedding(product_data)
            
            if embedding:
                embeddings.append(embedding.embedding)
                product_ids.append(embedding.product_id)
                metadata_list.append(embedding.metadata)
        
        if not embeddings:
            print("생성된 임베딩이 없습니다.")
            return
        
        # 임베딩을 numpy 배열로 변환
        embeddings_array = np.array(embeddings).astype('float32')
        
        # FAISS 인덱스에 추가
        self.index.add(embeddings_array)
        
        # 메타데이터 저장
        self.product_ids.extend(product_ids)
        self.metadata.extend(metadata_list)
        
        # 인덱스 저장
        self._save_index()
        
        print(f"벡터 DB에 {len(embeddings)}개 상품 추가 완료")
    
    def _save_index(self):
        """FAISS 인덱스와 메타데이터 저장"""
        if not FAISS_AVAILABLE:
            return
        
        try:
            # FAISS 인덱스 저장
            index_path = self.db_path / "faiss_index.bin"
            faiss.write_index(self.index, str(index_path))
            
            # 메타데이터 저장
            metadata_path = self.db_path / "metadata.json"
            metadata_data = {
                'product_ids': self.product_ids,
                'metadata': self.metadata
            }
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata_data, f, ensure_ascii=False, indent=2)
            
            print("벡터 DB 저장 완료")
            
        except Exception as e:
            print(f"벡터 DB 저장 실패: {e}")
    
    def search_similar_products(self, 
                              query: str, 
                              top_k: int = 10,
                              filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """유사한 상품 검색"""
        if not FAISS_AVAILABLE:
            return self._fallback_search(query, top_k, filters)
        
        try:
            # 쿼리 임베딩 생성
            query_embedding = self._create_simple_embedding(query).astype('float32').reshape(1, -1)
            
            # FAISS 검색
            scores, indices = self.index.search(query_embedding, min(top_k * 2, len(self.product_ids)))
            
            # 결과 처리
            results = []
            for score, idx in zip(scores[0], indices[0]):
                if idx == -1:  # FAISS에서 반환하는 무효 인덱스
                    continue
                
                product_metadata = self.metadata[idx]
                
                # 필터 적용
                if filters and not self._apply_filters(product_metadata, filters):
                    continue
                
                result = {
                    'product_id': self.product_ids[idx],
                    'product_name': product_metadata.get('product_name', ''),
                    'similarity_score': float(score),
                    'metadata': product_metadata
                }
                results.append(result)
                
                if len(results) >= top_k:
                    break
            
            return results
            
        except Exception as e:
            print(f"벡터 검색 실패: {e}")
            return self._fallback_search(query, top_k, filters)
    
    def _apply_filters(self, metadata: Dict[str, Any], filters: Dict[str, Any]) -> bool:
        """메타데이터에 필터 적용"""
        for key, value in filters.items():
            if key == 'category':
                if value not in str(metadata.get('category', '')):
                    return False
            elif key == 'style':
                style_keywords = metadata.get('style_keywords', [])
                if value not in style_keywords:
                    return False
            elif key == 'price_range':
                # 가격대 필터링 로직 (실제 구현 필요)
                pass
            elif key == 'color':
                if value not in str(metadata.get('description', '')):
                    return False
        
        return True
    
    def _fallback_search(self, query: str, top_k: int, filters: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """벡터 DB 사용 불가 시 기본 검색 (robust_style_keywords 사용)"""
        results = []
        query_lower = query.lower()
        for i, metadata in enumerate(self.metadata):
            score = 0
            product_name = metadata.get('product_name', '').lower()
            description = metadata.get('description', '').lower()
            style_keywords = [kw.lower() for kw in robust_style_keywords(metadata)]
            if any(word in product_name for word in query_lower.split()):
                score += 2
            if any(word in description for word in query_lower.split()):
                score += 1
            if any(word in style_keywords for word in query_lower.split()):
                score += 1.5
            if score > 0:
                result = {
                    'product_id': self.product_ids[i],
                    'product_name': metadata.get('product_name', ''),
                    'similarity_score': score,
                    'metadata': metadata
                }
                results.append(result)
        results.sort(key=lambda x: x['similarity_score'], reverse=True)
        if filters:
            results = [r for r in results if self._apply_filters(r['metadata'], filters)]
        return results[:top_k]
    
    def get_product_by_id(self, product_id: str) -> Optional[Dict[str, Any]]:
        """상품 ID로 상품 정보 조회"""
        try:
            idx = self.product_ids.index(product_id)
            return self.metadata[idx]
        except ValueError:
            return None
    
    def get_statistics(self) -> Dict[str, Any]:
        """벡터 DB 통계 정보"""
        return {
            'total_products': len(self.product_ids),
            'index_size': self.index.ntotal if self.index else 0,
            'dimension': self.dimension,
            'faiss_available': FAISS_AVAILABLE
        }


def main():
    """간단한 벡터 DB 테스트"""
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
        'description': [
            '베이직 오버핏 티셔츠 블랙',
            '스트릿 그래픽 반팔 화이트',
            '꾸안꾸 무지 티셔츠 그레이',
            '트렌디 로고 반팔 네이비',
            '빈티지 체크 셔츠 베이지'
        ],
        'style_keywords': [
            ['베이직', '오버핏'],
            ['스트릿', '그래픽'],
            ['베이직', '무지', '꾸안꾸'],
            ['트렌디', '로고'],
            ['빈티지', '체크']
        ],
        'rating': [4.8, 4.6, 4.9, 4.7, 4.5],
        'review_count': [1500, 800, 2200, 1200, 600]
    }
    
    df = pd.DataFrame(sample_data)
    
    # 벡터 DB 매니저 초기화
    vector_db = SimpleVectorDB()
    
    # 상품 추가
    vector_db.add_products(df)
    
    # 검색 테스트
    test_queries = [
        "꾸안꾸 느낌 나는 반팔",
        "스트릿한 무드의 티셔츠",
        "베이직한 오버핏 상의"
    ]
    
    for query in test_queries:
        print(f"\n검색 쿼리: {query}")
        results = vector_db.search_similar_products(query, top_k=3)
        
        for i, result in enumerate(results, 1):
            print(f"{i}. {result['product_name']} (유사도: {result['similarity_score']:.3f})")
    
    # 통계 정보
    stats = vector_db.get_statistics()
    print(f"\n벡터 DB 통계: {stats}")


if __name__ == "__main__":
    main() 