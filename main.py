import discord
import os
from dotenv import load_dotenv

load_dotenv() # .envファイルを読み込む
BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN') # .envファイルから取得する

# BOTのトークンと通知したいチャンネルIDを環境変数から取得
BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
NOTIFICATION_CHANNEL_ID = int(os.getenv('NOTIFICATION_CHANNEL_ID'))

# BOTが必要とする権限 (Intents) を設定
intents = discord.Intents.default()
intents.guilds = True
intents.guild_scheduled_events = True 

# BOTクライアントのインスタンスを作成
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    """BOTが起動したときに実行される処理"""
    print(f'{client.user} としてログインしました。')
    print('------')

@client.event
async def on_scheduled_event_create(event):
    """サーバーで新しいイベントが作成されたときに実行される処理"""
    channel = client.get_channel(NOTIFICATION_CHANNEL_ID)
    if not channel:
        print(f"エラー: 指定されたチャンネルID ({NOTIFICATION_CHANNEL_ID}) が見つかりません。")
        return

    # イベント情報を埋め込みメッセージ(Embed)として整形
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
    
    # ★★★ ここが修正点です ★★★
    # イベントにカバー画像があれば、それを埋め込みに設定する
    if event.cover_image:
        embed.set_image(url=event.cover_image.url)

    try:
        await channel.send(embed=embed)
        print(f"イベント作成通知を送信しました: {event.name}")
    except discord.Forbidden:
        print(f"エラー: チャンネル({channel.name})へのメッセージ送信権限がありません。")
    except Exception as e:
        print(f"通知送信中にエラーが発生しました: {e}")

@client.event
async def on_scheduled_event_update(before, after):
    """イベントの状態が更新されたときに実行される処理"""
    if before.status != discord.EventStatus.active and after.status == discord.EventStatus.active:
        channel = client.get_channel(NOTIFICATION_CHANNEL_ID)
        if not channel:
            print(f"エラー: 指定されたチャンネルID ({NOTIFICATION_CHANNEL_ID}) が見つかりません。")
            return
        
        embed = discord.Embed(
            title=f"🎉 イベント開始！ 🎉",
            description=f"**イベント「{after.name}」が開始されました！**",
            color=discord.Color.green()
        )
        try:
            await channel.send(content="@everyone", embed=embed) 
            print(f"イベント開始通知を送信しました: {after.name}")
        except discord.Forbidden:
            print(f"エラー: チャンネル({channel.name})へのメッセージ送信権限がありません。")
        except Exception as e:
            print(f"通知送信中にエラーが発生しました: {e}")

# BOTを実行
if not BOT_TOKEN or not NOTIFICATION_CHANNEL_ID:
    print("エラー: .envファイルで `DISCORD_BOT_TOKEN` または `NOTIFICATION_CHANNEL_ID` が設定されていません。")
else:
    client.run(BOT_TOKEN)