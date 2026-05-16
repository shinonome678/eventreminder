import discord
from discord.ext import commands
import os
import asyncio
import json
from datetime import datetime, timezone
from dotenv import load_dotenv

# .envファイルから環境変数を読み込む
load_dotenv()

BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
CONFIG_FILE = 'server_configs.json' # サーバーごとの設定を保存するファイル

# --- 設定ファイルの読み書き関数 ---
def load_config():
    """設定ファイルを読み込む"""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_config(config):
    """設定ファイルに書き込む"""
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=4)

# --- BOTの設定 ---
intents = discord.Intents.default()
intents.guilds = True
intents.guild_scheduled_events = True 
intents.message_content = True # コマンド（!setchannel等）を受け取るために必要

bot = commands.Bot(command_prefix='!', intents=intents)

scheduled_tasks = {}

# --- コマンド ---
@bot.command(name="setchannel")
# ★ここにあった管理者制限を削除しました。誰でも実行可能です。
async def set_channel(ctx, channel: discord.TextChannel):
    """通知先のチャンネルを設定するコマンド（例: !setchannel #通知用チャンネル）"""
    config = load_config()
    config[str(ctx.guild.id)] = channel.id
    save_config(config)
    
    await ctx.send(f"✅ このサーバーのイベント通知チャンネルを {channel.mention} に設定しました！")

# --- イベント通知タスク ---
async def schedule_event_notification(event):
    """イベント開始時刻に通知を送るタスク"""
    now = datetime.now(timezone.utc)
    delay = max(0, (event.start_time - now).total_seconds())

    print(f"イベント「{event.name}」の通知を {delay:.1f} 秒後に予約しました。")
    await asyncio.sleep(delay)

    config = load_config()
    channel_id = config.get(str(event.guild.id))

    if not channel_id:
        print(f"サーバー「{event.guild.name}」の通知チャンネルが未設定のため、通知をスキップします。")
        scheduled_tasks.pop(event.id, None)
        return

    channel = bot.get_channel(channel_id)
    if not channel:
        print(f"エラー: サーバー「{event.guild.name}」で設定されたチャンネルが見つかりません。")
        scheduled_tasks.pop(event.id, None)
        return

    try:
        updated_event = await event.guild.fetch_scheduled_event(event.id)
        if updated_event.status in (discord.EventStatus.canceled, discord.EventStatus.completed):
            print(f"イベント「{updated_event.name}」は開始前にキャンセルまたは完了したため、通知を中止します。")
            scheduled_tasks.pop(event.id, None)
            return
    except discord.NotFound:
        print(f"イベントID {event.id} が見つからなかったため、通知を中止します。")
        scheduled_tasks.pop(event.id, None)
        return

    embed = discord.Embed(
        title=f"⏰ イベント開始時刻です！ ⏰",
        description=f"**イベント「{event.name}」がまもなく始まります！**",
        color=discord.Color.orange()
    )
    try:
        await channel.send(embed=embed)
        print(f"イベント開始の自動通知を送信しました: {event.name}")
    except discord.Forbidden:
        print(f"エラー: チャンネル({channel.name})へのメッセージ送信権限がありません。")
    except Exception as e:
        print(f"通知送信中にエラーが発生しました: {e}")

    scheduled_tasks.pop(event.id, None)

@bot.event
async def on_ready():
    """BOTが起動したときに実行される処理"""
    print(f'{bot.user} としてログインしました。')
    print('------')
    
    for guild in bot.guilds:
        for event in guild.scheduled_events:
            if event.status == discord.EventStatus.scheduled and event.id not in scheduled_tasks:
                print(f"再起動復元: イベント「{event.name}」の通知タスクを再スケジュールします。")
                task = asyncio.create_task(schedule_event_notification(event))
                scheduled_tasks[event.id] = task

@bot.event
async def on_scheduled_event_create(event):
    """サーバーで新しいイベントが作成されたときに実行される処理"""
    print(f"新しいイベント「{event.name}」が作成されました。通知タスクをスケジュールします。")
    
    task = asyncio.create_task(schedule_event_notification(event))
    scheduled_tasks[event.id] = task

    config = load_config()
    channel_id = config.get(str(event.guild.id))
    if not channel_id:
        return 
        
    channel = bot.get_channel(channel_id)
    if not channel:
        return

    embed = discord.Embed(
        title=f"新しいイベントが作成されました！",
        description=f"**イベント名:** {event.name}",
        color=discord.Color.blue()
    )
    if event.location:
        embed.add_field(name="場所", value=f"{event.location}", inline=False)
    embed.add_field(name="開始日時", value=f"<t:{int(event.start_time.timestamp())}:F>", inline=False)
    if event.description:
        embed.add_field(name="説明", value=event.description, inline=False)
    if event.cover_image:
        embed.set_image(url=event.cover_image.url)
    try:
        await channel.send(embed=embed)
    except Exception as e:
        print(f"イベント作成通知中にエラー: {e}")

@bot.event
async def on_scheduled_event_update(before, after):
    """イベントの時刻などが変更されたときの処理"""
    if before.id in scheduled_tasks:
        scheduled_tasks[before.id].cancel()
        print(f"イベント「{before.name}」の古い通知タスクをキャンセルしました。")
    
    if after.status not in (discord.EventStatus.canceled, discord.EventStatus.completed):
        print(f"イベント「{after.name}」が更新されました。通知タスクを再スケジュールします。")
        task = asyncio.create_task(schedule_event_notification(after))
        scheduled_tasks[after.id] = task

@bot.event
async def on_scheduled_event_delete(event):
    """イベントが削除されたときの処理"""
    if event.id in scheduled_tasks:
        scheduled_tasks[event.id].cancel()
        print(f"イベント「{event.name}」が削除されたため、通知タスクをキャンセルしました。")

# BOTを実行
if not BOT_TOKEN:
    print("エラー: .envファイルで `DISCORD_BOT_TOKEN` が設定されていません。")
else:
    bot.run(BOT_TOKEN)
