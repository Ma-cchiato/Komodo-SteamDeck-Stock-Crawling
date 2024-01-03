# 필요한 라이브러리와 모듈을 import
import discord
from discord.ext import commands, tasks
import asyncio
import os
import json
from bs4 import BeautifulSoup
import requests
from fake_useragent import UserAgent

# Discord 봇 토큰
DISCORD_BOT_TOKEN = "YOUR_DISCORD_BOT_TOKEN"

# Discord Bot 객체 생성
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="?", intents=intents)

# Steam Deck 상품 페이지 URL
url = "https://steamdeck.komodo.jp/?lang=ko"

# Steam Deck 상품 매핑 정보
product_mapping = {
    "variation-89372": "Steam Deck LCD 256GB",  # KR
    "variation-89365": "Steam Deck LCD 256GB",  # JP
    "variation-301136": "Steam Deck OLED 512GB",  # KR
    "variation-301131": "Steam Deck OLED 512GB",  # JP
    "variation-301137": "Steam Deck OLED 1TB",  # KR
    "variation-301132": "Steam Deck OLED 1TB"  # JP
}

# 전역 변수로 사용할 변수 초기화
alarm_active = False
last_channel_id = None

# 함수: 마지막으로 저장된 메시지 로드
async def load_previous_message(server_guid):
    file_name = f"previous_message_{server_guid}.json"
    if os.path.exists(file_name):
        with open(file_name, "r") as file:
            data = json.load(file)
            return data.get("previous_message")
    return None

# 함수: 알람 상태 로드
async def load_alarm_status(server_guid):
    file_name = f"alarm_status_{server_guid}.json"
    if os.path.exists(file_name):
        with open(file_name, "r") as file:
            data = json.load(file)
            return data.get("alarm_active", False)
    return False

# 함수: 마지막 채널 ID 로드
async def load_last_channel_id(server_guid):
    file_name = f"last_channel_id_{server_guid}.json"
    if os.path.exists(file_name):
        with open(file_name, "r") as file:
            data = json.load(file)
            return data.get("last_channel_id")
    else:
        print(f"No last channel ID file found for guild {server_guid}.")
    return None

# 함수: 이전 메시지 저장
async def save_previous_message(server_guid, message):
    file_name = f"previous_message_{server_guid}.json"
    with open(file_name, "w") as file:
        json.dump({"previous_message": message}, file)

# 함수: 알람 상태 저장
async def save_alarm_status(server_guid, status):
    file_name = f"alarm_status_{server_guid}.json"
    with open(file_name, "w") as file:
        json.dump({"alarm_active": status}, file)

# 함수: 마지막 채널 ID 저장
async def save_last_channel_id(server_guid, channel_id):
    file_name = f"last_channel_id_{server_guid}.json"
    with open(file_name, "w") as file:
        json.dump({"last_channel_id": channel_id}, file)
    print(f"Saved last channel ID {channel_id} for guild {server_guid}.")

# 함수: 서버 GUID를 기반으로 채널 가져오기
async def get_channel_by_server_guid(server_guid):
    guild = bot.get_guild(int(server_guid))
    if not guild:
        print(f"Guild with ID {server_guid} not found.")
        return None

    last_channel_id = await load_last_channel_id(server_guid)
    if last_channel_id:
        channel = guild.get_channel(last_channel_id)
        if channel:
            return channel
        else:
            print(f"Channel with ID {last_channel_id} not found in guild {server_guid}. Falling back to system channel.")
    else:
        print(f"No last channel ID found for guild {server_guid}. Falling back to system channel.")
    
    # Falling back to the system channel if the last channel is not found or does not exist.
    return guild.system_channel if guild.system_channel else None

# 명령어: 재고 확인
@bot.command(name='check', aliases=['재고확인'])
async def check_availability_command(ctx):
    server_guid = str(ctx.guild.id)
    # 사용자가 메시지를 보낸 채널로 설정된 경우 혹은 사용자가 설정한 채널로 설정
    last_channel_id = await load_last_channel_id(server_guid)
    channel = bot.get_channel(last_channel_id) if last_channel_id else ctx.channel
    await check_availability(server_guid, channel, send_message=True)

# 명령어: 사용자가 메시지를 수신할 채널 설정
@bot.command(name='setchannel', aliases=['채널', '채널설정'])
async def set_channel(ctx, channel_id: int = None):
    server_guid = str(ctx.guild.id)
    if channel_id:
        # 사용자가 지정한 채널 ID로 설정
        await save_last_channel_id(server_guid, channel_id)
        await ctx.send(f"메시지를 수신할 채널이 {channel_id}로 설정되었습니다.")
    else:
        # 현재 채널로 설정
        await save_last_channel_id(server_guid, ctx.channel.id)
        await ctx.send(f"메시지를 수신할 채널이 현재 채널({ctx.channel.id})로 설정되었습니다.")

