# Discord Scanner - Vercel Deployment Guide

## Overview
This Discord Scanner has been converted to work with Vercel hosting using FastAPI instead of Flask.

## Files Created for Vercel
- `api/index.py` - Main FastAPI application (Vercel-compatible)
- `vercel.json` - Vercel deployment configuration
- `templates/index.html` - Updated with new API endpoints

## Key Changes Made
1. **Flask to FastAPI Conversion**: 
   - Replaced Flask routes with FastAPI endpoints
   - Added Pydantic models for request validation
   - Updated session management for serverless environment

2. **API Endpoint Updates**:
   - `/connect` → `/api/connect`
   - `/status` → `/api/status/{session_id}`
   - `/servers` → `/api/servers/{session_id}`
   - `/send_message` → `/api/send_message/{session_id}`
   - And all other endpoints follow the same pattern

3. **Session Management**:
   - Sessions now use UUID generation instead of Flask sessions
   - Each connection gets a unique session ID
   - All API calls require the session ID in the URL path

## Deployment to Vercel

### Prerequisites
1. Create a Vercel account at https://vercel.com
2. Install Vercel CLI: `npm install -g vercel`

### Deployment Steps
1. **Initialize Vercel Project**:
   ```bash
   vercel login
   vercel
   ```

2. **Configure Environment Variables** (if needed):
   - Go to your Vercel dashboard
   - Add any required environment variables
   - For Discord webhook logging, add `WEBHOOK_URL`

3. **Deploy**:
   ```bash
   vercel --prod
   ```

### File Structure for Vercel
```
.
├── api/
│   └── index.py          # Main FastAPI application
├── templates/
│   └── index.html        # Frontend interface
├── vercel.json           # Vercel configuration
├── config.json           # Discord webhook configuration
└── README_VERCEL.md      # This file
```

## Important Notes


### Serverless Limitations
- Each function has a 60-second timeout limit
- Stateful connections may be reset between requests
- Discord client connections may need reconnection handling

### Configuration
Update `config.json` with your Discord webhook URL for token logging:
```json
{
  "webhook_url": "https://discord.com/api/webhooks/YOUR_WEBHOOK_URL"
}
```

## Testing Locally
To test the FastAPI version locally:
```bash
cd api
python index.py
```
The server will run on http://localhost:5000

## Troubleshooting

### Common Issues
1. **Import Errors**: Ensure all dependencies are installed
2. **Discord Connection**: Check token validity and network connectivity
3. **Session Management**: Sessions may expire; refresh the page to reconnect

### Vercel-Specific Issues
1. **Cold Starts**: First request may be slow due to function initialization
2. **Memory Limits**: Large server scans may hit memory limits
3. **Timeout Issues**: Long-running operations may timeout

## Security Considerations
- Never commit Discord tokens to version control
- Use environment variables for sensitive data
- Monitor webhook logs for unauthorized access
- Consider implementing rate limiting for production use

## Next Steps
1. Test the application locally
2. Deploy to Vercel
3. Configure custom domain (optional)
4. Monitor logs and performance
5. Implement additional security measures as needed