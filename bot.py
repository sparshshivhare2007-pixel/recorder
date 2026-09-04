import os
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import MessageEntityType
from pytgcalls import PyTgCalls
from pytgcalls.types import AudioQuality

# Import modules
from config import API_ID, API_HASH, BOT_TOKEN
from youtube import YouTube
from utils import group_data, recording_file, assistant, extract_link, require_assistant, require_group

# ---------- INIT BOT ----------
bot = Client("bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# ============================================
# COMMAND: /start
# ============================================
@bot.on_message(filters.command("start"))
async def start_command(client, message: Message):
    await message.reply(
        "🎵 **Voice Bot**\n\n"
        "Main group voice chat mein gaana bajata hoon!\n\n"
        "📌 **Setup:**\n"
        "1. `/connect` - Assistant connect karo\n"
        "2. `/addgroup` - Public group add karo\n"
        "3. `/addprivate` - Private group add karo\n"
        "4. `/play` - Gaana play karo\n\n"
        "📖 **Help:** `/help`"
    )

# ============================================
# COMMAND: /help
# ============================================
@bot.on_message(filters.command("help"))
async def help_command(client, message: Message):
    help_text = """
🎵 **Voice Bot Commands**

━━━━━━━━━━━━━━━━━━━━
**🔧 Setup Commands**
`/connect <session>` - Assistant account connect
`/addgroup <link>` - Public group join
`/addprivate` - Private group join (link + chat_id)

━━━━━━━━━━━━━━━━━━━━
**🎵 Play Commands**
`/play <youtube_link>` - YouTube se play
`/play <search_query>` - Search karke play
`/play` (reply to audio) - Recording upload + play
`/upload` (reply to audio) - Recording save karo

━━━━━━━━━━━━━━━━━━━━
**🎮 Control Commands**
`/pause` - Pause karo
`/resume` - Resume karo
`/skip` - Skip karo
`/stop` - Stop karo

━━━━━━━━━━━━━━━━━━━━
**ℹ️ Info Commands**
`/status` - Group status
`/help` - Ye help menu

━━━━━━━━━━━━━━━━━━━━
**📌 Examples:**
`/play https://youtube.com/watch?v=xyz`
`/play Arijit Singh songs`
`/play` (reply to audio file)
    """
    await message.reply(help_text)

# ============================================
# COMMAND: /connect
# ============================================
@bot.on_message(filters.command("connect"))
async def connect_assistant(client, message: Message):
    try:
        session = message.text.split(maxsplit=1)[1]
        global assistant
        if assistant:
            await assistant.stop()
        
        # Create session folder
        os.makedirs("sessions", exist_ok=True)
        
        assistant = Client(
            "assistant",
            session_string=session,
            api_id=API_ID,
            api_hash=API_HASH,
            workdir="sessions/"
        )
        await assistant.start()
        
        # Get user info
        me = await assistant.get_me()
        await message.reply(f"✅ **Assistant Connected!**\n👤 {me.first_name}\n🆔 `{me.id}`")
    except IndexError:
        await message.reply("❌ Session string do!\nExample: `/connect session_string_here`")
    except Exception as e:
        await message.reply(f"❌ Error: {str(e)}")

# ============================================
# COMMAND: /addgroup (Public)
# ============================================
@bot.on_message(filters.command("addgroup"))
@require_assistant
async def add_public_group(client, message: Message):
    try:
        link = message.text.split(maxsplit=1)[1]
        await assistant.join_chat(link)
        chat = await assistant.get_chat(link)
        
        group_data[message.chat.id] = {
            "link": link,
            "chat_id": chat.id,
            "app": None,
            "recording": None,
            "title": chat.title
        }
        
        # Save chat_id in session
        await message.reply(
            f"✅ **Group Joined!**\n"
            f"📌 Title: {chat.title}\n"
            f"🆔 Chat ID: `{chat.id}`\n"
            f"👥 Members: {chat.members_count}"
        )
    except IndexError:
        await message.reply("❌ Group link do!\nExample: `/addgroup https://t.me/your_group`")
    except Exception as e:
        await message.reply(f"❌ Error: {str(e)}")

# ============================================
# COMMAND: /addprivate
# ============================================
@bot.on_message(filters.command("addprivate"))
@require_assistant
async def add_private_group(client, message: Message):
    try:
        await message.reply("📩 **Step 1:** Private group ka LINK bhejo")
        link_msg = await bot.wait_for_message(message.chat.id, timeout=60)
        link = link_msg.text
        
        await assistant.join_chat(link)
        chat = await assistant.get_chat(link)
        
        await message.reply(f"✅ Joined: {chat.title}\n\n🆗 **Step 2:** Ab CHAT_ID bhejo (number format mein)")
        id_msg = await bot.wait_for_message(message.chat.id, timeout=60)
        chat_id = int(id_msg.text)
        
        group_data[message.chat.id] = {
            "link": link,
            "chat_id": chat_id,
            "app": None,
            "recording": None,
            "title": chat.title
        }
        
        await message.reply(
            f"✅ **Private Group Added!**\n"
            f"📌 Title: {chat.title}\n"
            f"🆔 Chat ID: `{chat_id}`"
        )
    except asyncio.TimeoutError:
        await message.reply("⏰ Timeout! Process cancelled.")
    except Exception as e:
        await message.reply(f"❌ Error: {str(e)}")

# ============================================
# COMMAND: /upload
# ============================================
@bot.on_message(filters.command("upload"))
async def upload_recording(client, message: Message):
    if not message.reply_to_message:
        await message.reply("⚠️ Kisi audio file ko reply karo!\nExample: `/upload` (reply to audio)")
        return
    
    audio = message.reply_to_message.audio or message.reply_to_message.voice
    if not audio:
        await message.reply("❌ Ye audio file nahi hai! Audio/voice file reply karo.")
        return
    
    status = await message.reply("⬆️ Uploading recording...")
    try:
        file_path = await client.download_media(audio)
        global recording_file
        recording_file = file_path
        
        # Save in group data
        if message.chat.id in group_data:
            group_data[message.chat.id]["recording"] = file_path
        
        file_name = getattr(audio, 'file_name', 'audio')
        duration = getattr(audio, 'duration', 0)
        
        await status.edit(
            f"✅ **Recording Saved!**\n"
            f"📁 File: {file_name}\n"
            f"⏱️ Duration: {duration} sec\n"
            f"📂 Path: `{file_path}`\n\n"
            f"▶️ Play karne ke liye: `/play`"
        )
    except Exception as e:
        await status.edit(f"❌ Error: {str(e)}")

# ============================================
# COMMAND: /play (Main)
# ============================================
@bot.on_message(filters.command("play"))
@require_assistant
@require_group
async def play_command(client, message: Message):
    # ----- OPTION 1: Reply to audio -----
    if message.reply_to_message:
        audio = message.reply_to_message.audio or message.reply_to_message.voice
        if audio:
            await play_audio_reply(message, audio)
            return
    
    # ----- OPTION 2: YouTube link in message -----
    link = await extract_link(message)
    if link:
        await play_youtube(message, link)
        return
    
    # ----- OPTION 3: Search query -----
    query = message.text.split(maxsplit=1)
    if len(query) > 1:
        await play_search(message, query[1])
        return
    
    # ----- OPTION 4: Play uploaded recording -----
    if recording_file and os.path.exists(recording_file):
        status = await message.reply("🎵 Playing uploaded recording...")
        await play_audio(message.chat.id, recording_file, status)
    else:
        await message.reply(
            "❌ **Kuch toh bhejo!**\n\n"
            "🎵 **Options:**\n"
            "1. `/play https://youtube.com/...` - YouTube link\n"
            "2. `/play Arijit Singh` - Search karo\n"
            "3. `/play` (reply to audio) - Recording play\n"
            "4. Pehle `/upload` karo phir `/play`"
        )

# ============================================
# HELPER: Play Audio Reply
# ============================================
async def play_audio_reply(message, audio):
    status = await message.reply("⬆️ Uploading & Playing...")
    try:
        file_path = await bot.download_media(audio)
        global recording_file
        recording_file = file_path
        
        if message.chat.id in group_data:
            group_data[message.chat.id]["recording"] = file_path
        
        await status.edit("🎵 Playing recording in VC...")
        await play_audio(message.chat.id, file_path, status)
        
        file_name = getattr(audio, 'file_name', 'audio')
        await status.edit(f"▶️ **Now Playing:** {file_name}\n💬 Requested by: {message.from_user.mention}")
    except Exception as e:
        await status.edit(f"❌ Error: {str(e)}")

# ============================================
# HELPER: Play YouTube
# ============================================
async def play_youtube(message, link):
    status = await message.reply("⬇️ Downloading from YouTube...")
    try:
        file_path, success = await YouTube.download(link, message, songaudio=True)
        if not success:
            await status.edit("❌ Download failed! Invalid link?")
            return
        
        await status.edit("🎵 Playing in VC...")
        await play_audio(message.chat.id, file_path, status)
        
        # Show song details
        try:
            title, duration, _, _, _ = await YouTube.details(link)
            await status.edit(
                f"▶️ **Now Playing:** {title}\n"
                f"⏱️ Duration: {duration}\n"
                f"💬 Requested by: {message.from_user.mention}"
            )
        except:
            await status.edit("▶️ Playing in Voice Chat!")
    except Exception as e:
        await status.edit(f"❌ Error: {str(e)}")

# ============================================
# HELPER: Play Search
# ============================================
async def play_search(message, query):
    status = await message.reply(f"🔍 Searching: `{query}`")
    try:
        results = await YouTube.track(f"ytsearch:{query}")
        link = results[0]["link"]
        await status.edit(f"✅ Found: {results[0]['title']}\n⬇️ Downloading...")
        
        file_path, success = await YouTube.download(link, message, songaudio=True)
        if not success:
            await status.edit("❌ Download failed!")
            return
        
        await status.edit("🎵 Playing in VC...")
        await play_audio(message.chat.id, file_path, status)
        
        await status.edit(
            f"▶️ **Now Playing:** {results[0]['title']}\n"
            f"⏱️ Duration: {results[0]['duration_min']}\n"
            f"💬 Requested by: {message.from_user.mention}"
        )
    except Exception as e:
        await status.edit(f"❌ Error: {str(e)}")

# ============================================
# HELPER: Play Audio
# ============================================
async def play_audio(chat_id, file_path, status_msg=None):
    try:
        vc_chat_id = group_data[chat_id]["chat_id"]
        
        # Create or reuse app
        app = group_data[chat_id].get("app")
        if not app:
            app = PyTgCalls(assistant)
            await app.start()
            group_data[chat_id]["app"] = app
        
        # Join and play
        await app.join_call(vc_chat_id, AudioQuality.STUDIO)
        await app.play(file_path)
        
        if status_msg:
            await status_msg.edit("▶️ Playing...")
    except Exception as e:
        if status_msg:
            await status_msg.edit(f"❌ VC Error: {str(e)}")

# ============================================
# COMMAND: /pause
# ============================================
@bot.on_message(filters.command("pause"))
@require_group
async def pause_vc(client, message: Message):
    app = group_data[message.chat.id].get("app")
    if app:
        await app.pause()
        await message.reply("⏸️ **Paused**")
    else:
        await message.reply("❌ No active VC session")

# ============================================
# COMMAND: /resume
# ============================================
@bot.on_message(filters.command("resume"))
@require_group
async def resume_vc(client, message: Message):
    app = group_data[message.chat.id].get("app")
    if app:
        await app.resume()
        await message.reply("▶️ **Resumed**")
    else:
        await message.reply("❌ No active VC session")

# ============================================
# COMMAND: /skip
# ============================================
@bot.on_message(filters.command("skip"))
@require_group
async def skip_vc(client, message: Message):
    app = group_data[message.chat.id].get("app")
    if app:
        await app.skip()
        await message.reply("⏭️ **Skipped**")
    else:
        await message.reply("❌ No active VC session")

# ============================================
# COMMAND: /stop
# ============================================
@bot.on_message(filters.command("stop"))
@require_group
async def stop_vc(client, message: Message):
    app = group_data[message.chat.id].get("app")
    if app:
        try:
            await app.leave_call(group_data[message.chat.id]["chat_id"])
            group_data[message.chat.id]["app"] = None
            await message.reply("⏹️ **Stopped and left VC!**")
        except Exception as e:
            await message.reply(f"❌ Error: {str(e)}")
    else:
        await message.reply("❌ No active VC")

# ============================================
# COMMAND: /status
# ============================================
@bot.on_message(filters.command("status"))
@require_group
async def status_command(client, message: Message):
    data = group_data[message.chat.id]
    recording = "✅" if data.get("recording") and os.path.exists(data["recording"]) else "❌"
    vc = "✅" if data.get("app") else "❌"
    
    await message.reply(
        f"📊 **Group Status**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📌 Group: {data.get('title', 'Unknown')}\n"
        f"🆔 Chat ID: `{data['chat_id']}`\n"
        f"📼 Recording: {recording}\n"
        f"🎙️ VC Active: {vc}\n"
        f"🔗 Link: {data['link']}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📁 Recording Path: {data.get('recording', 'None')}"
    )

# ============================================
# COMMAND: /clear
# ============================================
@bot.on_message(filters.command("clear"))
async def clear_command(client, message: Message):
    """Clear downloaded files"""
    try:
        import shutil
        if os.path.exists("downloads"):
            shutil.rmtree("downloads")
            os.makedirs("downloads", exist_ok=True)
            await message.reply("🗑️ **Downloads cleared!**")
        else:
            await message.reply("❌ No downloads folder found")
    except Exception as e:
        await message.reply(f"❌ Error: {str(e)}")

# ============================================
# START BOT
# ============================================
async def main():
    # Create required folders
    os.makedirs("downloads", exist_ok=True)
    os.makedirs("sessions", exist_ok=True)
    
    # Start bot
    await bot.start()
    print("=" * 50)
    print("🤖 Voice Bot Started Successfully!")
    print("=" * 50)
    print("📌 Commands:")
    print("  /connect <session> - Connect assistant")
    print("  /addgroup <link> - Add public group")
    print("  /addprivate - Add private group")
    print("  /upload - Upload recording")
    print("  /play - Play audio")
    print("  /pause /resume /skip /stop - Controls")
    print("  /status - Check status")
    print("  /help - Help menu")
    print("=" * 50)
    
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
