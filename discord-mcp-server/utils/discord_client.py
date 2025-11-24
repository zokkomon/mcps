import discord
from discord.ext import commands
from typing import Optional
import asyncio
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DiscordClientManager:
    """Manages Discord bot client connection and state"""
    
    def __init__(self, token: str):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        intents.members = True
        intents.presences = False  

        self.bot = commands.Bot(command_prefix='!', intents=intents)
        self.token = token
        self._ready = asyncio.Event()
        
        @self.bot.event
        async def on_ready():
            logger.info(f'Bot connected as {self.bot.user}')
            self._ready.set()
    
    async def start(self):
        await self.bot.start(self.token)
        logger.info("Discord bot is ready")
    
    async def stop(self):
        await self.bot.close()
    
    def get_client(self) -> commands.Bot:
        return self.bot
    
    async def wait_until_ready(self):
        await self._ready.wait()