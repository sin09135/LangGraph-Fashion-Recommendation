#%%
import os
import time
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from typing import Optional, Union
import pandas as pd

#%%
# 저장 폴더
SAVE_DIR = "./musinsa_images"
os.makedirs(SAVE_DIR, exist_ok=True)

# 목표 개수 (카테고리별)
TARGET_COUNT = 200
SCROLL_PAUSE_TIME = 1.5

# 카테고리 정보
categories = {
    "상의" : "001",
    "가방": "004",
    "아우터": "002", 
    "바지": "003",
    "패션소품": "101",
    "스포츠/레저": "017",
    "신발": "103"
}

sex = "gf=M"
sort = "sortCode=SALE_ONE_WEEK_COUNT"

def crawl_category(category_name: str, category_code: str, driver: webdriver.Chrome) -> list:
    """특정 카테고리를 크롤링하는 함수"""
    print(f"\n🔄 {category_name} 카테고리 크롤링 시작...")
    
    # URL 생성
    url = f"https://www.musinsa.com/category/{category_code}?{sex}&{sort}"
    driver.get(url)
    time.sleep(3)
    
    # 스크롤을 반복해서 상품이 로딩될 때까지 기다림
    last_height = driver.execute_script("return document.body.scrollHeight")
    retries = 0
    
    while True:
        # 스크롤 최하단으로 이동
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(SCROLL_PAUSE_TIME)
        
        # 새 높이 확인
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            retries += 1
            if retries >= 3:
                break
        else:
            retries = 0
            last_height = new_height
        
        # 현재 상품 개수 확인
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        items = soup.select('a.gtm-view-item-list')
        if len(items) >= TARGET_COUNT:
            break
    
    print(f"[INFO] {category_name} 카테고리에서 {len(items)}개의 상품이 로딩되었습니다.")
    
    # 파싱 시작
    data = []
    collected = 0
    
    for idx, item in enumerate(items):
        if collected >= TARGET_COUNT:
            break
            
        try:
            img_tag = item.find('img')
            if not img_tag:
                continue
                
            # src 속성 안전하게 접근
            image_url = img_tag.get('src', '')
            if not image_url:
                continue
                
            # urlparse에 문자열 전달
            parsed_url = urlparse(str(image_url))
            image_name = f"{category_name}_{collected+1:03d}_{os.path.basename(parsed_url.path)}"
            image_path = os.path.join(SAVE_DIR, image_name)
            
            # 이미지 저장
            response = requests.get(str(image_url), stream=True)
            if response.status_code == 200:
                with open(image_path, 'wb') as f:
                    for chunk in response.iter_content(1024):
                        f.write(chunk)
            
            product = {
                "category": category_name,
                "category_code": category_code,
                "product_id": item.get('data-item-id'),
                "brand_en": item.get('data-item-brand'),
                "brand_kr": item.get('data-brand-id'),
                "price": safe_int(item.get('data-price', 0)),
                "original_price": safe_int(item.get('data-original-price', 0)),
                "discount_rate": safe_int(item.get('data-discount-rate', 0)),
                "product_url": item.get('href'),
                "image_url": image_url,
                "image_path": image_path,
                "product_name": img_tag.get('alt', '')
            }
            data.append(product)
            collected += 1
        except Exception as e:
            print(f"에러 발생: {e}")
    
    print(f"✅ {category_name} 카테고리에서 {len(data)}개 상품 수집 완료")
    return data

def safe_int(value: Union[str, list, int, None]) -> int:
    """안전하게 정수로 변환하는 함수"""
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return 0
    return 0

# Selenium 드라이버 시작
driver = webdriver.Chrome()

# 모든 카테고리 크롤링
all_data = []
for category_name, category_code in categories.items():
    try:
        category_data = crawl_category(category_name, category_code, driver)
        all_data.extend(category_data)
        print(f"📊 {category_name}: {len(category_data)}개 상품 수집 완료")
    except Exception as e:
        print(f"❌ {category_name} 카테고리 크롤링 실패: {e}")

driver.quit()

# 결과 확인
print(f"\n🎉 전체 수집 완료!")
print(f"📈 총 수집된 상품 수: {len(all_data)}개")

# 카테고리별 통계
df_temp = pd.DataFrame(all_data)
category_stats = df_temp['category'].value_counts()
print(f"\n📋 카테고리별 수집 현황:")
for category, count in category_stats.items():
    print(f"   - {category}: {count}개")

# DataFrame으로 변환하고 CSV 파일로 저장
df = pd.DataFrame(all_data)
csv_filename = "musinsa_products_all_categories.csv"
df.to_csv(csv_filename, index=False, encoding='utf-8-sig')
print(f"\n📊 데이터가 '{csv_filename}' 파일로 저장되었습니다.")
print(f"📋 DataFrame 정보:")
print(f"   - 행 수: {len(df)}")
print(f"   - 열 수: {len(df.columns)}")
print(f"   - 열 이름: {list(df.columns)}")
print(f"\n📈 데이터 미리보기:")
print(df.head())
