import requests
from bs4 import BeautifulSoup
import json
import random
import time
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import re
import os

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 Safari/605.1.15',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/88.0.4324.96 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.116 Safari/537.36',
]

def setup_driver():
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--window-size=1920,1080')
    user_agent = random.choice(USER_AGENTS)
    chrome_options.add_argument(f'--user-agent={user_agent}')
    driver = webdriver.Chrome(options=chrome_options)
    return driver

def extract_product_info(driver, url):
    """상품 정보 추출"""
    try:
        print(f"🔍 {url} 처리 중...")
        
        # 페이지 로드
        driver.get(url)
        time.sleep(random.uniform(2, 4))
        
        # BeautifulSoup으로 파싱
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # 둘러싼 div 구조에서 기본 정보 수집 (참고용)
        print("🔍 둘러싼 div 구조에서 정보 수집 중...")
        main_div = soup.select_one('#root > div:nth-of-type(1) > div:nth-of-type(2) > div')
        
        if main_div:
            all_text = main_div.get_text(strip=True)
            print(f"📝 수집된 전체 텍스트: {all_text[:200]}...")
        else:
            print("❌ 둘러싼 div를 찾을 수 없습니다")
        
        # 상품명 추출
        print("🔍 상품명 추출 중...")
        product_name = extract_product_name(driver)
        print(f"✅ 상품명 추출: {product_name}")
        
        # 카테고리 추출
        print("🔍 카테고리 추출 중...")
        categories = extract_categories(driver)
        print(f"✅ 카테고리 추출: {categories}")
        
        # 연관태그 추출
        print("🔍 연관태그 추출 중...")
        tags = extract_tags(driver)
        print(f"✅ 해시태그 추출: {tags}")
        
        # 사이즈 정보 추출
        print("🔍 사이즈 정보 추출 중...")
        size_info = extract_size_info(driver)
        print(f"✅ 사이즈 정보 추출: {len(size_info)}개 항목")
        
        # 핏/계절감 정보 추출
        print("🔍 핏/계절감 정보 추출 중...")
        fit_season_info = extract_fit_season_info(driver)
        print(f"✅ 핏/계절감 정보 추출: {len(fit_season_info)}개 항목")
        
        # 후기 정보 추출
        print("🔍 후기 정보 추출 중...")
        review_info = extract_review_info(driver)
        print(f"✅ 후기 정보 추출: 평점 {review_info.get('rating', 'N/A')}, 개수 {review_info.get('count', 'N/A')}")
        
        print("✅ 상품 정보 추출 완료!")
        
        return {
            'url': url,
            'product_name': product_name,
            'categories': categories,
            'tags': tags,
            'size_info': size_info,
            'fit_season_info': fit_season_info,
            'review_info': review_info
        }
        
    except Exception as e:
        print(f"❌ 오류 발생: {str(e)}")
        return {
            'url': url,
            'product_name': '추출 실패',
            'categories': [],
            'tags': [],
            'size_info': {},
            'fit_season_info': {},
            'review_info': {},
            'error': str(e)
        }

def extract_product_name(driver):
    """상품명 추출"""
    try:
        name_selectors = [
            "//div[contains(@class, 'sc-1omefes-0')]//span",
            "//*[@id='root']/div[1]/div[2]/div/div[3]/span",
            "//*[@id='root']/div[1]/div[2]/div/div[4]/span"
        ]
        for selector in name_selectors:
            try:
                element = driver.find_element(By.XPATH, selector)
                name = element.text.strip()
                if name and len(name) > 2:
                    return name
            except:
                continue
        return "상품명 추출 실패"
    except:
        return "상품명 추출 실패"

def extract_categories(driver):
    """카테고리 추출"""
    try:
        category_selectors = [
            "//div[contains(@class, 'sc-1prswe3-1')]//a",
            "//*[@id='root']/div[1]/div[2]/div/div[2]/span[2]/a",
            "//*[@id='root']/div[1]/div[2]/div/div[2]/span[3]/a",
            "//*[@id='root']/div[1]/div[2]/div/div[3]/span[2]/a",
            "//*[@id='root']/div[1]/div[2]/div/div[3]/span[3]/a"
        ]
        categories = []
        for selector in category_selectors:
            try:
                elements = driver.find_elements(By.XPATH, selector)
                for element in elements:
                    category = element.text.strip()
                    if category and category not in categories:
                        categories.append(category)
            except:
                continue
        return categories
    except:
        return []

