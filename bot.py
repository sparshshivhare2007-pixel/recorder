import os
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.enums import MessageEntityType
from pytgcalls import PyTgCalls
from pytgcalls.types import AudioQuality
from youtube import YouTube  # Aapka YouTube module

# ---------- CONFIG ----------
API_ID = 123456
API_HASH = "your_api_hash"
BOT_TOKEN = "your_bot_token"

# Storage
group_data = {}  # {chat_id: {"link": "...", "chat_id": 123, "app": None, "recording": None}}
assistant = None
recording_file = None  # Latest uploaded recording

# ---------- BOT ----------
bot = Client("bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# ============================================
# 1. ASSISTANT CONNECT
# ============================================
@bot.on_message(filters.command("connect"))
async def connect_assistant(client, message: Message):
    try:
        session = message.text.split(maxsplit=1)[1]
        global assistant
        if assistant:
            await assistant.stop()
        assistant = Client("assistant", session_string=session, api_id=API_ID, api_hash=API_HASH)
        await assistant.start()
        await message.reply("✅ Assistant connected successfully!")
    except Exception as e:
        await message.reply(f"❌ Error: {str(e)}")

# ============================================
# 2. ADD GROUP (PUBLIC)
# ============================================
@bot.on_message(filters.command("addgroup"))
async def add_public_group(client, message: Message):
    if not assistant:
        await message.reply("⚠️ Pehle /connect karo")
        return
    try:
        link = message.text.split(maxsplit=1)[1]
        await assistant.join_chat(link)
        chat = await assistant.get_chat(link)
        
        group_data[message.chat.id] = {
            "link": link,
            "chat_id": chat.id,
            "app": None,
            "recording": None
        }
        await message.reply(f"✅ Joined group: {chat.title}")
    except Exception as e:
        await message.reply(f"❌ Error: {str(e)}")

# ============================================
# 3. ADD GROUP (PRIVATE)
# ============================================
@bot.on_message(filters.command("addprivate"))
async def add_private_group(client, message: Message):
    if not assistant:
        await message.reply("⚠️ Pehle /connect karo")
        return
    try:
        await message.reply("📩 Private group ka LINK bhejo")
        link_msg = await bot.wait_for_message(message.chat.id, timeout=30)
        link = link_msg.text
        await assistant.join_chat(link)
        
        await message.reply("🆗 Ab CHAT_ID bhejo (number)")
        id_msg = await bot.wait_for_message(message.chat.id, timeout=30)
        chat_id = int(id_msg.text)
        
        group_data[message.chat.id] = {
            "link": link,
            "chat_id": chat_id,
            "app": None,
            "recording": None
        }
        await message.reply("✅ Private group added successfully!")
    except Exception as e:
        await message.reply(f"❌ Error: {str(e)}")

# ============================================
# 4. UPLOAD RECORDING
# ============================================
@bot.on_message(filters.command("upload"))
async def upload_recording(client, message: Message):
    if not message.reply_to_message:
        await message.reply("⚠️ Kisi audio file ko reply karo: `/upload`")
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
        
        await status.edit(f"✅ Recording saved: {audio.file_name if hasattr(audio, 'file_name') else 'audio'}")
    except Exception as e:
        await status.edit(f"❌ Error: {str(e)}")

# ============================================
# 5. PLAY COMMAND (YouTube + Recording + Search)
# ============================================
@bot.on_message(filters.command("play"))
async def play_command(client, message: Message):
    if not assistant:
        await message.reply("⚠️ Pehle /connect karo")
        return
    
    if message.chat.id not in group_data:
        await message.reply("❌ Pehle group add karo (/addgroup ya /addprivate)")
        return
    
    # ---- CHECK: Reply to audio file? ----
    if message.reply_to_message:
        audio = message.reply_to_message.audio or message.reply_to_message.voice
        if audio:
            # Upload karo aur play karo
            status = await message.reply("⬆️ Uploading & Playing recording...")
            try:
                file_path = await client.download_media(audio)
                global recording_file
                recording_file = file_path
                group_data[message.chat.id]["recording"] = file_path
                
                await status.edit("🎵 Playing recording in VC...")
                await play_audio(message.chat.id, file_path, status)
                return
            except Exception as e:
                await status.edit(f"❌ Error: {str(e)}")
                return
    
    # ---- CHECK: YouTube link in message ----
    link = None
    # Check current message
    if message.entities:
        for entity in message.entities:
            if entity.type in [MessageEntityType.URL, MessageEntityType.TEXT_LINK]:
                text = message.text or message.caption
                link = text[entity.offset:entity.offset + entity.length]
                break
    
    if link:
        await play_youtube(message, link)
        return
    
    # ---- CHECK: Search query ----
    query = message.text.split(maxsplit=1)
    if len(query) > 1:
        await play_search(message, query[1])
        return
    
    # ---- LAST OPTION: Play uploaded recording ----
    if recording_file and os.path.exists(recording_file):
        status = await message.reply("🎵 Playing uploaded recording...")
        await play_audio(message.chat.id, recording_file, status)
    else:
        await message.reply(
            "❌ Kuch toh bhejo!\n\n"
            "🎵 **Options:**\n"
            "1. `/play https://youtube.com/...` - YouTube link\n"
            "2. `/play Arijit Singh` - Search karo\n"
            "3. `/play` (reply to audio) - Recording play\n"
            "4. Pehle `/upload` karo phir `/play`"
        )

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
        
        await status.edit("🎵 Playing YouTube in VC...")
        await play_audio(message.chat.id, file_path, status)
        
        # Show song details
        try:
            title, duration, _, _, _ = await YouTube.details(link)
            await status.edit(f"▶️ **Now Playing:** {title}\n⏱️ Duration: {duration}\n💬 Requested by: {message.from_user.mention}")
        except:
            pass
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
        
        await status.edit(f"▶️ **Now Playing:** {results[0]['title']}\n⏱️ Duration: {results[0]['duration_min']}\n💬 Requested by: {message.from_user.mention}")
    except Exception as e:
        await status.edit(f"❌ Error: {str(e)}")

# ============================================
# HELPER: Play Audio in VC
# ============================================
async def play_audio(chat_id, file_path, status_msg=None):
    try:
        # Get VC chat ID
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
# 6. STOP
# ============================================
@bot.on_message(filters.command("stop"))
async def stop_vc(client, message: Message):
    if message.chat.id not in group_data:
        await message.reply("❌ No active group")
        return
    
    app = group_data[message.chat.id].get("app")
    if app:
        try:
            await app.leave_call(group_data[message.chat.id]["chat_id"])
            await message.reply("⏹️ Stopped and left VC!")
        except Exception as e:
            await message.reply(f"❌ Error: {str(e)}")
    else:
        await message.reply("❌ No active VC")

# ============================================
# 7. PAUSE / RESUME / SKIP
# ============================================
@bot.on_message(filters.command("pause"))
async def pause_vc(client, message: Message):
    app = group_data.get(message.chat.id, {}).get("app")
    if app:
        await app.pause()
        await message.reply("⏸️ Paused")

@bot.on_message(filters.command("resume"))
async def resume_vc(client, message: Message):
    app = group_data.get(message.chat.id, {}).get("app")
    if app:
        await app.resume()
        await message.reply("▶️ Resumed")

@bot.on_message(filters.command("skip"))
async def skip_vc(client, message: Message):
    app = group_data.get(message.chat.id, {}).get("app")
    if app:
        await app.skip()
        await message.reply("⏭️ Skipped")

# ============================================
# 8. STATUS
# ============================================
@bot.on_message(filters.command("status"))
async def status_command(client, message: Message):
    if message.chat.id not in group_data:
        await message.reply("❌ No group added")
        return
    
    data = group_data[message.chat.id]
    recording = "✅" if data.get("recording") and os.path.exists(data["recording"]) else "❌"
    vc = "✅" if data.get("app") else "❌"
    
    await message.reply(
        f"📊 **Group Status**\n"
        f"━━━━━━━━━━━━━━\n"
        f"🆔 Chat ID: `{data['chat_id']}`\n"
        f"📼 Recording: {recording}\n"
        f"🎙️ VC Active: {vc}\n"
        f"🔗 Link: {data['link']}"
    )

# ============================================
# START
# ============================================
async def main():
    await bot.start()
    print("🤖 Bot is running!")
    print("📌 Commands:")
    print("  /connect <session>")
    print("  /addgroup <link>")
    print("  /addprivate")
    print("  /upload (reply to audio)")
    print("  /play <link/search/reply>")
    print("  /pause /resume /skip /stop")
    await asyncio.Event().wait()

asyncio.run(main())
