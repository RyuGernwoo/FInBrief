"""FinBrief 관리 챗봇 (Discord 슬래시 커맨드 엔트리포인트).
   실행:  python -m app.services.discord_bot
   로직은 chatbot.handle + SubscriptionService 재사용(얇은 엔트리포인트)."""
from __future__ import annotations

import asyncio
import os

import discord
from discord import app_commands

from app.services.chatbot import handle
from app.services.subscription_service import SubscriptionService
from app.repositories.memory import create_memory_repositories      # 로컬 개발용(재시작 시 초기화)
from app.repositories.supabase import create_supabase_repositories  # 실 DB(영속)


def _load_dotenv() -> None:
    """의존성 없이 repo 루트 .env 를 os.environ 로 로드(이미 설정된 값은 유지)."""
    env_path = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
    try:
        with open(env_path, encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip())
    except FileNotFoundError:
        pass


_load_dotenv()

# repo 번들: SUPABASE_URL 있으면 실 DB(영속), 없으면 memory(재시작 시 초기화).
# 봇은 news.match 를 안 쓰므로 query_embedding_provider 불필요.
_REPOS = None


def _repos():
    global _REPOS
    if _REPOS is None:
        if os.getenv("SUPABASE_URL"):
            _REPOS = create_supabase_repositories()
        else:
            _REPOS = create_memory_repositories()
    return _REPOS


def _service() -> SubscriptionService:
    return SubscriptionService(_repos())


GUILD = discord.Object(id=int(os.environ["DISCORD_GUILD_ID"]))

intents = discord.Intents.default()   # 슬래시만 쓰면 기본으로 충분
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)


@tree.command(name="finbrief", description="브리핑 메이트에게 관심 금융 토픽을 자연어로 관리합니다.", guild=GUILD)
@app_commands.describe(message='예: "나스닥 구독", "내 토픽 보여줘", "비트코인 취소", "추천해줘"')
async def finbrief(interaction: discord.Interaction, message: str):
    # LLM intent 파싱이 3초를 넘길 수 있어 먼저 defer(15분 확보), 블로킹 handle 은 스레드에서.
    await interaction.response.defer(ephemeral=True)  # "생각 중…" (본인만 보이게)
    res = await asyncio.to_thread(handle, _service(), "discord", str(interaction.user.id), message,
                                  str(interaction.channel_id))  # 구독 시 이 채널로 카드 발송
    await interaction.followup.send(res["reply"], ephemeral=True)


@client.event
async def on_ready():
    await tree.sync(guild=GUILD)      # 길드 sync = 즉시 반영
    print(f"✅ logged in as {client.user}")


if __name__ == "__main__":
    client.run(os.environ["DISCORD_BOT_TOKEN"])