def extract_tags(driver):
    """연관태그 추출"""
    try:
        tag_selectors = [
            "//div[contains(@class, 'sc-1eb70kd-0')]",
            "//*[@id='root']/div[1]/div[2]/div/div[16]/ul",
            "//*[@id='root']/div[1]/div[2]/div/div[18]/ul"
        ]
        for selector in tag_selectors:
            try:
                element = driver.find_element(By.XPATH, selector)
                tag_text = element.text
                print(f"✅ 연관태그 텍스트: {tag_text[:100]}...")
                tags = []
                if '#' in tag_text:
                    words = tag_text.split()
                    for word in words:
                        if word.startswith('#'):
                            tags.append(word)
                return tags
            except:
                continue
        return []
    except:
        return []

def extract_size_info(driver):
    """사이즈 정보 추출"""
    try:
        size_button_selectors = [
            "//button[@data-button-name='사이즈탭클릭']",
            "//*[@id='root']/div[1]/div[1]/div[2]/div/button[2]"
        ]
        for selector in size_button_selectors:
            try:
                size_button = driver.find_element(By.XPATH, selector)
                driver.execute_script("arguments[0].click();", size_button)
                time.sleep(2)
                break
            except:
                continue
        size_data = {}
        try:
            table_selectors = [
                "//table[contains(@class, 'sc-1jg999i-9')]",
                "//*[@id='root']/div[1]/div[1]/div[4]/div/div[2]/div/table",
                "//*[@id='root']/div[1]/div[1]/div[4]/div/div[2]/div[2]/div/table"
            ]
            for selector in table_selectors:
                try:
                    table = driver.find_element(By.XPATH, selector)
                    rows = table.find_elements(By.TAG_NAME, "tr")
                    if len(rows) > 1:
                        headers = []
                        header_cells = rows[0].find_elements(By.TAG_NAME, "th")
                        for cell in header_cells:
                            headers.append(cell.text.strip())
                        size_data['headers'] = headers
                        size_data['rows'] = []
                        for row in rows[1:]:
                            cells = row.find_elements(By.TAG_NAME, "td")
                            row_data = []
                            for cell in cells:
                                row_data.append(cell.text.strip())
                            if row_data:
                                size_data['rows'].append(row_data)
                        break
                except:
                    continue
        except Exception as e:
            size_data['error'] = str(e)
        return size_data
    except Exception as e:
        return {'error': str(e)}

def extract_fit_season_info(driver):
    """핏/계절감 정보 추출"""
    try:
        fit_data = {}
        try:
            # 핏/계절감 div 찾기
            fit_selectors = [
                "//div[contains(@class, 'sc-36xiah-2')]",
                "//div[contains(@class, 'fvqqbN')]"
            ]
            fit_div = None
            for selector in fit_selectors:
                try:
                    fit_div = driver.find_element(By.XPATH, selector)
                    break
                except:
                    continue
            
            if fit_div:
                # 헤더 추출 (핏, 촉감, 신축성, 비침, 두께, 계절)
                header_selectors = [
                    ".//ul[contains(@class, 'sc-36xiah-3')]//li",
                    ".//ul[contains(@class, 'iZBEnN')]//li"
                ]
                headers = []
                for selector in header_selectors:
                    try:
                        header_elements = fit_div.find_elements(By.XPATH, selector)
                        for element in header_elements:
                            header_text = element.text.strip()
                            if header_text:
                                headers.append(header_text)
                        if headers:
                            break
                    except:
                        continue
                fit_data['headers'] = headers
                
                # 테이블 데이터 추출
                table_selectors = [
                    ".//table[contains(@class, 'sc-36xiah-6')]",
                    ".//table[contains(@class, 'jizuRz')]"
                ]
                for selector in table_selectors:
                    try:
                        table = fit_div.find_element(By.XPATH, selector)
                        rows = table.find_elements(By.TAG_NAME, "tr")
                        fit_data['rows'] = []
                        for row in rows:
                            cells = row.find_elements(By.TAG_NAME, "td")
                            row_data = []
                            for cell in cells:
                                cell_text = cell.text.strip()
                                if cell_text:
                                    # 강조된 셀(eviTcu 클래스)은 선택된 값
                                    if "eviTcu" in cell.get_attribute("class"):
                                        row_data.append(f"✓ {cell_text}")
                                    else:
                                        row_data.append(cell_text)
                            if row_data:
                                fit_data['rows'].append(row_data)
                        break
                    except:
                        continue
            else:
                fit_data['error'] = "핏/계절감 정보를 찾을 수 없습니다"
        except Exception as e:
            fit_data['error'] = str(e)
        return fit_data
    except Exception as e:
        return {'error': str(e)}

