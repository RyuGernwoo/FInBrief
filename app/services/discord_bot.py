"""FinBrief 관리 챗봇 (Discord 슬래시 커맨드 엔트리포인트).
   실행:  python -m app.services.discord_bot
   로직은 chatbot.handle + SubscriptionService 재사용(얇은 엔트리포인트)."""
from __future__ import annotations

import os

import discord
from discord import app_commands

from app.services.chatbot import handle
from app.services.subscription_service import SubscriptionService
from app.services._repo_stub import StubTopics, StubUsers, StubSubs  # Phase 4에서 실 repository로 교체

# MVP 카탈로그(실제는 TopicRepository.list_catalog). 챗봇 화이트리스트 = 이 목록.
CATALOG = [
    {"topic_id": "usdkrw", "name": "원/달러 환율"},
    {"topic_id": "us_rate", "name": "미국 기준금리"},
    {"topic_id": "nasdaq", "name": "나스닥"},
    {"topic_id": "btc", "name": "비트코인"},
    {"topic_id": "semi", "name": "반도체"},
]
# 모듈 레벨(프로세스 동안 in-memory 유지) — 재시작 시 초기화(실 repo 붙이면 영속)
_users, _subs, _topics = StubUsers(), StubSubs(), StubTopics(CATALOG)


def _service() -> SubscriptionService:
    return SubscriptionService(_users, _subs, _topics)


GUILD = discord.Object(id=int(os.environ["DISCORD_GUILD_ID"]))

intents = discord.Intents.default()   # 슬래시만 쓰면 기본으로 충분
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)


@tree.command(name="finbrief", description="구독/토픽 관리 (예: 나스닥 구독해줘)", guild=GUILD)
@app_commands.describe(message="원하는 걸 자연어로: 구독/조회/취소")
async def finbrief(interaction: discord.Interaction, message: str):
    res = handle(_service(), "discord", str(interaction.user.id), message)
    await interaction.response.send_message(res["reply"], ephemeral=True)  # 본인만 보이게


@client.event
async def on_ready():
    await tree.sync(guild=GUILD)      # 길드 sync = 즉시 반영
    print(f"✅ logged in as {client.user}")


if __name__ == "__main__":
    client.run(os.environ["DISCORD_BOT_TOKEN"])