# 명령어: 알람 관리
@bot.command(name='alarm', aliases=['알림'])
async def handle_alarm_command(ctx, *args):
    global alarm_active, last_channel_id
    try:
        if not args:
            help_message = ("명령어 사용법:\n"
                            "`?alarm 재고`: 30초마다 재고 정보를 확인하고 변경 사항이 있을 때만 메시지 표시\n"
                            "`?alarm 비활성화`: 알람 종료")
            await ctx.send(help_message)
            return

        if args[0] == '재고':
            await start_availability_check(str(ctx.guild.id), ctx.channel)

        elif args[0] == '비활성화':
            alarm_active = False
            last_channel_id = ctx.channel.id
            server_guid = str(ctx.guild.id)
            print('alarm inactive')
            # 재고 조회 완료 후 기본 상태 메시지로 변경
            await bot.change_presence(status=discord.Status.online, activity=None)
            await ctx.send("알람이 비활성화되었습니다.")
            await save_last_channel_id(server_guid, last_channel_id)
            await save_alarm_status(server_guid, alarm_active)

        else:
            await ctx.send("잘못된 명령어입니다. 도움말을 확인해주세요.")

    except Exception as e:
        error_message = f"에러 발생: {e}"
        print(error_message)
        await ctx.send(error_message)

# 함수: 주기적으로 재고 확인
async def check_availability_periodic(server_guid):
    while alarm_active:
        print("Checking availability...")
        channel = await get_channel_by_server_guid(server_guid)  # 수정된 부분
        await check_availability(str(server_guid), channel, send_message=False)  # 수정된 부분
        await asyncio.sleep(30)

# 함수: 재고 확인
async def check_availability(server_guid, channel, send_message=True):
    try:
        print(f"Check availability called for server {server_guid}")
        user_agent = UserAgent()
        headers = {
            "User-Agent": user_agent.random,
            'Cache-Control': 'no-cache'
        }

        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')

        # 'variation-item card-full-invoice show' 클래스를 가진 'li' 태그들을 찾습니다.
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
            await channel.send(combined_message)

        previous_message = await load_previous_message(server_guid)
        print(combined_message)
        print(previous_message)
        if previous_message != combined_message and channel:
            await channel.send("재고가 변경되었습니다!!!")
            await channel.send(combined_message)
            await save_previous_message(server_guid, combined_message)
        elif previous_message == combined_message:
            await save_previous_message(server_guid, combined_message)

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


# 함수: 주기적으로 재고 확인 및 알림
async def start_availability_check(server_guid, channel):
    global alarm_active, last_channel_id
    alarm_active = True
    last_channel_id = channel.id
    await channel.send("30초마다 재고를 확인합니다. \n변경 사항이 있는 경우, 알림 메시지를 표시합니다.")
    await bot.change_presence(status=discord.Status.online, activity=discord.Game("재고 조회 "))
    
    # 알람 상태와 마지막 채널 ID를 파일에 저장
    await save_alarm_status(server_guid, alarm_active)
    await save_last_channel_id(server_guid, last_channel_id)
    print(last_channel_id)
    
    # 주기적으로 재고 확인하는 태스크 생성
    bot.loop.create_task(check_availability_periodic(server_guid))

# 이벤트 핸들러: 봇이 준비되었을 때 실행되는 함수
@bot.event
async def on_ready():
    print(f'We have logged in as {bot.user}')
    for guild in bot.guilds:
        server_guid = str(guild.id)
        print(f"Ready in guild: {server_guid}")
        alarm_status = await load_alarm_status(server_guid)
        print(alarm_status)
        if alarm_status:
            # Load last channel id and send message
            last_channel = await get_channel_by_server_guid(server_guid)
            print(last_channel)
            if last_channel:
                await asyncio.sleep(1)
                await start_availability_check(server_guid, last_channel)
                await last_channel.send('봇이 재시작되었습니다. 알람이 재활성됩니다.')

# 이벤트 핸들러: 봇이 연결을 해제할 때 실행되는 함수
@bot.event
async def on_disconnect():
    print(f"We have been disconnected. Saving alarm status...")
    for guild in bot.guilds:
        server_guid = str(guild.id)
        await save_alarm_status(server_guid, alarm_active)

# Discord 봇 실행
bot.run(DISCORD_BOT_TOKEN)