def extract_review_info(driver):
    """후기 정보 추출"""
    try:
        review_button_selectors = [
            "//button[@data-button-name='스냅·후기탭클릭']",
            "//*[@id='root']/div[1]/div[1]/div[2]/div/button[4]"
        ]
        for selector in review_button_selectors:
            try:
                review_button = driver.find_element(By.XPATH, selector)
                driver.execute_script("arguments[0].click();", review_button)
                time.sleep(2)
                break
            except:
                continue
        review_data = {}
        try:
            rating_selectors = [
                "//div[contains(@class, 'GoodsReviewTitleSection__TitleContainer')]",
                "//*[@id='root']/div[1]/div[1]/div[6]/div[2]/div/div/div[4]/div[7]/div[1]/div[3]/div[3]/div/div[2]"
            ]
            for selector in rating_selectors:
                try:
                    rating_element = driver.find_element(By.XPATH, selector)
                    rating_text = rating_element.text
                    rating_match = re.search(r'(\d+\.\d+)', rating_text)
                    if rating_match:
                        review_data['rating'] = rating_match.group(1)
                    count_match = re.search(r'\((\d+(?:,\d+)*)\)', rating_text)
                    if count_match:
                        count_str = count_match.group(1).replace(',', '')
                        review_data['count'] = int(count_str)
                    break
                except:
                    continue
        except Exception as e:
            review_data['rating_error'] = str(e)
        try:
            review_selectors = [
                "//div[contains(@class, 'GoodsReviewStaticList__Container')]//div[contains(@class, 'review-list-item__Container')]",
                "//*[@id='root']/div[1]/div[1]/div[6]/div[2]/div/div/div[4]/div[7]/div"
            ]
            reviews = []
            for selector in review_selectors:
                try:
                    review_elements = driver.find_elements(By.XPATH, selector)
                    for i, element in enumerate(review_elements[:5]):
                        try:
                            review_info = {'index': i + 1}
                            content_selectors = [
                                ".//span[contains(@class, 'text-body_13px_reg') and contains(@class, 'text-black')]",
                                ".//div[contains(@class, 'ExpandableContent__ContentContainer')]//span[contains(@class, 'text-body_13px_reg')]",
                                ".//div[contains(@class, 'ExpandableContent__ContentContainer')]//span"
                            ]
                            content = ""
                            for content_selector in content_selectors:
                                try:
                                    content_elements = element.find_elements(By.XPATH, content_selector)
                                    for content_element in content_elements:
                                        text = content_element.text.strip()
                                        if text and len(text) > 10:
                                            content = text
                                            break
                                    if content:
                                        break
                                except:
                                    continue
                            if content:
                                review_info['content'] = content[:300] + "..." if len(content) > 300 else content
                            like_selectors = [
                                ".//div[contains(@class, 'LikeButton__Container')]//span[contains(@class, 'text-body_13px_reg')]",
                                ".//div[contains(@class, 'InteractionSection__Container')]//span[contains(@class, 'text-body_13px_reg')]"
                            ]
                            like_count = ""
                            for like_selector in like_selectors:
                                try:
                                    like_elements = element.find_elements(By.XPATH, like_selector)
                                    for like_element in like_elements:
                                        text = like_element.text.strip()
                                        if text.isdigit():
                                            like_count = text
                                            break
                                    if like_count:
                                        break
                                except:
                                    continue
                            if like_count:
                                review_info['likes'] = int(like_count)
                            else:
                                review_info['likes'] = 0
                            comment_selectors = [
                                ".//a[contains(@class, 'CommentButton__Container')]//span[contains(@class, 'text-body_13px_reg')]",
                                ".//div[contains(@class, 'InteractionSection__Container')]//a//span[contains(@class, 'text-body_13px_reg')]"
                            ]
                            comment_count = ""
                            for comment_selector in comment_selectors:
                                try:
                                    comment_elements = element.find_elements(By.XPATH, comment_selector)
                                    for comment_element in comment_elements:
                                        text = comment_element.text.strip()
                                        if text.isdigit():
                                            comment_count = text
                                            break
                                    if comment_count:
                                        break
                                except:
                                    continue
                            if comment_count:
                                review_info['comments'] = int(comment_count)
                            else:
                                review_info['comments'] = 0
                            user_selectors = [
                                ".//span[contains(@class, 'UserProfileSection__Nickname')]",
                                ".//div[contains(@class, 'UserProfileSection__Info')]//span[contains(@class, 'text-body_13px_med')]"
                            ]
                            user_name = ""
                            for user_selector in user_selectors:
                                try:
                                    user_element = element.find_element(By.XPATH, user_selector)
                                    user_name = user_element.text.strip()
                                    if user_name:
                                        break
                                except:
                                    continue
                            if user_name:
                                review_info['user'] = user_name
                            date_selectors = [
                                ".//span[contains(@class, 'UserProfileSection__PurchaseDate')]",
                                ".//span[contains(@class, 'text-body_13px_reg') and contains(@class, 'text-gray-500')]"
                            ]
                            review_date = ""
                            for date_selector in date_selectors:
                                try:
                                    date_elements = element.find_elements(By.XPATH, date_selector)
                                    for date_element in date_elements:
                                        text = date_element.text.strip()
                                        if re.match(r'\d{2}\.\d{2}\.\d{2}|\d{4}\.\d{2}\.\d{2}', text):
                                            review_date = text
                                            break
                                    if review_date:
                                        break
                                except:
                                    continue
                            if review_date:
                                review_info['date'] = review_date
                            purchase_selectors = [
                                ".//div[contains(@class, 'UserInfoGoodsOptionSection')]//span[contains(@class, 'text-body_13px_reg')]"
                            ]
                            purchase_info = ""
                            for purchase_selector in purchase_selectors:
                                try:
                                    purchase_elements = element.find_elements(By.XPATH, purchase_selector)
                                    for purchase_element in purchase_elements:
                                        text = purchase_element.text.strip()
                                        if "구매" in text or "·" in text:
                                            purchase_info = text
                                            break
                                    if purchase_info:
                                        break
                                except:
                                    continue
                            if purchase_info:
                                review_info['purchase_info'] = purchase_info
                            if review_info.get('content'):
                                reviews.append(review_info)
                        except Exception as e:
                            continue
                    if reviews:
                        break
                except:
                    continue
            review_data['reviews'] = reviews
        except Exception as e:
            review_data['reviews_error'] = str(e)
        return review_data
    except Exception as e:
        return {'error': str(e)}

