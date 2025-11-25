from typing import Dict, Any, List
from discord.ext import commands

class ChannelService:
    """Service for handling Discord channel operations"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    async def list_channels(self, guild_id: str) -> Dict[str, Any]:
        """List all channels in a Discord server"""
        try:
            guild = self.bot.get_guild(int(guild_id))
            
            if not guild:
                return {
                    "success": False,
                    "error": f"Guild {guild_id} not found"
                }
            
            channels = []
            for channel in guild.channels:
                channel_info = {
                    "id": str(channel.id),
                    "name": channel.name,
                    "type": str(channel.type),
                    "position": channel.position
                }
                
                if hasattr(channel, 'category'):
                    channel_info["category"] = channel.category.name if channel.category else None
                
                channels.append(channel_info)
            
            return {
                "success": True,
                "guild_id": guild_id,
                "channels": channels,
                "count": len(channels)
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }