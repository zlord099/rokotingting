# Discord OAuth Setup Guide

To enable Discord server membership authentication for the Discord Scanner, you need to configure a Discord OAuth application.

## Step 1: Create Discord Application

1. Go to https://discord.com/developers/applications
2. Click "New Application"
3. Give it a name (e.g., "Discord Scanner")
4. Click "Create"

## Step 2: Configure OAuth2

1. In your application, go to "OAuth2" → "General"
2. Copy the **Client ID**
3. Copy the **Client Secret** (click "Reset Secret" if needed)
4. Add this redirect URI: `http://localhost:5000/auth/callback`
   - For production/Replit: Use your Replit URL like `https://yourapp.replit.app/auth/callback`

## Step 3: Get Your Discord Server ID

1. Enable Developer Mode in Discord:
   - User Settings → Advanced → Developer Mode (toggle on)
2. Right-click your Discord server
3. Click "Copy Server ID"

## Step 4: Configure auth_config.json

Update the `auth_config.json` file with your values:

```json
{
  "discord_client_id": "YOUR_CLIENT_ID_HERE",
  "discord_client_secret": "YOUR_CLIENT_SECRET_HERE", 
  "discord_server_id": "YOUR_SERVER_ID_HERE",
  "redirect_uri": "http://localhost:5000/auth/callback"
}
```

## Step 5: Required OAuth2 Scopes

The application automatically requests these scopes:
- `identify` - to get user information
- `guilds` - to check server membership

## How It Works

1. Users visit your website
2. They see a login page requiring Discord authentication
3. They click "Login with Discord"
4. Discord redirects them back after authorization
5. The app checks if they're a member of your Discord server
6. If yes, they get access to the Discord Scanner
7. If no, they see an access denied message

## Security Features

- JWT tokens for secure session management
- Server membership verification on every login
- No database required - all authentication is session-based
- Automatic token expiration (24 hours)

## Testing

After configuration:
1. Restart the FastAPI server
2. Visit your website
3. You should see the Discord login page
4. Test with a user who is NOT in your server (should be denied)
5. Test with a user who IS in your server (should get access)