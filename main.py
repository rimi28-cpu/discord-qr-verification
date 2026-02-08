#!/usr/bin/env python3
"""
Discord QR Login System
Main entry point for Replit
"""

import os
import sys
import asyncio

print("╔══════════════════════════════════════╗")
print("║    Discord QR Login System           ║")
print("╚══════════════════════════════════════╝")
print("\n🌐 Running on Replit")
print("🤖 Starting Discord Bot...")
print("💡 Use !verify command in Discord")
print("-" * 50)

# Import and run the bot
try:
    from qr_bot import main as bot_main
    asyncio.run(bot_main())
except KeyboardInterrupt:
    print("\n\n⚠️ Bot stopped by user.")
except Exception as e:
    print(f"\n❌ Error starting bot: {e}")
    import traceback
    traceback.print_exc()
    print("\n💡 Make sure you've set up all configuration in config.py")
