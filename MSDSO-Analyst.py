# system library
import os
import re

# discord.py library - no longer maintained. Swapping to disnake library
# import discord
# from discord.ext import commands
# util library

from datetime import datetime
from socket import gethostname

# disnake library
import disnake
from disnake.ext import commands

bot = commands.Bot(command_prefix="MSDSO: ")

MSDSO_emote = "<:MSDSO:773312353622032414>"

roles_channel_id = "802282167559651358"
bots_command_channel_id = "802306009506906132"

administrator_role_id = 807796843190419498
moderator_role_id = 773282500734484490

# Login notification
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}: ID: {bot.user.id})")

@commands.check_any(commands.is_owner(), commands.has_any_role(administrator_role_id, moderator_role_id))
@bot.command()
async def status(ctx):
    machine_type = "remote AWS" if gethostname()=="MSDSO-AWS" else "local"
    machine_time = str(datetime.now())
    await ctx.channel.send(f"{MSDSO_emote} MSDSO Analyst is running on a {machine_type} machine.\n Machine Time: {machine_time}\n Welcome, user {ctx.message.author.mention}")

@commands.check_any(commands.is_owner(), commands.has_any_role(administrator_role_id, moderator_role_id))
@bot.command()
async def purge(ctx, amount: int):
    await ctx.channel.purge(limit=(amount+1))

@commands.check_any(commands.is_owner(), commands.has_any_role(administrator_role_id, moderator_role_id))
@bot.command()
async def shutdown(ctx):
    await ctx.channel.send("Goodbye, shutting down.")
    await ctx.bot.logout()

@commands.check_any(commands.is_owner(), commands.has_any_role(administrator_role_id, moderator_role_id))
@bot.command()

async def assign(ctx, user: disnake.User, role_name, *args): # update for disnake package
    if len(args) > 0:
        await ctx.channel.send("usage: ``MSDSO: assign [-@user] [-role]``")
    else:
        guild = ctx.guild
        role = disnake.utils.get(guild.roles, name=role_name) # update for disnake package
        if role == None:
            await ctx.channel.send(f"error: role ``{role}`` is not valid.")
            return
        members = guild.members
        if user == "all":
            for member in members:
                await member.add_roles(role)
            return
        if user:
            await user.add_roles(role)
        else:
            await ctx.channel.send(f"error: member ``{user.name}`` is not in the server.")

@commands.check_any(commands.is_owner(), commands.has_any_role(administrator_role_id, moderator_role_id))
@bot.command()
async def echo(ctx, arg):
    await ctx.channel.send(arg)

@commands.check_any(commands.is_owner(), commands.has_any_role(administrator_role_id, moderator_role_id))
@bot.command()
async def edit(ctx, *args):
    if len(args) != 3:
        await ctx.channel.send("usage: ``MSDSO: edit [-channel id] [-message id] [-quoted message]``")
    else:
        channel = ctx.guild.get_channel(int(args[0]))
        message = await channel.fetch_message(int(args[1]))
        new_message = str(args[2])
        await message.edit(content=new_message)

@bot.command()
async def react_to_message(ctx, *args):
    if len(args) != 3:
        await ctx.channel.send("usage: ``MSDSO: react_to_message [-channel id] [-message id] [-reaction]``")
    else:
        channel_id = int(args[0])
        message_id = int(args[1])
        channel = ctx.guild.get_channel(channel_id)
        message = await channel.fetch_message(message_id)
        emoji = args[2]
        await message.add_reaction(emoji)

reaction_role_message_id = [
    803042885179277322,         # role
    803043475616301097,         # cohort
    803058349775912970          # class access
]

reaction_role_dict = {
    # general role
    "🕵️": 802765865048604673,       # Visitor",
    "MSCSO": 802765732055220244,    # MSCSO Student
    "MSDSO": 773281658555990023,    # Admitted Student
    "👀": 773281343823675422,       # Prospective Student
    # cohort role
    "1️⃣": 773282104657838101, # Spring 2021 Cohort
    "2️⃣": 802795502126891040, # Fall 2021 Cohort
    "3️⃣": 809871306442145872, # Spring 2022 Cohort
    "4️⃣": 809871233034354758, # Fall 2022 Cohort
    # class access role
    "💭": 809847471962193920, # DSC 383 Advanced Predictive Models
    "💻": 809847762081284117, # DSC 388G Algorithms: Techniques And Theory
    "🖼️": 809847968605536256, # DSC 385 Data Exploration & Visualization
    "🧠": 809848094275403866, # DSC 395T Deep Learning
    "📖": 809848240756621402, # DSC 395T Design Principles & Causal Inference
    "🗣️": 809848390984007690, # DSC 395T Natural Language Processing
    "🧮": 809848511423053825, # DSC 395T Optimization
    "🤖": 809848769809088543, # DSC 391L Principles Of Machine Learning
    "📊": 809848917653979226, # DSC 381 Probability & Inference
    "📈": 809849489891393580  # DSC 382 Regression & Predictive Modeling
}

@bot.event
async def on_raw_reaction_add(payload):
    message_id = payload.message_id
    if message_id in reaction_role_message_id:
        member = payload.member
        guild_id = payload.guild_id
        guild = bot.get_guild(guild_id)
        role_id = reaction_role_dict[payload.emoji.name]
        role = guild.get_role(role_id)
        await member.add_roles(role)

@bot.event
async def on_raw_reaction_remove(payload):
    message_id = payload.message_id
    if message_id in reaction_role_message_id:
        guild_id = payload.guild_id
        guild = bot.get_guild(guild_id)
        member = await guild.fetch_member(payload.user_id)
        role_id = reaction_role_dict[payload.emoji.name]
        role = guild.get_role(role_id)
        await member.remove_roles(role)

# server OAuth2 key
from private.config import TOKEN 
bot.run(TOKEN)
