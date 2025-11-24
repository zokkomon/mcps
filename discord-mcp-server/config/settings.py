import os
from typing import Optional
from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()

class Settings(BaseModel):
    discord_token: str
    default_guild_id: Optional[str] = None
    
    class Config:
        env_file = ".env"

    @classmethod
    def from_env(cls):
        return cls(
            discord_token=os.getenv("DISCORD_TOKEN", ""),
            default_guild_id=os.getenv("DISCORD_GUILD_ID")
        )

settings = Settings.from_env()