from typing import Optional, List, Dict, Any
import discord
from discord.ext import commands

class MessageService:
    """Service for handling Discord message operations"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    async def send_message(
        self,
        channel_id: str,
        content: str,
        guild_id: Optional[str] = None
    ) -> Dict[str, Any]:
        try:
            channel = self.bot.get_channel(int(channel_id))
            
            if not channel:
                if guild_id:
                    guild = self.bot.get_guild(int(guild_id))
                    if guild:
                        channel = guild.get_channel(int(channel_id))
            
            if not channel:
                return {
                    "success": False,
                    "error": f"Channel {channel_id} not found"
                }
            
            message = await channel.send(content)
            
            return {
                "success": True,
                "message_id": str(message.id),
                "channel_id": str(message.channel.id),
                "content": message.content,
                "author": str(message.author),
                "timestamp": message.created_at.isoformat()
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def read_messages(
        self,
        channel_id: str,
        limit: int = 10,
        guild_id: Optional[str] = None
    ) -> Dict[str, Any]:
        try:
            channel = self.bot.get_channel(int(channel_id))
            
            if not channel:
                if guild_id:
                    guild = self.bot.get_guild(int(guild_id))
                    if guild:
                        channel = guild.get_channel(int(channel_id))
            
            if not channel:
                return {
                    "success": False,
                    "error": f"Channel {channel_id} not found"
                }
            
            messages = []
            async for message in channel.history(limit=limit):
                messages.append({
                    "id": str(message.id),
                    "content": message.content,
                    "author": {
                        "id": str(message.author.id),
                        "name": message.author.name,
                        "discriminator": message.author.discriminator
                    },
                    "timestamp": message.created_at.isoformat(),
                    "attachments": [att.url for att in message.attachments]
                })
            
            return {
                "success": True,
                "channel_id": channel_id,
                "messages": messages,
                "count": len(messages)
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def edit_message(
        self,
        channel_id: str,
        message_id: str,
        new_content: str,
        guild_id: Optional[str] = None
    ) -> Dict[str, Any]:
        try:
            channel = self.bot.get_channel(int(channel_id))
            
            if not channel:
                if guild_id:
                    guild = self.bot.get_guild(int(guild_id))
                    if guild:
                        channel = guild.get_channel(int(channel_id))
            
            if not channel:
                return {
                    "success": False,
                    "error": f"Channel {channel_id} not found"
                }
            
            message = await channel.fetch_message(int(message_id))
            await message.edit(content=new_content)
            
            return {
                "success": True,
                "message_id": str(message.id),
                "new_content": new_content,
                "edited_at": message.edited_at.isoformat() if message.edited_at else None
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def delete_message(
        self,
        channel_id: str,
        message_id: str,
        guild_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Delete a message from a Discord channel"""
        try:
            channel = self.bot.get_channel(int(channel_id))
            
            if not channel:
                if guild_id:
                    guild = self.bot.get_guild(int(guild_id))
                    if guild:
                        channel = guild.get_channel(int(channel_id))
            
            if not channel:
                return {
                    "success": False,
                    "error": f"Channel {channel_id} not found"
                }
            
            message = await channel.fetch_message(int(message_id))
            await message.delete()
            
            return {
                "success": True,
                "message_id": message_id,
                "deleted": True
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def send_private_message(
        self,
        user_id: str,
        content: str
    ) -> Dict[str, Any]:
        try:
            user = await self.bot.fetch_user(int(user_id))
            
            if not user:
                return {
                    "success": False,
                    "error": f"User {user_id} not found"
                }
            
            message = await user.send(content)
            
            return {
                "success": True,
                "message_id": str(message.id),
                "user_id": user_id,
                "content": content,
                "timestamp": message.created_at.isoformat()
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }