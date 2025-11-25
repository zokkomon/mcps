from typing import Dict, Any, Optional
from discord.ext import commands

class ServerService:
    """Service for handling Discord server/guild operations"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    async def get_server_info(self, guild_id: str) -> Dict[str, Any]:
        try:
            guild = self.bot.get_guild(int(guild_id))
            
            if not guild:
                return {
                    "success": False,
                    "error": f"Guild {guild_id} not found"
                }
            
            return {
                "success": True,
                "guild": {
                    "id": str(guild.id),
                    "name": guild.name,
                    "description": guild.description,
                    "member_count": guild.member_count,
                    "owner_id": str(guild.owner_id),
                    "created_at": guild.created_at.isoformat(),
                    "icon_url": str(guild.icon.url) if guild.icon else None,
                    "channels_count": len(guild.channels),
                    "roles_count": len(guild.roles),
                    "boost_level": guild.premium_tier,
                    "boost_count": guild.premium_subscription_count
                }
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_user_id_by_name(
        self,
        guild_id: str,
        username: str
    ) -> Dict[str, Any]:
        try:
            guild = self.bot.get_guild(int(guild_id))
            
            if not guild:
                return {
                    "success": False,
                    "error": f"Guild {guild_id} not found"
                }
            
            # Search for member by name
            member = None
            for m in guild.members:
                if m.name == username or m.display_name == username:
                    member = m
                    break
            
            if not member:
                return {
                    "success": False,
                    "error": f"User '{username}' not found in guild"
                }
            
            return {
                "success": True,
                "user": {
                    "id": str(member.id),
                    "username": member.name,
                    "discriminator": member.discriminator,
                    "display_name": member.display_name,
                    "mention": f"<@{member.id}>"
                }
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }