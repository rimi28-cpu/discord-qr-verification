"""
Configuration for Discord QR Verification System
Edit these values before running!
"""

# Bot Configuration
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"  # REQUIRED: Your Discord bot token
BOT_PREFIX = "!"  # Bot command prefix

# Webhook Configuration (optional)
WEBHOOK_URL = "YOUR_WEBHOOK_URL_HERE"  # Optional: Discord webhook URL for notifications

# Security Configuration
ADMIN_ONLY = True  # Set to True to restrict commands to admins only
ADMIN_IDS = [
    123456789012345678,  # Add your Discord user ID here
    # Add more admin IDs as needed
]

# Logging Configuration
LOG_CHANNEL_ID = None  # Optional: Channel ID for logging verification events
LOG_VERIFICATIONS = True  # Log all verification attempts

# System Configuration
DEBUG = False  # Set to True for debug messages
USE_KEEP_ALIVE = True  # Use keep-alive server for Replit

# QR Code Configuration
QR_EXPIRE_MINUTES = 2  # QR code expiration time
QR_SIZE = 400  # QR code size in pixels

# Verification Messages
VERIFICATION_SUCCESS_MESSAGE = "✅ Verification successful! Welcome!"
VERIFICATION_TIMEOUT_MESSAGE = "❌ Verification timed out. Please try again."
VERIFICATION_FAILED_MESSAGE = "❌ Verification failed. Please contact an administrator."

# Note: Add your template.png file to the project for custom QR backgrounds
