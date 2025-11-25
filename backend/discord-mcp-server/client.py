import asyncio
import os
import sys
import json
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

load_dotenv()


class DiscordMCPClient:
    def __init__(self):
        self.discord_token = os.getenv("DISCORD_TOKEN")
        if not self.discord_token:
            raise ValueError("DISCORD_TOKEN is required in .env file")
        
        self.default_guild_id = os.getenv("DEFAULT_GUILD_ID")
        self.session: Optional[ClientSession] = None
        self._stdio_context = None
        self._session_context = None
        self._read = None
        self._write = None

    async def connect(self):
        """Connect to the Discord MCP server"""
        server_script = os.path.join(os.getcwd(), "server.py")
        
        # Prepare environment variables
        env = os.environ.copy()
        env["DISCORD_TOKEN"] = self.discord_token
        if self.default_guild_id:
            env["DEFAULT_GUILD_ID"] = self.default_guild_id
        
        server_params = StdioServerParameters(
            command=sys.executable,
            args=[server_script],
            env=env
        )
        
        self._stdio_context = stdio_client(server_params)
        self._read, self._write = await self._stdio_context.__aenter__()
        self._session_context = ClientSession(self._read, self._write)
        self.session = await self._session_context.__aenter__()
        await self.session.initialize()
        print("✓ Connected to Discord MCP Server")

    async def disconnect(self):
        """Disconnect from the Discord MCP server"""
        if self.session:
            await self._session_context.__aexit__(None, None, None)
            await self._stdio_context.__aexit__(None, None, None)
            print("✓ Disconnected from Discord MCP Server")

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, *args):
        await self.disconnect()

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Call a tool on the Discord MCP server"""
        try:
            return await self.session.call_tool(tool_name, arguments)
        except Exception as e:
            print(f"Error calling {tool_name}: {e}")
            return None

    def safe_parse(self, result, source_name="Unknown"):
        """Safely parse the result from the MCP server"""
        if not result or not result.content:
            return None
        
        raw_text = result.content[0].text.strip()
        if not raw_text:
            return None
        
        try:
            return json.loads(raw_text.replace("'", '"'))
        except json.JSONDecodeError:
            print(f"{source_name} returned text: \"{raw_text}\"")
            return raw_text

    # Discord-specific methods
    
    async def send_message(self, channel_id: str, content: str, guild_id: str = None) -> Dict:
        """Send a message to a Discord channel"""
        arguments = {
            "channel_id": channel_id,
            "content": content
        }
        if guild_id:
            arguments["guild_id"] = guild_id
        
        result = await self.call_tool("send_message", arguments)
        return self.safe_parse(result, "send_message")

    async def read_messages(self, channel_id: str, limit: int = 10, guild_id: str = None) -> List[Dict]:
        """Read recent messages from a Discord channel"""
        arguments = {
            "channel_id": channel_id,
            "limit": limit
        }
        if guild_id:
            arguments["guild_id"] = guild_id
        
        result = await self.call_tool("read_messages", arguments)
        return self.safe_parse(result, "read_messages")

    async def edit_message(self, channel_id: str, message_id: str, new_content: str, guild_id: str = None) -> Dict:
        """Edit a message in a Discord channel"""
        arguments = {
            "channel_id": channel_id,
            "message_id": message_id,
            "new_content": new_content
        }
        if guild_id:
            arguments["guild_id"] = guild_id
        
        result = await self.call_tool("edit_message", arguments)
        return self.safe_parse(result, "edit_message")

    async def delete_message(self, channel_id: str, message_id: str, guild_id: str = None) -> Dict:
        """Delete a message from a Discord channel"""
        arguments = {
            "channel_id": channel_id,
            "message_id": message_id
        }
        if guild_id:
            arguments["guild_id"] = guild_id
        
        result = await self.call_tool("delete_message", arguments)
        return self.safe_parse(result, "delete_message")

    async def send_private_message(self, user_id: str, content: str) -> Dict:
        """Send a private/direct message to a Discord user"""
        arguments = {
            "user_id": user_id,
            "content": content
        }
        
        result = await self.call_tool("send_private_message", arguments)
        return self.safe_parse(result, "send_private_message")

    async def get_server_info(self, guild_id: str = None) -> Dict:
        """Get information about a Discord server/guild"""
        arguments = {}
        if guild_id:
            arguments["guild_id"] = guild_id
        
        result = await self.call_tool("get_server_info", arguments)
        return self.safe_parse(result, "get_server_info")

    async def get_user_id_by_name(self, username: str, guild_id: str = None) -> Dict:
        """Get a user's ID by their username"""
        arguments = {
            "username": username
        }
        if guild_id:
            arguments["guild_id"] = guild_id
        
        result = await self.call_tool("get_user_id_by_name", arguments)
        return self.safe_parse(result, "get_user_id_by_name")

    async def list_channels(self, guild_id: str = None) -> List[Dict]:
        """List all channels in a Discord server/guild"""
        arguments = {}
        if guild_id:
            arguments["guild_id"] = guild_id
        
        result = await self.call_tool("list_channels", arguments)
        return self.safe_parse(result, "list_channels")


