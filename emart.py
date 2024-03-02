import requests
from requests.exceptions import JSONDecodeError, RequestException
import time
import json

def check_stock_all_pages(sku_code, area_id, store_type, limit, xlog_key, referer):
    headers = {
        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_3_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Encoding': 'gzip, deflate, br',
        'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.8',
        'Content-Type': 'application/json',
        'Sec-Fetch-Site': 'same-origin',
        'Sec-Fetch-Mode': 'cors',
        'xlog_key': xlog_key,
        'xlog_location': 'store',
        'Sec-Fetch-Dest': 'empty',
        'Referer': referer,
    }
    
    base_url = 'https://eapp.emart.com/api/v1/search/item'
    all_items = []
    page = 1

    while True:
        params = {
            'skuCode': sku_code,
            'areaId': area_id,
            'storeType': store_type,
            'bookmarkYn': 'false',
            'statusOpenYn': 'false',
            'sortType': 'storeNm',
            #'sortType': 'distance',           # 거리순 정렬
            #'posX': '37.53382410969574',      # 검색할 위치의 위도
            #'posY': '126.93710803985596',      # 검색할 위치의 경도
            'page': page,
            'limit': limit
        }

        response = requests.get(base_url, headers=headers, params=params)
        try:
            data = response.json()
        except JSONDecodeError:
            break  # JSON 디코딩 실패 시 반복 중단

        detail_items = data.get('data', {}).get('detailItems', [])
        if not detail_items:
            break  # 상세 아이템이 없으면 종료

        all_items.extend(detail_items)
        page += 1  # 다음 페이지로
        time.sleep(1)  # 요청 사이에 1초 대기

    return all_items

# 결과 데이터 구조화
def structure_results(items, model):
    structured_data = []
    for item in items:
        structured_item = {
            "storeName": item["name"],
            "model": model,
            "stockStatus": item["stockStatus"]
        }
        structured_data.append(structured_item)
    return structured_data

# 512GB 모델 조회
sku_code_512gb = '0814585022285'
xlog_key_512gb = 'O244FmgT1ba9lBKGYZqqBlfurO4eotOfzbuGjWCEhHjGW/0pHneZfYSnuScagqiO|LoFKr0shdsjhQmkv55qHzg=='
referer_512gb = 'https://eapp.emart.com/webapp/product/stock?sku=0814585022285&searchKeyword=%EC%8A%A4%ED%8C%80%EB%8D%B1'
all_items_512gb = check_stock_all_pages(sku_code_512gb, 'Z', 'E', 10, xlog_key_512gb, referer_512gb)

# 1TB 모델 조회
sku_code_1tb = '0814585022339'
xlog_key_1tb = 'O244FmgT1ba9lBKGYZqqBlfurO4eotOfzbuGjWCEhHjGW/0pHneZfYSnuScagqiO|JBzYXoY2kDmqvn076BCDzQ=='
referer_1tb = 'https://eapp.emart.com/webapp/product/stock?sku=0814585022339&searchKeyword=%EC%8A%A4%ED%8C%80%EB%8D%B1'
all_items_1tb = check_stock_all_pages(sku_code_1tb, 'Z', 'E', 10, xlog_key_1tb, referer_1tb)

# 결과 출력
print("512GB Model:")
for item in all_items_512gb:
    print(item)

print("\n1TB Model:")
for item in all_items_1tb:
    print(item)

# 512GB 모델과 1TB 모델의 결과를 구조화
structured_data_512gb = structure_results(all_items_512gb, "512GB")
structured_data_1tb = structure_results(all_items_1tb, "1TB")

# 모든 결과를 하나의 리스트로 결합
combined_results = structured_data_512gb + structured_data_1tb

# JSON 파일로 저장
json_filename = "emart_stock_status.json"
with open(json_filename, "w", encoding="utf-8") as json_file:
    json.dump(combined_results, json_file, ensure_ascii=False, indent=4)

print(f"Data saved to {json_filename}")