def crawl_tops_details():
    """상의 카테고리 상품들의 상세 정보 크롤링"""
    
    # CSV 파일에서 상의 카테고리 URL들 추출
    df = pd.read_csv('musinsa_products_all_categories.csv')
    tops_df = df[df['category'] == '상의']
    all_tops_urls = tops_df['product_url'].tolist()
    
    print(f"📊 상의 카테고리 상품 수: {len(all_tops_urls)}개")
    
    # 체크포인트 파일 확인
    results = []
    processed_urls = set()
    failed_urls = set()
    
    if os.path.exists('tops_details_checkpoint.json'):
        try:
            with open('tops_details_checkpoint.json', 'r', encoding='utf-8') as f:
                results = json.load(f)
            
            # 성공한 URL과 실패한 URL 분리
            for item in results:
                if 'url' in item:
                    processed_urls.add(item['url'])
                    if item.get('product_name') == '추출 실패':
                        failed_urls.add(item['url'])
            
            print(f"📂 체크포인트 파일 발견: {len(results)}개 상품 이미 처리됨")
            print(f"❌ 실패한 URL: {len(failed_urls)}개")
        except Exception as e:
            print(f"⚠️ 체크포인트 파일 읽기 실패: {e}")
    
    # 처리할 URL들 (새로운 URL + 실패한 URL들)
    urls_to_process = []
    
    # 새로운 URL들 추가
    new_urls = [url for url in all_tops_urls if url not in processed_urls]
    urls_to_process.extend(new_urls)
    
    # 실패한 URL들 다시 추가
    urls_to_process.extend(list(failed_urls))
    
    print(f"🔄 처리할 상품: {len(urls_to_process)}개")
    print(f"  - 새로운 URL: {len(new_urls)}개")
    print(f"  - 재시도 URL: {len(failed_urls)}개")
    
    if not urls_to_process:
        print("✅ 모든 상품이 성공적으로 처리되었습니다!")
        return
    
    driver = setup_driver()
    successful_count = len([item for item in results if item.get('product_name') != '추출 실패'])
    failed_count = len([item for item in results if item.get('product_name') == '추출 실패'])
    
    try:
        for i, url in enumerate(urls_to_process, len(results) + 1):
            print(f"진행률: {i}/{len(urls_to_process)} - {url}")
            
            # 이미 처리된 URL인지 확인
            existing_result = None
            for result_item in results:
                if result_item.get('url') == url:
                    existing_result = result_item
                    break
            
            # 실패한 URL인 경우 기존 결과 제거
            if existing_result and existing_result.get('product_name') == '추출 실패':
                results.remove(existing_result)
                print(f"  🔄 실패한 URL 재시도: {url}")
            
            try:
                # 상품 정보 추출
                product_data = extract_product_info(driver, url)
                results.append(product_data)
                
                if product_data['product_name'] != "추출 실패":
                    successful_count += 1
                    print(f"  ✓ 성공: {product_data['product_name']}")
                else:
                    failed_count += 1
                    print(f"  ✗ 실패: 추출 실패")
                
                # 10개마다 중간 저장
                if i % 10 == 0:
                    with open('tops_details_checkpoint.json', 'w', encoding='utf-8') as f:
                        json.dump(results, f, ensure_ascii=False, indent=2)
                    print(f"  중간 저장 완료 ({i}개 처리)")
                
            except Exception as e:
                failed_count += 1
                print(f"  ✗ 오류: {e}")
                # 세션 오류인 경우 드라이버 재시작
                if "invalid session id" in str(e).lower():
                    print("  🔄 세션 오류 발생, 드라이버 재시작 중...")
                    driver.quit()
                    driver = setup_driver()
                
                results.append({
                    "url": url,
                    "product_name": "추출 실패",
                    "categories": [],
                    "tags": [],
                    "size_info": {},
                    "fit_season_info": {},
                    "review_info": {},
                    "error": str(e)
                })
            
            # 요청 간 랜덤 대기 (5-15초)
            if i < len(urls_to_process):
                wait_time = random.uniform(5, 15)
                print(f"  대기 중... ({wait_time:.1f}초)")
                time.sleep(wait_time)
    
    finally:
        driver.quit()
    
    # 최종 저장
    with open('tops_details_final.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"\n🎉 상의 상세 크롤링 완료!")
    print(f"성공: {successful_count}개")
    print(f"실패: {failed_count}개")
    print(f"총 처리: {len(all_tops_urls)}개")
    print(f"성공률: {successful_count/len(all_tops_urls)*100:.1f}%")
    
    # 성공한 데이터만 별도 저장
    successful_data = [item for item in results if item['product_name'] != '추출 실패']
    with open('tops_details_successful.json', 'w', encoding='utf-8') as f:
        json.dump(successful_data, f, ensure_ascii=False, indent=2)
    
    print(f"성공한 데이터 {len(successful_data)}개를 'tops_details_successful.json'에 저장했습니다.")

if __name__ == "__main__":
    crawl_tops_details() 