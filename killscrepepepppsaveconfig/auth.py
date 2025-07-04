"""
Discord OAuth Authentication for Server Membership Verification
No database required - uses session-based authentication
"""

import os
import json
import httpx
from fastapi import HTTPException, Request, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from datetime import datetime, timedelta
from typing import Optional, Dict

# JWT Configuration
SECRET_KEY = os.urandom(32).hex()  # Generate random secret key
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24

# Discord OAuth Configuration - loaded from auth_config.json
def get_auth_config():
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
                    config = json.load(f)
                    return config
        
        return {}
    except Exception as e:
        return {}

auth_config = get_auth_config()
DISCORD_CLIENT_ID = auth_config.get("discord_client_id", "")
DISCORD_CLIENT_SECRET = auth_config.get("discord_client_secret", "")
DISCORD_REDIRECT_URI = auth_config.get("redirect_uri", "http://localhost:5000/auth/callback")
YOUR_DISCORD_SERVER_ID = auth_config.get("discord_server_id", "")

# Discord OAuth URLs
DISCORD_API_BASE = "https://discord.com/api/v10"
DISCORD_OAUTH_URL = f"{DISCORD_API_BASE}/oauth2/authorize"
DISCORD_TOKEN_URL = f"{DISCORD_API_BASE}/oauth2/token"

security = HTTPBearer()

class DiscordAuth:
    @staticmethod
    def get_oauth_url() -> str:
        """Generate Discord OAuth URL"""
        # Reload config to get latest values
        current_config = get_auth_config()
        client_id = current_config.get("discord_client_id", "")
        redirect_uri = current_config.get("redirect_uri", "")
        
        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "identify guilds"
        }
        
        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        return f"{DISCORD_OAUTH_URL}?{query_string}"
    
    @staticmethod
    async def exchange_code_for_token(code: str) -> Dict:
        """Exchange OAuth code for access token"""
        # Reload config to get latest values
        current_config = get_auth_config()
        
        data = {
            "client_id": current_config.get("discord_client_id", ""),
            "client_secret": current_config.get("discord_client_secret", ""),
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": current_config.get("redirect_uri", "")
        }
        
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        
        async with httpx.AsyncClient() as client:
            response = await client.post(DISCORD_TOKEN_URL, data=data, headers=headers)
            
            if response.status_code != 200:
                raise HTTPException(status_code=400, detail="Failed to exchange code for token")
            
            return response.json()
    
    @staticmethod
    async def get_user_info(access_token: str) -> Dict:
        """Get Discord user information"""
        headers = {"Authorization": f"Bearer {access_token}"}
        
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{DISCORD_API_BASE}/users/@me", headers=headers)
            
            if response.status_code != 200:
                raise HTTPException(status_code=400, detail="Failed to get user info")
            
            return response.json()
    
    @staticmethod
    async def get_user_guilds(access_token: str) -> list:
        """Get user's Discord servers"""
        headers = {"Authorization": f"Bearer {access_token}"}
        
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{DISCORD_API_BASE}/users/@me/guilds", headers=headers)
            
            if response.status_code != 200:
                raise HTTPException(status_code=400, detail="Failed to get user guilds")
            
            return response.json()
    
    @staticmethod
    def check_server_membership(guilds: list, required_server_id: str) -> bool:
        """Check if user is member of required Discord server"""
        for guild in guilds:
            if str(guild.get("id")) == str(required_server_id):
                return True
        return False
    
    @staticmethod
    def create_access_token(user_data: Dict) -> str:
        """Create JWT access token"""
        to_encode = user_data.copy()
        expire = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
        to_encode.update({"exp": expire})
        
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt
    
    @staticmethod
    def verify_access_token(token: str) -> Dict:
        """Verify and decode JWT token"""
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            return payload
        except JWTError:
            raise HTTPException(status_code=401, detail="Invalid or expired token")

# Dependency to get current authenticated user
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict:
    """Get current authenticated user from JWT token"""
    token = credentials.credentials
    user_data = DiscordAuth.verify_access_token(token)
    
    # Check if token is expired
    exp = user_data.get("exp")
    if exp and datetime.utcnow().timestamp() > exp:
        raise HTTPException(status_code=401, detail="Token expired")
    
    return user_data

# Optional dependency - returns None if not authenticated
async def get_current_user_optional(request: Request) -> Optional[Dict]:
    """Get current user if authenticated, otherwise return None"""
    try:
        # Check Authorization header first
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            return DiscordAuth.verify_access_token(token)
        
        # Check for token in cookies as fallback
        token = request.cookies.get("discord_token")
        if token:
            return DiscordAuth.verify_access_token(token)
        
        return None
    except:
        return None

def load_auth_config():
    """Load authentication configuration"""
    try:
        with open('auth_config.json', 'r') as f:
            return json.load(f)
    except:
        return {}

def save_auth_config(config: Dict):
    """Save authentication configuration"""
    with open('auth_config.json', 'w') as f:
        json.dump(config, f, indent=2)