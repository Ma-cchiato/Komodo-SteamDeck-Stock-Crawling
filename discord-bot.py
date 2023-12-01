import discord
from discord.ext import commands
import asyncio
import os
import json
from bs4 import BeautifulSoup
import requests
from fake_useragent import UserAgent

DISCORD_BOT_TOKEN = "YOUR_DISCORD_BOT_TOKEN" # 개별 디스코드 봇 토큰으로 교체
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="?", intents=intents)

url = "https://steamdeck.komodo.jp/?lang=ko"

# 파일 경로 및 파일 이름 설정
#CHANNEL_ID_FILE = "channel_id.json"
PREVIOUS_MESSAGE_FILE = "previous_message.json"

product_mapping = {
    "variation-89372": "Steam Deck LCD 256GB",  #KR
    "variation-89365": "Steam Deck LCD 256GB",  #JP
    "variation-301136": "Steam Deck OLED 512GB",  #KR
    "variation-301131": "Steam Deck OLED 512GB",  #JP
    "variation-301137": "Steam Deck OLED 1TB",  #KR
    "variation-301132": "Steam Deck OLED 1TB"  #JP
}

alarm_active = False
check_active = False


# 채널 아이디를 저장하고 불러오는 함수 정의
#def save_channel_id(channel_id):
#  with open(CHANNEL_ID_FILE, "w") as file:
#    json.dump({"channel_id": channel_id}, file)


#def load_channel_id():
#  if os.path.exists(CHANNEL_ID_FILE):
#    with open(CHANNEL_ID_FILE, "r") as file:
#      data = json.load(file)
#      return data.get("channel_id")
#  return None


def save_previous_message(message):
  with open(PREVIOUS_MESSAGE_FILE, "w") as file:
    json.dump({"previous_message": message}, file)


def load_previous_message():
  if os.path.exists(PREVIOUS_MESSAGE_FILE):
    with open(PREVIOUS_MESSAGE_FILE, "r") as file:
      data = json.load(file)
      return data.get("previous_message")
  return None


def translate_korean_to_english(korean_command):
  command_mappings = {
      '재고알림': 'alarm',
      '재고알림활성화': 'alarm',
      '재고알림비활성화': 'alarm',
  }

  return command_mappings.get(korean_command, korean_command)


async def check_availability(ctx, send_message=True):
  try:

    # UserAgent 인스턴스 생성
    user_agent = UserAgent()

    headers = {
        "User-Agent": user_agent.random,  # 랜덤한 User-Agent 설정
        'Cache-Control': 'no-cache'
    }

    response = requests.get(url, headers=headers)
    print(response)
    print(url)
    print(headers)

    print(response.request.headers['User-Agent'])
    soup = BeautifulSoup(response.text, 'html.parser')

    product_items = soup.find_all(
        "li",
        class_=[
            "variation-item card-full-invoice show",
            "variation-item card-full-invoice sold-out show"
        ])
    print(product_items)

    availability_messages = []

    for item in product_items:
      item_id = item.get('id')

      if "sold-out" in item.get('class'):
        availability_messages.append(f"{product_mapping[item_id]}: 재고없음")
      else:
        availability_messages.append(f"{product_mapping[item_id]}: 재고있음")

    combined_message = "\n".join(availability_messages)
    print(combined_message)

    if send_message:
      print("send message 호출됨")
      await ctx.send(combined_message)

    previous_message = load_previous_message()
    if previous_message != combined_message:
      print("availability changed")
      await ctx.send("재고가 변경되었습니다!!!")
      print("send message 호출됨")
      await ctx.send(combined_message)
      save_previous_message(combined_message)
    elif previous_message == combined_message:
      print("not changed")
      save_previous_message(combined_message)

  except Exception as e:
    error_message = f"에러 발생: {e}"
    print(error_message)
    await ctx.send(error_message)


async def check_availability_periodic(ctx):
  while alarm_active:
    await check_availability(ctx)
    asyncio.sleep(30)  # 현재 크롤링이 동작하는 시간


@bot.command(name='check', aliases=['재고확인'])
async def handle_check_command(ctx):
  global check_active

  print("/check 명령어가 호출되었습니다.")
  check_active = True
  await check_availability(ctx, send_message=True)
  check_active = False


@bot.command(name='alarm', aliases=['재고알림', '알림'])
async def handle_alarm_command(ctx, *args):
  global alarm_active

  try:
    if not args:
      help_message = ("명령어 사용법:\n"
                      "`?alarm 재고`: 30초마다 재고 정보를 확인하고 변경 사항이 있을 때만 메시지 표시\n"
                      "`?alarm 비활성화`: 알람 종료")
      await ctx.send(help_message)
      return

    if args[0] == '재고':
      alarm_active = True
      await ctx.send("30초마다 재고를 확인합니다. \n변경 사항이 있는 경우, 알림 메시지를 표시합니다.")
      await bot.change_presence(status=discord.Status.online,
                                activity=discord.Game("재고 조회 "))
      #await check_availability(ctx, send_message=True)
      while alarm_active:
        await check_availability(ctx, send_message=False)
        await asyncio.sleep(30)

    elif args[0] == '비활성화':
      alarm_active = False
      print('alarm inactive')
      # 재고 조회 완료 후 기본 상태 메시지로 변경
      await bot.change_presence(status=discord.Status.online, activity=None)
      await ctx.send("알람이 비활성화되었습니다.")

    else:
      await ctx.send("잘못된 명령어입니다. 도움말을 확인해주세요.")

  except Exception as e:
    error_message = f"에러 발생: {e}"
    print(error_message)
    await ctx.send(error_message)


#@bot.command(name='setchannel', aliases=['채널설정'])
#async def handle_setchannel_command(ctx):
#  global DISCORD_CHANNEL_ID

#  current_channel_id = load_channel_id()

#  if current_channel_id:
#    await ctx.send(f'현재 채널이 이미 설정되어 있습니다. 현재 채널 아이디: {current_channel_id}')
#  else:
#    DISCORD_CHANNEL_ID = ctx.channel.id
#    save_channel_id(DISCORD_CHANNEL_ID)
#    await ctx.send(f'채널이 {ctx.channel.mention}로 설정되었습니다.')


@bot.event
async def on_ready():
  print(f'We have logged in as {bot.user}')


bot.run(DISCORD_BOT_TOKEN)
