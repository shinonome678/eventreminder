import discord
import os
import asyncio
from datetime import datetime, timezone
from dotenv import load_dotenv

# .envファイルから環境変数を読み込む
load_dotenv()

BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
# チャンネルIDは整数に変換
NOTIFICATION_CHANNEL_ID = int(os.getenv('NOTIFICATION_CHANNEL_ID'))

# BOTが必要とする権限 (Intents) を設定
intents = discord.Intents.default()
intents.guilds = True
intents.guild_scheduled_events = True 

# BOTクライアントのインスタンスを作成
client = discord.Client(intents=intents)

# 実行中の通知タスクを管理するための辞書
# {event_id: task}
scheduled_tasks = {}

async def schedule_event_notification(event):
    """イベント開始時刻に通知を送るタスク"""
    # 現在時刻（タイムゾーン情報付き）を取得
    now = datetime.now(timezone.utc)
    
    # イベント開始までの秒数を計算
    # もしイベントが既に過去のものであれば、遅延時間は0秒とする
    delay = max(0, (event.start_time - now).total_seconds())

    print(f"イベント「{event.name}」の通知を {delay:.1f} 秒後に予約しました。")
    await asyncio.sleep(delay)

    channel = client.get_channel(NOTIFICATION_CHANNEL_ID)
    if not channel:
        print(f"エラー: チャンネルID ({NOTIFICATION_CHANNEL_ID}) が見つかりません。")
        return

    # イベントがキャンセルまたは完了していないか最終確認
    try:
        updated_event = await event.guild.fetch_scheduled_event(event.id)
        if updated_event.status in (discord.EventStatus.canceled, discord.EventStatus.completed):
            print(f"イベント「{updated_event.name}」は開始前にキャンセルまたは完了したため、通知を中止します。")
            return
    except discord.NotFound:
        print(f"イベントID {event.id} が見つからなかったため、通知を中止します。")
        return

    embed = discord.Embed(
        title=f"⏰ イベント開始時刻です！ ⏰",
        description=f"**イベント「{event.name}」がまもなく始まります！**",
        color=discord.Color.orange()
    )
    try:
        await channel.send(content="@everyone", embed=embed)
        print(f"イベント開始の自動通知を送信しました: {event.name}")
    except discord.Forbidden:
        print(f"エラー: チャンネル({channel.name})へのメッセージ送信権限がありません。")
    except Exception as e:
        print(f"通知送信中にエラーが発生しました: {e}")

    # タスク完了後、辞書から自身を削除
    scheduled_tasks.pop(event.id, None)

@client.event
async def on_ready():
    """BOTが起動したときに実行される処理"""
    print(f'{client.user} としてログインしました。')
    print('------')

@client.event
async def on_scheduled_event_create(event):
    """サーバーで新しいイベントが作成されたときに実行される処理"""
    print(f"新しいイベント「{event.name}」が作成されました。通知タスクをスケジュールします。")
    
    # 通知タスクを作成して辞書に保存
    task = asyncio.create_task(schedule_event_notification(event))
    scheduled_tasks[event.id] = task

    # === イベント作成時の即時通知（これは変更なし） ===
    channel = client.get_channel(NOTIFICATION_CHANNEL_ID)
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

@client.event
async def on_scheduled_event_update(before, after):
    """イベントの時刻などが変更されたときの処理"""
    # 既存のタスクがあればキャンセル
    if before.id in scheduled_tasks:
        scheduled_tasks[before.id].cancel()
        print(f"イベント「{before.name}」の古い通知タスクをキャンセルしました。")
    
    # イベントがキャンセルまたは完了されたのでなければ、新しい時刻でタスクを再作成
    if after.status not in (discord.EventStatus.canceled, discord.EventStatus.completed):
        print(f"イベント「{after.name}」が更新されました。通知タスクを再スケジュールします。")
        task = asyncio.create_task(schedule_event_notification(after))
        scheduled_tasks[after.id] = task

@client.event
async def on_scheduled_event_delete(event):
    """イベントが削除されたときの処理"""
    if event.id in scheduled_tasks:
        scheduled_tasks[event.id].cancel()
        print(f"イベント「{event.name}」が削除されたため、通知タスクをキャンセルしました。")

# BOTを実行
if not BOT_TOKEN or not NOTIFICATION_CHANNEL_ID:
    print("エラー: .envファイルで `DISCORD_BOT_TOKEN` または `NOTIFICATION_CHANNEL_ID` が設定されていません。")
else:
    client.run(BOT_TOKEN)
