import os
import asyncio
from typing import Optional, Dict
from pyrogram.types import Message
from pyrogram.enums import MessageEntityType

# ---------- STORAGE ----------
group_data: Dict[int, dict] = {}
recording_file: Optional[str] = None
assistant = None

# ---------- HELPERS ----------
async def extract_link(message: Message) -> Optional[str]:
    """Extract YouTube link from message"""
    link = None
    
    # Check current message
    if message.entities:
        for entity in message.entities:
            if entity.type in [MessageEntityType.URL, MessageEntityType.TEXT_LINK]:
                text = message.text or message.caption
                link = text[entity.offset:entity.offset + entity.length]
                break
    
    # Check replied message
    if not link and message.reply_to_message:
        reply = message.reply_to_message
        if reply.entities:
            for entity in reply.entities:
                if entity.type in [MessageEntityType.URL, MessageEntityType.TEXT_LINK]:
                    text = reply.text or reply.caption
                    link = text[entity.offset:entity.offset + entity.length]
                    break
    
    return link

def get_download_path(filename: str) -> str:
    """Get download path for file"""
    os.makedirs("downloads", exist_ok=True)
    return os.path.join("downloads", filename)

def clean_filename(filename: str) -> str:
    """Clean filename for saving"""
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '')
    return filename[:100]  # Limit length

async def format_time(seconds: int) -> str:
    """Convert seconds to MM:SS format"""
    minutes = seconds // 60
    seconds = seconds % 60
    return f"{minutes:02d}:{seconds:02d}"

# ---------- DECORATORS ----------
def require_assistant(func):
    """Decorator to check if assistant is connected"""
    async def wrapper(client, message):
        global assistant
        if not assistant:
            await message.reply("⚠️ Pehle `/connect` karo!")
            return
        return await func(client, message)
    return wrapper

def require_group(func):
    """Decorator to check if group is added"""
    async def wrapper(client, message):
        if message.chat.id not in group_data:
            await message.reply("❌ Pehle group add karo (`/addgroup` ya `/addprivate`)")
            return
        return await func(client, message)
    return wrapper
