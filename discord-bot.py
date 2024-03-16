import discord
from discord.ext import commands,tasks
from discord.commands import Option
import asyncio
import aiohttp 
import logging
from logging.handlers import TimedRotatingFileHandler
from aiohttp import ClientSession, ClientError
import json
from bs4 import BeautifulSoup
import requests
from json.decoder import JSONDecodeError
from requests.exceptions import  RequestException
import time
import datetime
import os
from fake_useragent import UserAgent

# 로깅 설정
def setup_logging():
    if not os.path.exists('logs'):
        os.makedirs('logs')
    log_formatter = logging.Formatter('%(asctime)s %(levelname)s: %(message)s')
    log_file = 'logs/logs.log'

    log_handler = TimedRotatingFileHandler(log_file, when="D", interval=1, backupCount=3)
    log_handler.setFormatter(log_formatter)
    log_handler.setLevel(logging.INFO)

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logger.addHandler(log_handler)

    # 콘솔 로거 설정 (선택적)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(log_formatter)
    logger.addHandler(console_handler)

# 로그 설정 초기화
setup_logging()


@tasks.loop(hours=1)
async def cleanup_server_status():
    current_guild_ids = {str(guild.id) for guild in bot.guilds}
    logging.info(f"Current List: {current_guild_ids}")
    server_status = load_server_status()

    # server_status에서 현재 봇이 속해 있지 않은 서버 정보를 삭제
    removed_servers = [guild_id for guild_id in server_status if guild_id not in current_guild_ids]
    for guild_id in removed_servers:
        del server_status[guild_id]
        logging.info(f"Removed server status for guild ID {guild_id}")

    save_server_status(server_status)
    logging.info("Completed cleanup of server_status.json.")

# Discord 봇 토큰 및 기타 설정
DISCORD_BOT_TOKEN = "YOUR_DISCORD_BOT_TOKEN"
intents = discord.Intents.default()
intents.typing = False  # 타이핑 시작 이벤트를 받지 않음
intents.presences = False  # 유저의 상태 변경 이벤트를 받지 않음
bot = commands.Bot(command_prefix="?", intents=intents)

# 관리자의 USER_ID
author_user_id = YOUR_USERID

# 상품 페이지 URL 및 매핑 정보
url = "https://steamdeck.komodo.jp/?lang=ko"
product_mapping = {
    "variation-89372": "Steam Deck LCD 256GB",
    "variation-89365": "Steam Deck LCD 256GB",
    "variation-301136": "Steam Deck OLED 512GB",
    "variation-301131": "Steam Deck OLED 512GB",
    "variation-301137": "Steam Deck OLED 1TB",
    "variation-301132": "Steam Deck OLED 1TB"
}
# Komodo 상품 페이지 URL 및 매핑 정보
url = "https://steamdeck.komodo.jp/?lang=ko"
product_mapping = {
    "variation-89372": "Steam Deck LCD 256GB",
    "variation-89365": "Steam Deck LCD 256GB",
    "variation-301136": "Steam Deck OLED 512GB",
    "variation-301131": "Steam Deck OLED 512GB",
    "variation-301137": "Steam Deck OLED 1TB",
    "variation-301132": "Steam Deck OLED 1TB"
}

# xlog_key를 저장하고 관리하는 JSON 파일 이름
XLOG_KEYS_FILE = 'xlog_keys.json'

