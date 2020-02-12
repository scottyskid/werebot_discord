# bot.py
import sqlite3

import discord
from discord.ext import commands

import database as db

bot = commands.Bot(command_prefix='!')

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')

@bot.command(name='game-create')
@commands.has_role('Admin')
async def game_init(ctx, game_name='wolf'):
    guild = ctx.guild
    existing_category = discord.utils.get(guild.categories, name=game_name)

    if existing_category is not None:
        await ctx.message.channel.send(f'{game_name} game already exists')
        return None
    # else:
    print(f'Creating a new game: {game_name}')
    game_channel = await guild.create_category(game_name)
    await guild.create_text_channel('narration', category=game_channel)
    await guild.create_text_channel('moderator', category=game_channel)
    await guild.create_text_channel('player', category=game_channel)
    await guild.create_text_channel('everyone', category=game_channel)
    await guild.create_text_channel('lynching', category=game_channel)
    await guild.create_text_channel('werewolves', category=game_channel)
    await guild.create_text_channel('vampires', category=game_channel)
    await guild.create_text_channel('graveyard', category=game_channel)

    #todo create roles
    print('creating roles')
    await guild.create_role(name=f'{game_name}-alive')
    await guild.create_role(name=f'{game_name}-deceased')
    await guild.create_role(name=f'{game_name}-mod')


@bot.command(name='game-remove')
@commands.has_role('Admin')
async def game_del(ctx, game_name='wolf'):
    guild = ctx.guild
    # print(ctx.attrs)
    category = discord.utils.get(guild.categories, name=game_name)

    if category is None:
        await ctx.message.channel.send(f'{game_name} game does not exist')
        return None

    for ch in category.channels:
        await ch.delete()
    await category.delete()

    for role in guild.roles:
        if game_name in role.name:
            await role.delete()

@bot.event
async def on_raw_reaction_add(payload):
    print(f'{payload.message_id}')
    print(payload)
    guild = bot.get_guild(payload.guild_id)
    if payload.message_id == 677090496987922432 and payload.emoji.name == '👍':
        member = guild.get_member(payload.user_id)
        role = discord.utils.get(guild.roles, name="day-alive")
        await member.add_roles(role)


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.errors.CheckFailure):
        await ctx.send('You do not have the correct role for this command.')
    else:
        raise error

