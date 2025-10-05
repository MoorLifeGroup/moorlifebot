# main.py
import os
import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv

# Load environment variables (useful for local runs; Render injects env directly)
load_dotenv()

# Bot token (support either DISCORD_TOKEN or DISCORD_BOT_TOKEN)
TOKEN = os.getenv("DISCORD_TOKEN") or os.getenv("DISCORD_BOT_TOKEN")

# Intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

# Bot instance
bot = commands.Bot(command_prefix="!", intents=intents)

# --- Minimal health checks ---
@bot.event
async def on_ready():
    print(f"✅ {bot.user} is online (ID: {bot.user.id})")

@bot.command(name="hello")
async def hello(ctx: commands.Context):
    await ctx.send(f"Hello, {ctx.author.mention}!")

# --- Load the activities cog and start ---
async def _startup():
    if not TOKEN:
        raise SystemExit("❌ Missing bot token. Set DISCORD_TOKEN (or DISCORD_BOT_TOKEN).")
    # Import here so file errors are surfaced clearly on boot
    try:
        from activities import ActivityCog
    except Exception as e:
        raise SystemExit(f"❌ Failed to import activities cog: {e}")

    try:
        await bot.add_cog(ActivityCog(bot))
        print("📦 Loaded Activities cog")
    except Exception as e:
        raise SystemExit(f"❌ Failed to add Activities cog: {e}")

    # Start the bot
    await bot.start(TOKEN)

if __name__ == "__main__":
    try:
        asyncio.run(_startup())
    except KeyboardInterrupt:
        print("🛑 Shutdown requested by user.")