def load_xlog_keys():
    try:
        with open(XLOG_KEYS_FILE, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        return {}

def save_xlog_keys(xlog_keys):
    with open(XLOG_KEYS_FILE, 'w') as file:
        json.dump(xlog_keys, file, indent=4)

# 이마트 재고 확인을 위한 SKU 코드 및 기타 매개변수
sku_details = {
    '512GB': {
        'sku_code': '0814585022285',
        'area_id': 'Z', 
        'store_type': 'E', 
        'limit': 10,
        'referer': 'https://eapp.emart.com/webapp/product/stock?sku=0814585022285&searchKeyword=%EC%8A%A4%ED%8C%80%EB%8D%B1'
    },
    '1TB': {
        'sku_code': '0814585022339',
        'area_id': 'Z', 
        'store_type': 'E', 
        'limit': 10,
        'referer': 'https://eapp.emart.com/webapp/product/stock?sku=0814585022339&searchKeyword=%EC%8A%A4%ED%8C%80%EB%8D%B1'
    }
}


# 서버 상태 JSON 파일 관련 함수
def load_server_status():
    try:
        with open('server_status.json', 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        return {}

def save_server_status(server_status):
    with open('server_status.json', 'w') as file:
        json.dump(server_status, file, indent=4)

def load_previous_message(server_guid):
    server_status = load_server_status()
    return server_status.get(server_guid, {}).get('previous_message')

def save_previous_message(server_guid, message):
    update_server_status(server_guid, previous_message=message)

def save_to_emart_json(filename, data):
    current_time = datetime.datetime.now()
    with open(filename, "w", encoding="utf-8") as file:
        # 데이터와 함께 현재 시간의 타임스탬프를 저장합니다.
        data_to_save = {
            "timestamp": current_time.isoformat(),
            "data": data
        }
        json.dump(data_to_save, file, ensure_ascii=False, indent=4)

def load_emart_stock_status():
    try:
        with open('emart_stock_status.json', 'r', encoding='utf-8') as file:
            data = json.load(file)
            return data
    except FileNotFoundError:
        return None

def update_server_status(server_id, **kwargs):
    server_status = load_server_status()

    if server_id not in server_status:
        server_status[server_id] = {}

    # 모델 정보 업데이트
    if 'emart_model' in kwargs:
        server_status[server_id]['emart_model'] = kwargs['emart_model']

    # 기존 인수 처리
    for key in ['komodo_alarm_active', 'emart_alarm_active', 'last_channel_id', 'previous_message']:
        if key in kwargs and kwargs[key] is not None:
            server_status[server_id][key] = kwargs[key]

    # 기타 상태 업데이트
    for key, value in kwargs.items():
        if key in ['komodo_alarm_active', 'emart_alarm_active', 'last_channel_id', 'previous_message']:
            server_status[server_id][key] = value

    save_server_status(server_status)

@bot.slash_command(name="등록", description="xlog_key를 등록합니다. (Admin Only)")
async def register_xlog_key(ctx, key: Option(str, "xlog_key 값을 입력하세요 (Admin Only)", required=True)):
    # 특정 사용자 ID를 확인하여 기능 제한
    if ctx.author.id != author_user_id:
        await ctx.respond(":no_entry: **You Don't have Permission!!** :no_entry:")
        return
    
    xlog_keys = load_xlog_keys()
    xlog_keys['xlog_key'] = key
    save_xlog_keys(xlog_keys)
    await ctx.respond("xlog_key가 성공적으로 등록되었습니다.")

# 기존 코드에서 xlog_key 값을 사용할 때 이 함수를 호출하여 값을 가져옵니다.
def get_xlog_key():
    xlog_keys = load_xlog_keys()
    return xlog_keys.get('xlog_key', '')

@bot.slash_command(name="재고확인", description="재고를 확인합니다.")
async def check_availability_slash(ctx, 
                                   seller: Option(str, "판매처를 선택하세요", 
                                                  choices=["코모도", "이마트"], required=True)):

    server_guid = str(ctx.guild.id)
    channel_id = ctx.channel.id
    channel = bot.get_channel(channel_id)
    
    if seller == "코모도":
        # 코모도 재고 확인 함수 호출
        logging.info(f"서버 {server_guid}에서 Komodo 재고확인이 호출되었습니다.")
        result_message = await check_availability(server_guid, channel)
        await ctx.respond(f"코모도 재고:\n{result_message}")
    elif seller == "이마트":
        # 이마트 재고 확인 함수 호출 (비동기적으로 처리)
        logging.info(f"서버 {server_guid}에서 이마트 재고확인이 호출되었습니다.")
        await ctx.respond("이마트 재고 확인 요청이 처리되었습니다. 잠시 후 결과가 표시됩니다.")
        await check_availability_emart(ctx)

# 슬래시 명령어: 채널 설정
@bot.slash_command(name="채널", description="메시지를 수신할 채널을 설정합니다.")
async def set_channel_slash(ctx, 
                            channel_id: Option(int, "채널아이디", required=False)):
    server_guid = str(ctx.guild.id)
    
    # 사용자가 채널 ID를 입력하지 않았다면 현재 채널의 ID를 사용
    if channel_id is None:
        channel_id = ctx.channel.id

    update_server_status(server_guid, last_channel_id=channel_id)
    await ctx.respond(f"메시지를 수신할 채널이 {channel_id}로 설정되었습니다.")


# 명령어: 알람 관리
@bot.slash_command(name='코모도', description="30초마다 Komodo 사이트에서 재고를 확인하고, 변경사항이 발생하면 알림을 수신합니다.")
async def handle_alarm_command(ctx, 
                               mode: Option(str, "알림 모드를 선택하세요", 
                                            choices=["활성", "비활성"], required=True)):
    global check_availability_task_komodo
    server_guid = str(ctx.guild.id)
    
    try:
        if mode == '활성':
            update_server_status(server_guid, komodo_alarm_active=True, last_channel_id=ctx.channel.id)
            await ctx.respond("Komodo 재고 알람이 활성화되었습니다.")
            logging.info(f"서버 {server_guid}에서 Komodo 알람이 활성화되었습니다.")

            if any(status.get('komodo_alarm_active') for status in load_server_status().values()):
                await bot.change_presence(status=discord.Status.online, activity=discord.Game("재고 조회"))

            # 태스크가 이미 실행 중인지 확인하고, 실행 중이지 않으면 태스크 시작
            if check_availability_task_komodo is None or check_availability_task_komodo.done():
                check_availability_task_komodo = asyncio.create_task(check_availability_periodic_komodo())

        elif mode == '비활성': 
            update_server_status(server_guid, komodo_alarm_active=False)
            await ctx.respond("Komodo 재고 알람이 비활성화되었습니다.")
            logging.info(f"서버 {server_guid}에서 Komodo 알람이 비활성화되었습니다.")

    except Exception as e:
        error_message = f"에러 발생: {e}"
        logging.error(error_message)
        await ctx.respond(error_message)

@bot.slash_command(name='이마트', description="5분마다 이마트의 재고를 확인하고, 품절->재고있음 상태가 발생하면 알림을 수신합니다. (모델 미선택시, 기본 512GB 선택)")
async def handle_alarm_emart(ctx, mode: Option(str, "알림 모드를 선택하세요", 
                                               choices=["활성", "비활성"], required=True),
                                               model: Option(str, "모델을 선택하세요", choices=["512GB", "1TB"], required=False, default="512GB")):
    server_guid = str(ctx.guild.id)  # 서버 ID를 문자열로 변환
    global check_availability_task_emart
    try:
        if mode == '활성':
            # 이마트 알람을 활성화하는 로직
            update_server_status(server_guid, emart_alarm_active=True, emart_model=model, last_channel_id=ctx.channel.id)
            await ctx.respond(f"이마트 {model} 모델 재고 알람이 활성화되었습니다.")
            logging.info(f"서버 {server_guid}에서 이마트 알람이 활성화되었습니다.")

            if check_availability_task_emart is None or check_availability_task_emart.done():
                check_availability_task_emart = bot.loop.create_task(check_availability_periodic_emart())

        elif mode == '비활성':
            # 이마트 알람을 비활성화하는 로직
            update_server_status(server_guid, emart_alarm_active=False, emart_model=None)
            if check_availability_task_emart is not None:
                check_availability_task_emart.cancel()
                check_availability_task_emart = None  # 태스크를 취소한 후 None으로 재설정
            await ctx.respond("이마트 재고 알람이 비활성화되었습니다.")
            logging.info(f"서버 {server_guid}에서 이마트 알람이 비활성화되었습니다.")

    except Exception as e:
        error_message = f"에러 발생: {e}"
        logging.error(error_message)
        await ctx.respond(error_message)
    
# 주기적 재고 확인 함수 코모도
async def check_availability_periodic_komodo():
    while True:
        try:
            # 서버 상태 확인하여 알람 활성화된 서버가 있는지 검사
            server_status = load_server_status()
            if not any(status.get('komodo_alarm_active') for status in server_status.values()):
                break

            user_agent = UserAgent()
            headers = {"User-Agent": user_agent.random, 'Cache-Control': 'no-cache'}
            response = requests.get(url, headers=headers)
            soup = BeautifulSoup(response.text, 'html.parser')
            stock_items = soup.find_all("li", class_="variation-item card-full-invoice show")

            availability_messages = []
            for item in stock_items:
                item_id = item.get('id')
                product_name = product_mapping.get(item_id, "Unknown Product")
                is_sold_out = item.find("div", class_="new-soldout-ribbon") is not None
                stock_status = '품절' if is_sold_out else '재고있음'
                availability_messages.append(f"{product_name}: {stock_status}")

            combined_message = "\n".join(availability_messages)

            for server_id, status in server_status.items():
                if status.get('komodo_alarm_active'):
                    channel_id = status.get('last_channel_id')
                    previous_message = status.get('previous_message', '')
                    if channel_id and previous_message != combined_message:
                        channel = bot.get_channel(int(channel_id))
                        if channel:
                            await channel.send(combined_message)
                            update_server_status(server_id, previous_message=combined_message)
            
            logging.info("코모도 전역 크롤러 태스크 실행 중...")
            #logging.info(combined_message)
            await asyncio.sleep(30)

        except requests.RequestException as e:
            logging.error(f"HTTP 요청 중 에러 발생: {e}")
            await asyncio.sleep(30)
            continue  # 다음 주기로 넘어감

        except Exception as e:
            logging.error(f"기타 에러 발생: {e}")
            await asyncio.sleep(30)
            continue  # 다음 주기로 넘어감


async def fetch_emart_stock(session, url, headers, params):
    try:
        async with session.get(url, headers=headers, params=params) as response:
            return await response.json()
    except Exception as e:
        logging.error(f"Error fetching eMart stock: {e}")
        return None

# 주기적 재고 확인 함수 이마트
async def check_availability_periodic_emart():
    while True:
        try:
            logging.info("이마트 재고확인 반복 함수 호출됨")
            all_items_data = {}
            models = ['512GB', '1TB']
            async with aiohttp.ClientSession() as session:
                for model in models:
                    items = []
                    details = sku_details[model]
                    xlog_keys = load_xlog_keys()  # xlog_keys.json에서 값을 불러옴
                    headers = {
                            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_3_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148',
                            'Accept': 'application/json, text/plain, */*',
                            'Accept-Encoding': 'gzip, deflate, br',
                            'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.8',
                            'Content-Type': 'application/json',
                            'Sec-Fetch-Site': 'same-origin',
                            'Sec-Fetch-Mode': 'cors',
                            'xlog_key': xlog_keys.get('xlog_key', ''),
                            'xlog_location': 'store',
                            'Sec-Fetch-Dest': 'empty',
                            'Referer': details['referer'],
                        }
                    base_url = 'https://eapp.emart.com/api/v1/search/item'
                    page = 1

                    while True:
                        params = {
                            'skuCode': details['sku_code'],
                            'areaId': details['area_id'],
                            'storeType': details['store_type'],
                            'bookmarkYn': 'false',
                            'statusOpenYn': 'false',
                            'sortType': 'storeNm',
                            #'sortType': 'distance',
                            #'posX': '37.53382410969574',      #검색할 위치의 위도
                            #'posY': '126.93710803985596',      #검색할 위치의 경도
                            'page': page,
                            'limit': details['limit']
                        }
                        data = await fetch_emart_stock(session, base_url, headers, params)
                        
                        if not data or not data.get('data', {}).get('detailItems', []):
                            break  # No more items to fetch or failure in fetching
                            
                        items.extend(data['data']['detailItems'])
                        logging.info(f"{model} 페이지 {page} 이마트 재고확인 중...")
                        page += 1
                        await asyncio.sleep(1)  # Be polite with the server's resources

                    all_items_data[model] = items
                    #logging.info(f"{all_items_data[model]}")

                    if all_items_data[model]:
                        logging.info(f"[{model}] 크롤링 완료: {len(all_items_data[model])}개의 아이템을 찾았습니다.")
                    else:
                        logging.error(f"[{model}] 크롤링 결과가 없습니다.")
                        
                        user = await bot.fetch_user(author_user_id)  # 사용자 객체를 가져옵니다.
                        if user:
                            try:
                                dm_channel = await user.create_dm()  # DM 채널을 생성합니다.
                                await dm_channel.send(f"xlog_key 최신화 필요")  # DM으로 메시지를 보냅니다.
                                logging.error(f"xlog_key 최신화 필요")
                            except Exception as e:
                                logging.error(f"Failed to send DM: {e}")

            file_path = 'emart_stock_status.json'
            if not os.path.exists(file_path):
                with open(file_path, 'w') as file:
                    json.dump({}, file)
            else:
                # 이전 재고 상태 로드
                previous_stock_status = load_emart_stock_status()

            # 현재와 이전 재고 상태 비교, 변경사항 필터링
            stock_changes = {}
            for model, items in all_items_data.items():
                previous_items = previous_stock_status.get('data', {}).get(model, [])
                # 항목별로 재고 상태가 '품절'에서 '재고있음'으로 변경된 경우만 필터링
                changed_items = [
                    item for item in items
                    if item['stockStatus'] != 'NO_STOCK' and not any(
                        p_item['storeNm'] == item['storeNm'] and p_item['stockStatus'] == item['stockStatus'] for p_item in previous_items)
                ]
                # 재고가 변경된 점포 목록
                #logging.info(f"{changed_items}") 
                if changed_items:
                    stock_changes[model] = changed_items

            if stock_changes:
                # 실제로 재고 상태가 변경된 경우에만 업데이트 파일 저장
                save_to_emart_json('emart_stock_status.json', all_items_data)

                # 서버 설정에 따라 메시지 발송
                for server_id, status in load_server_status().items():
                    if status.get('emart_alarm_active'):
                        model = status.get('emart_model', '512GB')
                        if model in stock_changes and stock_changes[model]:
                            channel_id = status.get('last_channel_id')
                            if channel_id:
                                channel = bot.get_channel(int(channel_id))
                                if channel:
                                    await compose_stock_change_message(channel, stock_changes[model], model)

            logging.info("이마트 전역 크롤러 태스크 실행 중...")
            await asyncio.sleep(300)

        except requests.RequestException as e:
            logging.error(f"HTTP 요청 중 에러 발생: {e}")
            await asyncio.sleep(300)
            continue  # 다음 주기로 넘어감

        except Exception as e:
            logging.error(f"기타 에러 발생: {e}")
            await asyncio.sleep(300)
            continue  # 다음 주기로 넘어감

async def compose_stock_change_message(channel, stock_changes, model):
    # 페이지당 최대 줄 수와 한 줄당 항목 수
    MAX_LINES = 8
    ITEMS_PER_LINE = 3
    MAX_FIELDS_PER_PAGE = MAX_LINES * ITEMS_PER_LINE

    # 페이지 수와 현재 페이지에 추가된 필드 수를 추적
    page_num = 1
    fields_added = 0

    # 새 embed 생성
    embed = discord.Embed(title=f"이마트 {model} 모델 입고 알림 - (페이지 {page_num})", color=0xF1B924)
    embed.set_footer(text="실제 재고는 다를 수 있습니다. 정확한 재고는 매장에 문의해주세요.")

    for item in stock_changes:
        store_name = item['storeNm']
        stock_status = ':green_circle: 재고 있음' if item['stockStatus'] != 'NO_STOCK' else ':red_circle: 품절'
        embed.add_field(name=store_name, value=stock_status, inline=True)
        fields_added += 1

        # 페이지당 최대 필드 수를 초과하면 새 페이지 생성
        if fields_added >= MAX_FIELDS_PER_PAGE:
            await channel.send(embed=embed)  # 현재 페이지 전송
            page_num += 1  # 페이지 수 증가
            fields_added = 0  # 추가된 필드 수 초기화

            # 새로운 embed 생성
            embed = discord.Embed(title=f"이마트 {model} 모델 입고 알림 - (페이지 {page_num})", color=0xF1B924)
            embed.set_footer(text="실제 재고는 다를 수 있습니다. 정확한 재고는 매장에 문의해주세요.")

    # 마지막 페이지 전송
    if fields_added > 0:
        await channel.send(embed=embed)
    

# 재고 확인 함수 코모도
async def check_availability(server_guid, channel, send_message=True):
    try:
        logging.info(f"Check availability called for server {server_guid}")
        user_agent = UserAgent()
        headers = {"User-Agent": user_agent.random, 'Cache-Control': 'no-cache'}
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')

        stock_items = soup.find_all("li", class_="variation-item card-full-invoice show")
        availability_messages = []
        for item in stock_items:
            item_id = item.get('id')
            product_name = product_mapping.get(item_id, "Unknown Product")
            is_sold_out = item.find("div", class_="new-soldout-ribbon") is not None
            stock_status = '품절' if is_sold_out else '재고있음'
            availability_messages.append(f"{product_name}: {stock_status}")

        combined_message = "\n".join(availability_messages)

        if send_message and channel:
            #sent_message = await channel.send(combined_message)
            return f"{combined_message}"

        previous_message = load_previous_message(server_guid)
        logging.info(f"Previous message for server {server_guid}: {previous_message}")
        if previous_message != combined_message and channel:
            await channel.send("재고가 변경되었습니다!!!")
            await channel.send(combined_message)
            save_previous_message(server_guid, combined_message)
        elif previous_message == combined_message:
            save_previous_message(server_guid, combined_message)

    except requests.RequestException as e:
        error_message = f"HTTP 요청 중 에러 발생: {e}"
        logging.error(error_message)
        if channel:
            await channel.send(error_message)
    except Exception as e:
        error_message = f"에러 발생: {e}"
        logging.error(error_message)
        if channel:
            await channel.send(error_message)

async def send_stock_info_as_embed(ctx, all_items_512GB, all_items_1TB):
    # Embed 생성 및 페이지별로 필드 추가
    def create_embed(title, items, page_num):
        embed = discord.Embed(title=f"{title} (페이지 {page_num})", color=0xF1B924)
        embed.set_footer(text="실제 재고는 다를 수 있습니다. 정확한 재고는 매장에 문의해주세요.")
        return embed

    # Embed 전송 및 페이지 수 증가
    async def send_embed_items(embed, items, page_num, model):
        for item in items:
            stock_status = ':green_circle: 재고있음' if item['stockStatus'] != 'NO_STOCK' else ':red_circle: 품절'
            embed.add_field(name=f"{item['storeNm']}", value=stock_status, inline=True)
            if len(embed.fields) % 25 == 0:
                await ctx.send(embed=embed)
                page_num += 1
                embed = create_embed(f"이마트 재고 상태 - {model}", items, page_num)
        return embed, page_num

    # 512GB 모델 정보를 Embed에 담아 전송합니다.
    page_num_512GB = 1
    embed_512GB = create_embed("이마트 재고 상태 - 512GB", all_items_512GB, page_num_512GB)
    embed_512GB, page_num_512GB = await send_embed_items(embed_512GB, all_items_512GB, page_num_512GB, '512GB')
    if len(embed_512GB.fields) > 0:
        await ctx.send(embed=embed_512GB)

    # 1TB 모델 정보를 Embed에 담아 전송합니다.
    page_num_1TB = 1
    embed_1TB = create_embed("이마트 재고 상태 - 1TB", all_items_1TB, page_num_1TB)
    embed_1TB, page_num_1TB = await send_embed_items(embed_1TB, all_items_1TB, page_num_1TB, '1TB')
    if len(embed_1TB.fields) > 0:
        await ctx.send(embed=embed_1TB)

async def check_availability_emart(ctx):
    # 이전에 저장된 데이터가 있는지 확인하고, 5분 이내인지 검증합니다.
    data = load_emart_stock_status()
    timestamp = datetime.datetime.fromisoformat(data["timestamp"])
    diff_time = (datetime.datetime.now() - timestamp).total_seconds()
    logging.info(f"마지막 확인 시간: {diff_time}s 전")

    if diff_time <= 300:
        # 5분 이내의 데이터가 있다면, 해당 데이터를 사용하여 메시지를 발송합니다.
        logging.info(f"기존 데이터 사용")
        await send_stock_info_as_embed(ctx, data['data']['512GB'], data['data']['1TB'])
    # 파일에 기록된 시간을 확인하고 현재 시간과의 차이를 계산합니다.    
    elif diff_time > 300:
        logging.info(f"크롤링 진행")
        models = ['512GB', '1TB']
        all_items_512GB = []
        all_items_1TB = []

        async with aiohttp.ClientSession() as session:
            for model in models:
                details = sku_details[model]
                xlog_keys = load_xlog_keys()  # xlog_keys.json에서 값을 불러옴
                headers = {
                    'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_3_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148',
                    'Accept': 'application/json, text/plain, */*',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.8',
                    'Content-Type': 'application/json',
                    'Sec-Fetch-Site': 'same-origin',
                    'Sec-Fetch-Mode': 'cors',
                    'xlog_key': xlog_keys.get('xlog_key', ''),
                    'xlog_location': 'store',
                    'Sec-Fetch-Dest': 'empty',
                    'Referer': details['referer'],
                }
                base_url = 'https://eapp.emart.com/api/v1/search/item'
                items = []
                page = 1

                async with aiohttp.ClientSession() as session:
                    while True:
                        params = {
                            'skuCode': details['sku_code'],
                            'areaId': details['area_id'],
                            'storeType': details['store_type'],
                            'bookmarkYn': 'false',
                            'statusOpenYn': 'false',
                            'sortType': 'storeNm',           # 상점명 가나다순 정렬
                            # 'sortType': 'distance',        # 상점 거리순 정렬 (필요한 경우 주석 해제)
                            # 'posX': '37.53382410969574',   # 검색할 위치의 위도, 필요한 경우 주석 해제 및 값 조정
                            # 'posY': '126.93710803985596',  # 검색할 위치의 경도, 필요한 경우 주석 해제 및 값 조정
                            'page': page,
                            'limit': details['limit']
                        }
                        data = await fetch_emart_stock(session, base_url, headers, params)
                        if not data or not data.get('data', {}).get('detailItems', []):
                            break  # No more items to fetch or failure in fetching
                            
                        items.extend(data['data']['detailItems'])
                        page += 1
                        await asyncio.sleep(1)  # 다음 결과 호출전까지 1초 대기

                        # 모델별로 나눠서 저장
                        if model == '512GB':
                            all_items_512GB = items
                        elif model == '1TB':
                            all_items_1TB = items

                    # 여기에 JSON 파일 저장 로직 추가
                    stock_data = {
                        '512GB': all_items_512GB,
                        '1TB': all_items_1TB
                    }
                    save_to_emart_json('emart_stock_status.json', stock_data)
    
        await send_stock_info_as_embed(ctx, all_items_512GB, all_items_1TB)


global check_availability_task_komodo
check_availability_task_komodo = None
global check_availability_task_emart
check_availability_task_emart = None

# 이벤트 핸들러: 봇이 준비되었을 때 실행되는 함수
@bot.event
async def on_ready():
    global check_availability_task_komodo, check_availability_task_emart

    logging.info(f'We have logged in as {bot.user}')

    if not cleanup_server_status.is_running():
        cleanup_server_status.start()
        logging.info("Scheduled cleanup task for server_status.json.")

    server_status = load_server_status()
    for guild in bot.guilds:
        server_guid = str(guild.id)
        server_info = server_status.get(server_guid, {})

        # 코모도 알람 재활성화 로직
        if server_info.get('komodo_alarm_active'):
            last_channel_id = server_info.get('last_channel_id')
            if last_channel_id:
                channel = bot.get_channel(int(last_channel_id))
                if channel:
                    if not check_availability_task_komodo or check_availability_task_komodo.done():
                        check_availability_task_komodo = bot.loop.create_task(check_availability_periodic_komodo())
                    logging.info(f"Reactivating komodo alarm for guild {server_guid}")
                    await channel.send('이전에 코모도 재고알림이 활성화 되어 있었으므로, 알람이 재활성됩니다.')

        # 이마트 알람 재활성화 로직
        if server_info.get('emart_alarm_active'):
            selected_model = server_info.get('emart_model', None)  # 사용자가 선택한 모델 정보 조회
            last_channel_id = server_info.get('last_channel_id')
            if last_channel_id:
                channel = bot.get_channel(int(last_channel_id))
                if channel:
                    if not check_availability_task_emart or check_availability_task_emart.done():
                        check_availability_task_emart = bot.loop.create_task(check_availability_periodic_emart())
                    logging.info(f"Reactivating emart alarm for guild {server_guid} with model {selected_model}")
                    await channel.send(f'이전에 이마트 {selected_model} 모델 재고알림이 활성화 되어 있었으므로, 알람이 재활성됩니다.')


# 이벤트 핸들러: 봇이 연결을 해제할 때 실행되는 함수
@bot.event
async def on_disconnect():
    logging.info(f"We have been disconnected.")


async def start_bot():
    async with bot:
        await bot.start(DISCORD_BOT_TOKEN)

async def main():
    reconnect_attempts = 0
    max_reconnect_attempts = 30  # 최대 재연결 시도 횟수 설정
    while reconnect_attempts < max_reconnect_attempts:
        try:
            logging.info("Bot is starting...")
            await start_bot()
        except aiohttp.http_websocket.WebSocketError as e:
            reconnect_attempts += 1
            logging.error(f"WebSocketError detected: {e}. Attempting to reconnect... (Attempt {reconnect_attempts}/{max_reconnect_attempts})")
            # 재연결 전 대기 시간 (여기서는 10초)
            await asyncio.sleep(10)
        except Exception as e:
            logging.exception("An unexpected error occurred", exc_info=e)
            break
    if reconnect_attempts >= max_reconnect_attempts:
        logging.error(f"Reached the maximum number of reconnect attempts ({max_reconnect_attempts}). Exiting...")
        await bot.close()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
