from mcp.server.fastmcp import FastMCP, Context
from config.settings import settings
from utils.discord_client import DiscordClientManager
from services.message_service import MessageService
from services.server_service import ServerService
from services.channel_service import ChannelService
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from dataclasses import dataclass
import logging
import asyncio

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

discord_manager: DiscordClientManager = None
discord_task = None

@dataclass
class AppContext:
    """Application context with Discord services"""
    message_service: MessageService
    server_service: ServerService
    channel_service: ChannelService

@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[AppContext]:
    """Manage Discord client lifecycle"""
    global discord_manager, discord_task
    
    logger.info("Starting Discord MCP Server initialization...")
    
    if not settings.discord_token:
        raise ValueError("DISCORD_TOKEN environment variable is required")
    
    # Initialize Discord
    discord_manager = DiscordClientManager(settings.discord_token)
    discord_task = asyncio.create_task(discord_manager.start())
    
    bot = discord_manager.get_client()
    try:
        await asyncio.wait_for(bot.wait_until_ready(), timeout=30.0)
        logger.info("Discord bot is ready")
    except asyncio.TimeoutError:
        logger.error("Discord bot failed to become ready within 30 seconds")
        discord_task.cancel()
        raise
    
    message_service = MessageService(bot)
    server_service = ServerService(bot)
    channel_service = ChannelService(bot)
    
    logger.info("Discord services initialized successfully")
    
    try:
        yield AppContext(
            message_service=message_service,
            server_service=server_service,
            channel_service=channel_service
        )
    finally:
        # Cleanup when server shuts down
        logger.info("Shutting down Discord services...")
        if discord_manager:
            await discord_manager.stop()
        if discord_task and not discord_task.done():
            discord_task.cancel()
            try:
                await discord_task
            except asyncio.CancelledError:
                pass

# Initialize MCP server with lifespan
mcp = FastMCP("discord-mcp-server", lifespan=app_lifespan)

@mcp.tool()
async def send_message(
    ctx: Context,
    channel_id: str,
    content: str,
    guild_id: str = None
) -> str:
    """Send a message to a Discord channel"""
    guild_id = guild_id or settings.default_guild_id
    message_service = ctx.request_context.lifespan_context.message_service
    result = await message_service.send_message(channel_id, content, guild_id)
    return str(result)

@mcp.tool()
async def read_messages(
    ctx: Context,
    channel_id: str,
    limit: int = 10,
    guild_id: str = None
) -> str:
    """Read recent messages from a Discord channel"""
    guild_id = guild_id or settings.default_guild_id
    message_service = ctx.request_context.lifespan_context.message_service
    result = await message_service.read_messages(channel_id, limit, guild_id)
    return str(result)

@mcp.tool()
async def edit_message(
    ctx: Context,
    channel_id: str,
    message_id: str,
    new_content: str,
    guild_id: str = None
) -> str:
    """Edit a message in a Discord channel"""
    guild_id = guild_id or settings.default_guild_id
    message_service = ctx.request_context.lifespan_context.message_service
    result = await message_service.edit_message(channel_id, message_id, new_content, guild_id)
    return str(result)

@mcp.tool()
async def delete_message(
    ctx: Context,
    channel_id: str,
    message_id: str,
    guild_id: str = None
) -> str:
    """Delete a message from a Discord channel"""
    guild_id = guild_id or settings.default_guild_id
    message_service = ctx.request_context.lifespan_context.message_service
    result = await message_service.delete_message(channel_id, message_id, guild_id)
    return str(result)

@mcp.tool()
async def send_private_message(
    ctx: Context,
    user_id: str,
    content: str
) -> str:
    """Send a private/direct message to a Discord user"""
    message_service = ctx.request_context.lifespan_context.message_service
    result = await message_service.send_private_message(user_id, content)
    return str(result)

@mcp.tool()
async def get_server_info(ctx: Context, guild_id: str = None) -> str:
    """Get information about a Discord server/guild"""
    guild_id = guild_id or settings.default_guild_id
    if not guild_id:
        return str({"success": False, "error": "Guild ID is required"})
    
    server_service = ctx.request_context.lifespan_context.server_service
    result = await server_service.get_server_info(guild_id)
    return str(result)

@mcp.tool()
async def get_user_id_by_name(
    ctx: Context,
    username: str,
    guild_id: str = None
) -> str:
    """Get a user's ID by their username"""
    guild_id = guild_id or settings.default_guild_id
    if not guild_id:
        return str({"success": False, "error": "Guild ID is required"})
    
    server_service = ctx.request_context.lifespan_context.server_service
    result = await server_service.get_user_id_by_name(guild_id, username)
    return str(result)

@mcp.tool()
async def list_channels(ctx: Context, guild_id: str = None) -> str:
    """List all channels in a Discord server/guild"""
    guild_id = guild_id or settings.default_guild_id
    if not guild_id:
        return str({"success": False, "error": "Guild ID is required"})
    
    channel_service = ctx.request_context.lifespan_context.channel_service
    result = await channel_service.list_channels(guild_id)
    return str(result)

if __name__ == "__main__":
    mcp.run()