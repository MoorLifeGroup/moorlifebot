import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
import asyncio

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

# This event handles new members joining the server
@bot.event
async def on_member_join(member):
    # Sends a welcome message to the server's default channel
    channel = member.guild.system_channel
    if channel is not None:
        await channel.send(f'Welcome, {member.mention}! We\'re glad you\'re here.')

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
    # Create an embedded message for a nicer look
    embed = discord.Embed(title="New Poll", description=question, color=discord.Color.blue())
    poll_message = await ctx.send(embed=embed)
    await poll_message.add_reaction("👍")
    await poll_message.add_reaction("👎")

# This command logs daily activity with a single line of input
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

# This command starts the conversational activity logger
@bot.command(name='start_log')
async def start_log_command(ctx):
    # We will handle the rest of this conversation in a separate file (e.g., activities.py)
    await ctx.send("Let's log your daily activity. Please enter the number of **Knocks**.")

# Run the bot with the token from the .env file
if __name__ == "__main__":
    bot.run(TOKEN)
