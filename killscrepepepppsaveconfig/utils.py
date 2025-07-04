"""
Utility functions for Discord Mass DM Script
"""

import json
import logging
import os
from typing import List, Dict, Any
from datetime import datetime


def setup_logging() -> logging.Logger:
    """Setup logging configuration"""
    # Create logs directory if it doesn't exist
    os.makedirs("logs", exist_ok=True)

    # Setup logging
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = f"logs/discord_mass_dm_{timestamp}.log"

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_filename),
            logging.StreamHandler()
        ]
    )

    logger = logging.getLogger(__name__)
    logger.info("="*50)
    logger.info("Discord Mass DM Script Started")
    logger.info("="*50)

    return logger

def load_config() -> Dict[str, Any]:
    """Load configuration from config.json"""
    default_config = {
        "min_delay": 2.0,
        "max_delay": 8.0,
        "rate_limit_delay": 30.0,
        "max_retries": 3,
        "discord_webhook_url": ""  # Add webhook URL to config
    }

    try:
        if os.path.exists("config.json"):
            with open("config.json", "r") as f:
                config = json.load(f)
                # Merge with defaults
                for key, value in default_config.items():
                    if key not in config:
                        config[key] = value
                return config
        else:
            # Create default config file
            save_config(default_config)
            return default_config

    except Exception as e:
        print(f"⚠️  Error loading config: {e}. Using defaults.")
        return default_config

def save_config(config: Dict[str, Any]) -> bool:
    """Save configuration to config.json"""
    try:
        with open("config.json", "w") as f:
            json.dump(config, f, indent=4)
        return True
    except Exception as e:
        print(f"⚠️  Error saving config: {e}")
        return False

def parse_users_file(filename: str) -> List[str]:
    """Parse users from text file"""
    users = []

    try:
        if not os.path.exists(filename):
            return users

        with open(filename, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):  # Skip empty lines and comments
                    users.append(line)

        return users

    except Exception as e:
        print(f"⚠️  Error reading {filename}: {e}")
        return []

def validate_user_id(user_id: str) -> bool:
    """Validate if string is a valid Discord user ID"""
    try:
        # Discord IDs are 17-19 digit numbers
        id_int = int(user_id)
        return 10**16 <= id_int <= 10**19
    except ValueError:
        return False

def sanitize_message(message: str) -> str:
    """Sanitize message content"""
    # Remove potential Discord markdown that might cause issues
    # This is a basic sanitization - add more as needed
    message = message.replace("@everyone", "@‌everyone")
    message = message.replace("@here", "@‌here")

    # Limit message length (Discord limit is 2000 characters)
    if len(message) > 2000:
        message = message[:1997] + "..."

    return message

def format_duration(seconds: float) -> str:
    """Format duration in human readable format"""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}m"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}h"

def create_backup_file(users: List[str], message: str) -> str:
    """Create backup file with users and message"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"backup_mass_dm_{timestamp}.json"

    backup_data = {
        "timestamp": timestamp,
        "users": users,
        "message": message,
        "total_users": len(users)
    }

    try:
        with open(backup_filename, "w") as f:
            json.dump(backup_data, f, indent=4)
        return backup_filename
    except Exception as e:
        print(f"⚠️  Could not create backup file: {e}")
        return ""

