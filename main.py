import discord
from discord.ext import commands
import os
from dotenv import load_dotenv

# Load the environment variables from the .env file
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

# Set up the bot's intents. Intents specify which events your bot listens to.
intents = discord.Intents.default()
intents.message_content = True  # Required to read message content
intents.members = True          # Required for member-related events

# Create a bot instance with a command prefix of '!'
bot = commands.Bot(command_prefix='!', intents=intents)

# This event runs when the bot is online and ready
@bot.event
async def on_ready():
    print(f'{bot.user.name} has connected to Discord!')

# This is a simple command that responds to '!hello'
@bot.command()
async def hello(ctx):
    await ctx.send(f'Hello, {ctx.author.mention}!')

# Run the bot with the token
if __name__ == "__main__":
    bot.run(TOKEN)