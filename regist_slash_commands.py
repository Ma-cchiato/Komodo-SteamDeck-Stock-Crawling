import requests
import json
import time

# 봇의 애플리케이션 ID와 토큰
application_id = "YOUR_DISCORD_BOT_APPLICATION_ID"
bot_token = "YOUR_DISCORD_BOT_TOKEN"

# 등록할 슬래시 커맨드 정의
commands = [
    {
        "name": "재고확인",
        "description": "재고를 확인합니다.",
        "type": 1
    },
    {
        "name": "채널",
        "description": "메시지를 수신할 채널을 설정합니다.",
        "type": 1
    },
    {
        "name": "알림",
        "description": "재고 알림을 관리합니다.",
        "type": 1
    },
    # 기타 기능에 대한 슬래시 커맨드를 여기에 추가
]

# 디스코드 API에 명령어를 등록하기 위한 URL
url = f"https://discord.com/api/v10/applications/{application_id}/commands"

# 헤더에는 인증 토큰을 포함해야 합니다.
headers = {"Authorization": f"Bot {bot_token}"}

# 각 명령어를 디스코드 API에 등록합니다.
for command in commands:
    response = requests.post(url, headers=headers, json=command)
    if response.status_code in [200, 201]:
        print(f"Command '{command['name']}' registered successfully.")
    else:
        print(f"Error registering command '{command['name']}': {response.status_code} {response.text}")
    time.sleep(3)  # 명령어 등록 간 지연