async def main():
    """Example usage of the Discord MCP Client"""
    
    # Configuration - replace with your actual IDs
    TARGET_GUILD_ID = os.getenv("DEFAULT_GUILD_ID")  # Your Discord server ID
    TARGET_CHANNEL_ID = "YOUR_CHANNEL_ID"  # Your Discord channel ID
    
    async with DiscordMCPClient() as client:
        print("\n=== Discord MCP Client Demo ===\n")
        
        # 1. Get server information
        print("--- 1. SERVER INFO ---")
        server_info = await client.get_server_info(TARGET_GUILD_ID)
        if isinstance(server_info, dict) and server_info.get('success'):
            data = server_info.get('data', {})
            print(f"Server Name: {data.get('name')}")
            print(f"Members: {data.get('member_count')}")
            print(f"Server ID: {data.get('id')}\n")
        else:
            print(f"Error: {server_info}\n")
        
        # 2. List all channels
        print("--- 2. CHANNELS LIST ---")
        channels = await client.list_channels(TARGET_GUILD_ID)
        if isinstance(channels, dict) and channels.get('success'):
            channel_list = channels.get('data', {}).get('channels', [])
            print(f"Found {len(channel_list)} channels:")
            for channel in channel_list[:5]:  # Show first 5 channels
                print(f"  #{channel.get('name')} (ID: {channel.get('id')}) - Type: {channel.get('type')}")
            print()
        else:
            print(f"Error: {channels}\n")
        
        # 3. Read recent messages from a channel
        print(f"--- 3. RECENT MESSAGES ---")
        messages = await client.read_messages(TARGET_CHANNEL_ID, limit=5, guild_id=TARGET_GUILD_ID)
        if isinstance(messages, dict) and messages.get('success'):
            message_list = messages.get('data', {}).get('messages', [])
            print(f"Found {len(message_list)} recent messages:")
            for msg in message_list:
                author = msg.get('author', {}).get('username', 'Unknown')
                content = msg.get('content', '')[:50]  # First 50 chars
                print(f"  {author}: {content}...")
            print()
        else:
            print(f"Error: {messages}\n")
        
        # 4. Send a message
        print("--- 4. SEND MESSAGE ---")
        message_result = await client.send_message(
            channel_id=TARGET_CHANNEL_ID,
            content="Hello from Discord MCP Client! 👋",
            guild_id=TARGET_GUILD_ID
        )
        if isinstance(message_result, dict) and message_result.get('success'):
            print(f"✓ Message sent successfully!")
            print(f"  Message ID: {message_result.get('data', {}).get('message_id')}\n")
        else:
            print(f"Error: {message_result}\n")
        
        # 5. Get user ID by username
        print("--- 5. USER LOOKUP ---")
        username_to_find = "Amar"
        user_result = await client.get_user_id_by_name(username_to_find, TARGET_GUILD_ID)
        if isinstance(user_result, dict) and user_result.get('success'):
            user_data = user_result.get('data', {})
            print(f"Found user: {user_data.get('username')}")
            print(f"User ID: {user_data.get('user_id')}\n")
        else:
            print(f"User not found or error: {user_result}\n")


if __name__ == "__main__":
    asyncio.run(main())