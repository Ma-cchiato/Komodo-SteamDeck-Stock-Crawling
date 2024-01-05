import discord
from discord.ext import commands
from discord.commands import Option
import asyncio
import json
from bs4 import BeautifulSoup
import requests
from fake_useragent import UserAgent

# Discord 봇 토큰 및 기타 설정
DISCORD_BOT_TOKEN = "YOUR_DISCORD_BOT_TOKEN"
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="?", intents=intents)

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

# 서버 상태 JSON 파일 관련 함수
def load_server_status():
    try:
        with open('server_status.json', 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        return {}

def save_server_status(server_status):
    with open('server_status.json', 'w') as file:
        json.dump(server_status, file)

def load_previous_message(server_guid):
    server_status = load_server_status()
    return server_status.get(server_guid, {}).get('previous_message')

def save_previous_message(server_guid, message):
    update_server_status(server_guid, previous_message=message)

def update_server_status(server_id, alarm_active=None, last_channel_id=None, previous_message=None):
    server_status = load_server_status()
    if server_id not in server_status:
        server_status[server_id] = {}
    if alarm_active is not None:
        server_status[server_id]['alarm_active'] = alarm_active
    if last_channel_id is not None:
        server_status[server_id]['last_channel_id'] = last_channel_id
    if previous_message is not None:
        server_status[server_id]['previous_message'] = previous_message
    save_server_status(server_status)

# 슬래시 명령어: 재고 확인
@bot.slash_command(name="재고확인", description="재고를 확인합니다.")
async def check_availability_slash(ctx):
    await ctx.defer()  # 명령어 처리가 진행 중임을 알림

    server_guid = str(ctx.guild.id)
    server_status = load_server_status()
    channel_id = server_status.get(server_guid, {}).get('last_channel_id') or ctx.channel.id
    channel = bot.get_channel(int(channel_id))
    
    # 재고 확인 메시지를 보낸 후, 응답 완료 메시지 전송
    result_message = await check_availability(server_guid, channel, send_message=True)
    await ctx.respond(f"재고 상태:\n{result_message}")
    print(f"서버 {server_guid}에서 재고확인을 호출하였습니다.")

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
@bot.slash_command(name='알림', description="30초마다 재고를 확인하고, 변경사항이 발생하면 알림을 수신합니다.")
async def handle_alarm_command(ctx, 
                               mode: Option(str, "알림 모드를 선택하세요", 
                                            choices=["재고", "비활성화"], required=True)):
    global check_availability_task
    server_guid = str(ctx.guild.id)
    
    try:
        if mode == '재고':
            update_server_status(server_guid, alarm_active=True, last_channel_id=ctx.channel.id)
            await ctx.respond("재고 알람이 활성화되었습니다.")
            print(f"서버 {server_guid}에서 알람이 활성화되었습니다.")

            if any(status.get('alarm_active') for status in load_server_status().values()):
                await bot.change_presence(status=discord.Status.online, activity=discord.Game("재고 조회"))

            # 태스크가 이미 실행 중인지 확인하고, 실행 중이지 않으면 태스크 시작
            if check_availability_task is None or check_availability_task.done():
                check_availability_task = asyncio.create_task(check_availability_periodic())

        elif mode == '비활성화':
            update_server_status(server_guid, alarm_active=False)
            await ctx.respond("재고 알람이 비활성화되었습니다.")
            print(f"서버 {server_guid}에서 알람이 비활성화되었습니다.")

    except Exception as e:
        error_message = f"에러 발생: {e}"
        print(error_message)
        await ctx.respond(error_message)

# 주기적 재고 확인 함수
async def check_availability_periodic():
    while True:
        # 서버 상태 확인하여 알람 활성화된 서버가 있는지 검사
        server_status = load_server_status()
        if not any(status.get('alarm_active') for status in server_status.values()):
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
            if status.get('alarm_active'):
                channel_id = status.get('last_channel_id')
                previous_message = status.get('previous_message', '')
                if channel_id and previous_message != combined_message:
                    channel = bot.get_channel(int(channel_id))
                    if channel:
                        await channel.send(combined_message)
                        update_server_status(server_id, previous_message=combined_message)
        
        print("전역 크롤러 태스크 실행 중...")
        print(combined_message)
        await asyncio.sleep(30)

# 재고 확인 함수
async def check_availability(server_guid, channel, send_message=True):
    try:
        print(f"Check availability called for server {server_guid}")
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
        print(combined_message)
        print(f"Previous message for server {server_guid}: {previous_message}")
        if previous_message != combined_message and channel:
            await channel.send("재고가 변경되었습니다!!!")
            await channel.send(combined_message)
            save_previous_message(server_guid, combined_message)
        elif previous_message == combined_message:
            save_previous_message(server_guid, combined_message)

    except requests.RequestException as e:
        error_message = f"HTTP 요청 중 에러 발생: {e}"
        print(error_message)
        if channel:
            await channel.send(error_message)
    except Exception as e:
        error_message = f"에러 발생: {e}"
        print(error_message)
        if channel:
            await channel.send(error_message)


global check_availability_task
check_availability_task = None
# 이벤트 핸들러: 봇이 준비되었을 때 실행되는 함수
@bot.event
async def on_ready():
    global check_availability_task


    print(f'We have logged in as {bot.user}')
    server_status = load_server_status()
    for guild in bot.guilds:
        server_guid = str(guild.id)
        print(f"Ready in guild: {server_guid}")
        server_info = server_status.get(server_guid, {})
        if server_info.get('alarm_active'):
            last_channel_id = server_info.get('last_channel_id')
            if last_channel_id:
                channel = bot.get_channel(int(last_channel_id))
                if channel:
                    print(f"Reactivating alarm for guild {server_guid} in channel {channel.id}")
                    await channel.send('봇이 다시 시작되었습니다.')
                    await channel.send('이전에 재고알림이 활성화 되어 있었으므로, 알람이 재활성됩니다.')
                    update_server_status(server_guid, alarm_active=True, last_channel_id=last_channel_id)
                    if not check_availability_task or check_availability_task.done():
                        check_availability_task = bot.loop.create_task(check_availability_periodic())

# 이벤트 핸들러: 봇이 연결을 해제할 때 실행되는 함수
@bot.event
async def on_disconnect():
    print(f"We have been disconnected.")
    for guild in bot.guilds:
        server_guid = str(guild.id)
        update_server_status(server_guid, alarm_active=False)

bot.run(DISCORD_BOT_TOKEN)
