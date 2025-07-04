# Discord Mass DM Script

## Overview

This Python script allows you to send announcement DMs to multiple Discord users using your personal account. It includes rate limiting, error handling, and logging to minimize the risk of detection.

## Features

- 🔐 Secure token handling (environment variables or secure input)
- 👥 Support for both user IDs and usernames
- ⏱️ Intelligent rate limiting to mimic human behavior
- 📊 Comprehensive logging and error handling
- 🎯 Success/failure tracking with statistics
- 📝 Flexible user input methods (file or manual entry)
- 🛡️ Built-in safety delays and warnings

## Installation

1. **Install Python 3.7+**

2. **Install required packages:**
   ```bash
   pip install discord.py-self
   ```

3. **Download the script files:**
   - `main.py` - Main script
   - `utils.py` - Utility functions
   - `config.json` - Configuration file
   - `users.txt` - Users list template

## Configuration

### config.json
```json
{
    "min_delay": 2.0,        // Minimum delay between messages (seconds)
    "max_delay": 8.0,        // Maximum delay between messages (seconds)
    "rate_limit_delay": 30.0, // Delay when rate limited (seconds)
    "max_retries": 3,        // Maximum retry attempts
    "backup_enabled": true,  // Create backup files
    "log_level": "INFO"      // Logging level
}
