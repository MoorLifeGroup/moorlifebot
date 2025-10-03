import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
import asyncio
from activities import ActivityCog

# Load environment variables from the .env file
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

# Set up bot intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

# Create a bot instance
bot = commands.Bot(command_prefix='!', intents=intents)

# This event runs when the bot is online and ready
@bot.event
async def on_ready():
    print(f'{bot.user.name} has connected to Discord!')

# This is a simple command that responds to '!hello'
@bot.command()
async def hello(ctx):
    await ctx.send(f'Hello, {ctx.author.mention}!')

# This command sends a direct message to the user who ran it
@bot.command()
async def dm(ctx, *, message):
    try:
        await ctx.author.send(f'You asked me to send a DM saying: {message}')
        await ctx.send('DM sent successfully!')
    except discord.Forbidden:
        await ctx.send('I could not send you a DM. Please check your privacy settings.')

# This command creates a basic poll with thumbs up and down reactions
@bot.command()
async def poll(ctx, *, question):
    embed = discord.Embed(title="New Poll", description=question, color=discord.Color.blue())
    poll_message = await ctx.send(embed=embed)
    await poll_message.add_reaction("👍")
    await poll_message.add_reaction("👎")

# This command is a one-line activity logger
@bot.command()
async def log_activity(ctx, knocks, presentations, ni, bad_addresses, sales, ap):
    message = (
        f"**Daily Activity Report for {ctx.author.name}:**\n"
        f"Knocks: {knocks}\n"
        f"Presentations: {presentations}\n"
        f"NI: {ni}\n"
        f"Bad Addresses: {bad_addresses}\n"
        f"Sales: {sales}\n"
        f"AP: {ap}"
    )
    await ctx.send(message)

# This function adds the cogs to the bot
async def main():
    await bot.add_cog(ActivityCog(bot))
    await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
