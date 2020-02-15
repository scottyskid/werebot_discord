# bot.py
import sqlite3
from datetime import date, timedelta
from dateutil.parser import parse

import discord
from discord.ext import commands

import database as db

bot = commands.Bot(command_prefix='!')

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')

@bot.command(name='game-create')
@commands.has_role('Admin')
async def game_init(ctx, game_name='WOLF', starting_date=(date.today() + timedelta(days=1)).strftime("%y-%m-%d")):
    # starting_date = date(starting_date)
    game_name = game_name.upper()

    try:
        starting_date = parse(starting_date, yearfirst=True).date()
    except ValueError:
        await ctx.message.channel.send(f'ensure starting date is in the format of "YYYY-MM-DD" you provided: {starting_date} ')
        return
    if starting_date < date.today():
        await ctx.message.channel.send(f'date you provided was not in the future, you provided {starting_date}')
        return
    if starting_date > date.today() + timedelta(days=60):
        await ctx.message.channel.send(f'games can be at most 60 days in the future, you provided {starting_date}')
        return

    await game_del(ctx, game_name) #todo remove after testing
    guild = ctx.guild
    existing_category = discord.utils.get(guild.categories, name=game_name)

    if existing_category is not None:
        await ctx.message.channel.send(f'{game_name} game already exists')
        return
    # else:
    print(f'Creating a new game: {game_name}')


    game_category = await guild.create_category(game_name)

    #send an announcemnt for the game
    announcement_channel = bot.get_channel(676761050133168148)
    announcement_message = await announcement_channel.send(
        f'''New game called {game_name} will be starting on {starting_date}. If you would like to register for this game, react to this post with a :wolf: Registrations will close at 5pm on {starting_date}. Roles will be assigned and more instructions will follow.''')

    # add game data to database
    game_data = {'discord_category_id': game_category.id,
                 'game_name': game_name,
                 'status': 'recruiting',
                 'start_date': starting_date,
                 'discord_announce_message_id': announcement_message.id}
    db.insert_into_table('game', game_data)

    game_table = db.get_table('game')
    game_id = game_table[game_table['discord_category_id'] == game_category.id]['game_id'].iloc[0]


    channels = db.get_table('channel')
    for idx, channel in channels.iterrows():
        new_channel = await guild.create_text_channel(channel['channel_name'],
                                        category=game_category,
                                        position=channel['channel_order'],
                                        topic=channel['channel_topic'])
        channel_data = {'game_id': int(game_id), 'channel_id': channel['channel_id'],
                        'discord_channel_id': new_channel.id, 'name': channel['channel_name']}
        db.insert_into_table('game_channel', channel_data)

    ## create roles

    await guild.create_role(name=f'{game_name}-alive')
    await guild.create_role(name=f'{game_name}-deceased')
    await guild.create_role(name=f'{game_name}-nar')





@bot.command(name='game-remove')
@commands.has_role('Admin')
async def game_del(ctx, game_name='wolf'):
    game_name = game_name.upper()
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
    game_table = db.get_table('game')
    game_table = game_table[game_table['status'].str.lower() == 'recruiting']

    guild = bot.get_guild(payload.guild_id)
    for idx, row in game_table.iterrows():
        if payload.message_id == row['discord_announce_message_id'] and payload.emoji.name == '🐺':
            member = guild.get_member(payload.user_id)
            role = discord.utils.get(guild.roles, name=f"{row['game_name']}-alive")
            await member.add_roles(role)

            # add member to database
            game_player_data = {'game_id': row['game_id'],
                         'discord_user_id': member.id}
            db.insert_into_table('game_player', game_player_data)

            print("inserting")
            print(db.get_table('game_player'))

            return


@bot.event
async def on_raw_reaction_remove(payload):
    game_table = db.get_table('game')
    game_table = game_table[game_table['status'].str.lower() == 'recruiting']

    guild = bot.get_guild(payload.guild_id)
    for idx, row in game_table.iterrows():
        if payload.message_id == row['discord_announce_message_id'] and payload.emoji.name == '🐺':
            member = guild.get_member(payload.user_id)

            role = discord.utils.get(guild.roles, name=f"{row['game_name']}-alive")
            await member.remove_roles(role)

            db.delete_from_table('game_player', {'game_id': row['game_id'], 'discord_user_id': member.id})

            return

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.errors.CheckFailure):
        await ctx.send('You do not have the correct role for this command.')
    else:
        raise error

