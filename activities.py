import discord
from discord.ext import commands

class ActivityCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_conversations = {}

    @commands.command(name='start_log')
    async def start_log_command(self, ctx):
        user_id = ctx.author.id
        self.active_conversations[user_id] = {'step': 0, 'data': {}, 'channel': ctx.channel}
        await ctx.send("Let's log your daily activity. Please enter the number of **Knocks**.")

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author == self.bot.user:
            return

        user_id = message.author.id
        conversation = self.active_conversations.get(user_id)

        if conversation and message.channel == conversation['channel']:
            step = conversation['step']
            data = conversation['data']
            
            # This is where you would validate input (e.g., check if it's a number)
            # For now, we'll just move to the next step

            if step == 0:
                data['knocks'] = message.content
                await message.channel.send("Great. Now, the number of **Presentations**?")
                conversation['step'] = 1
            elif step == 1:
                data['presentations'] = message.content
                await message.channel.send("Okay. How many were **Not Interested (NI)**?")
                conversation['step'] = 2
            elif step == 2:
                data['ni'] = message.content
                await message.channel.send("Next, the number of **Bad Addresses**.")
                conversation['step'] = 3
            elif step == 3:
                data['bad_addresses'] = message.content
                await message.channel.send("How many **Sales** did you make?")
                conversation['step'] = 4
            elif step == 4:
                data['sales'] = message.content
                await message.channel.send("And finally, the **AP** (Annual Premium) for today?")
                conversation['step'] = 5
            elif step == 5:
                data['ap'] = message.content
                
                # End of conversation, send final report
                final_message = (
                    f"**Final Activity Report for {message.author.name}:**\n"
                    f"Knocks: {data['knocks']}\n"
                    f"Presentations: {data['presentations']}\n"
                    f"NI: {data['ni']}\n"
                    f"Bad Addresses: {data['bad_addresses']}\n"
                    f"Sales: {data['sales']}\n"
                    f"AP: {data['ap']}"
                )
                await message.channel.send(final_message)
                
                # Clear the conversation state
                del self.active_conversations[user_id]
