# bot.py

from collections import defaultdict
from datetime import date, timedelta
from dateutil.parser import parse
import logging
import random

import discord
from discord.ext import commands
import numpy as np
import pandas as pd
from texttable import Texttable

import database as db
import globals

bot = commands.Bot(command_prefix='!')

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')


@bot.command(name='game-create')
@commands.has_role('Admin')
async def game_init(ctx, game_name='WOLF', starting_date=(date.today() + timedelta(days=1)).strftime("%y-%m-%d")):
    game_name = game_name.upper()

    #####################
    ### CHECKS      #####
    #####################
    # check that the inputs are valid
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

    # await game_del(ctx, game_name) #todo remove after testing
    guild = ctx.guild
    existing_category = discord.utils.get(guild.categories, name=game_name)

    #check game name is not already being used
    if existing_category is not None:
        await ctx.message.channel.send(f'{game_name} game already exists')
        return

    # check the announcement channel exists
    announcement_channel = None
    for channel in ctx.guild.channels:
        if channel.name == 'game-announcements':
            announcement_channel = channel

    if announcement_channel is None:
        await ctx.channel.send(f'you need to create a "game-announcements" channel')
        return

    #####################
    ### CREATE GAME #####
    #####################
    print(f'Creating a new game: {game_name}')

    default_permissions = {guild.default_role: discord.PermissionOverwrite(read_messages=False)}
    game_category = await guild.create_category(game_name, overwrites=default_permissions)

    #send an announcemnt for the game
    announcement_message = await announcement_channel.send(
        f'''New game called {game_name} will be starting on {starting_date}. If you would like to register for this game, react to this post with a {globals.GAME_REACTION_EMOJI} Registrations will close at 5pm on {starting_date}. Roles will be assigned and more instructions will follow.''')
    await announcement_message.add_reaction(globals.GAME_REACTION_EMOJI)

    # add game data to database
    game_data = {'discord_category_id': game_category.id,
                 'game_name': game_name,
                 'status': 'recruiting',
                 'start_date': starting_date,
                 'discord_announce_message_id': announcement_message.id}
    db.insert_into_table('game', game_data)

    game_table = db.get_table('game', {'discord_category_id': game_category.id})
    game_id = game_table['game_id'].iloc[0]


    #####################
    ### CREATE ROLE #####
    #####################
    role = db.get_table('role')
    roles_created = {}
    for idx, row in role.iterrows():
        if row['default_value'] == 'everyone':
            continue
        created_role = await guild.create_role(name=f'{game_name}-{row["role_name"]}')
        roles_created[row['role_id']] = created_role

        print(f'role created named {created_role.name}')

    #add role data to db
    for idx, role in roles_created.items():

        game_role_data = {'game_id': int(game_id),
                     'role_id': idx,
                     'discord_role_id': role.id,
                     'game_role_name': role.name}
        db.insert_into_table('game_role', game_role_data)


    ########################
    ### CREATE CHANNEL #####
    ########################
    channels = db.get_table('channel')
    for idx, channel in channels.iterrows():
        channel_options = {'name': channel['channel_name'],
                            'category':game_category,
                            'position':channel['channel_order'],
                            'topic':channel['channel_topic']}
        if channel['channel_type'] == 'voice':
            new_channel = await guild.create_voice_channel(**channel_options)
        else:
            new_channel = await guild.create_text_channel(**channel_options)
        channel_data = {'game_id': int(game_id), 'channel_id': channel['channel_id'],
                        'discord_channel_id': new_channel.id, 'name': channel['channel_name']}
        db.insert_into_table('game_channel', channel_data)
        print(f'creating channel {new_channel.name}')

    #########################
    ### SET PERMISSIONS #####
    #########################
    await update_game_permissions(ctx, game_id, 'day')


@bot.command(name='game-remove', help='WANING: Removes the entire game from the server (unrecoverable)')
@commands.has_role('Admin')
async def game_del(ctx, game_name='wolf'):
    game_name = game_name.upper()
    guild = ctx.guild
    # print(ctx.attrs)
    category = discord.utils.get(guild.categories, name=game_name)

    if category is None:
        await ctx.message.channel.send(f'{game_name} game does not exist')
        return None

    print(f'Removing game {category.name}')

    game_data = db.get_table('game', {'discord_category_id': category.id}).iloc[0]
    game_id = game_data['game_id']

    for ch in category.channels:
        await ch.delete()
    await category.delete()


    game_role = db.get_table('game_role', {'game_id': game_id})
    for idx, row in game_role.iterrows():
        role = guild.get_role(row['discord_role_id'])
        await role.delete()


async def get_game(channel, check_status=None):
    game_data = db.get_table('game', {'discord_category_id': channel.category.id})
    if not game_data.empty:
        game_data = game_data.iloc[0]

        if check_status is not None and game_data['status'].lower() != check_status:
            await channel.send(f'{game_data["game_name"]} is not in the {check_status} stage, this will have no affect')
            return None
        return game_data
    return None


@bot.command(name='character-add', help='Add a character to staging, can only be used in a game category')
@commands.has_role('Admin')
async def character_add(ctx, characters, build='primary'):
    build = build.lower()
    characters = characters.lower()

    game_data = await get_game(ctx.channel, 'recruiting')
    if game_data is not None:
        game_id = game_data['game_id']

        character_data  = db.get_table('character')
        character_list = characters.split(',')
        for character in character_list:

            character_info = character_data[character_data['character_name'] == character]
            if character_info.empty:
                await ctx.channel.send(f'no character named {character}, this has not been included')
                continue

            print(f'adding character {character}')
            character_info = character_info.iloc[0]

            game_character_data = {'game_id': game_id, 'character_id': character_info['character_id'],
                                   'build_name': build, 'will_play': True}
            db.insert_into_table('game_character', game_character_data)

        game_character = db.get_table('game_character', indicators={'game_id': game_id, 'build_name': build})

        await ctx.channel.send(f'SUCCESS! you have a total of {game_character.shape[0]} characters in build "{build}"')
        return


@bot.command(name='character-build-list', help='List all characters in selected build')
@commands.has_role('Admin')
async def character_list(ctx, build='primary'):
    build = build.lower()

    game_data = await get_game(ctx.channel, 'recruiting')
    if game_data is not None:
        game_id = game_data['game_id']

        game_character = db.get_table('game_character', indicators={'game_id': game_id, 'build_name': build},
                                      joins={'character': 'character_id'})
        text = f'Characters currently assigned to build {build}'
        for idx, character in game_character.iterrows():
            text += f"\n{character['character_name']}"
        text += f'\n{game_character.shape[0]} total'
        await ctx.channel.send(text)


@bot.command(name='character-build-purge', help='Removes all characters in selected build')
@commands.has_role('Admin')
async def character_build_purge(ctx, build='primary'):
    build = build.lower()

    game_data = await get_game(ctx.channel, 'recruiting')
    if game_data is not None:
        game_id = game_data['game_id']

        db.delete_from_table('game_character', indicators={'game_id': game_id, 'build_name': build})
        await ctx.channel.send(f'Purged characters in build "{build}"')


@bot.command(name='game-assign-characters', help='Randomly assigns the characters of a build to characters')
@commands.has_role('Admin')
async def game_assign_characters(ctx, build='primary'):
    build = build.lower()

    game_data = await get_game(ctx.channel, 'initializing')
    if game_data is not None:
        game_id = game_data['game_id']

        game_players = db.get_table('game_player', indicators={'game_id':game_id})
        game_characters = db.get_table('game_character', indicators={'game_id': game_id, 'build_name': build}).sample(frac=1)

        if game_players.shape[0] != game_characters.shape[0]:
            await ctx.channel.send(f'players ({game_players.shape[0]}) and characters ({game_characters.shape[0]}) must be equal')
            return

        await ctx.channel.send(f'you have {game_players.shape[0]} players and {game_characters.shape[0]}  characters')

        positions = list(range(1, game_players.shape[0] + 1))
        random.shuffle(positions)
        for idx, player in game_players.iterrows():
            user = ctx.guild.get_member(player['discord_user_id'])
            character_id = game_characters['character_id'].iloc[idx]
            character = db.get_table('character', indicators={'character_id': character_id}).iloc[0]
            await ctx.channel.send(f'{user} has been assigned the role {character["character_display_name"]}')

            db.update_table('game_player',  {'character_id': character_id, 'starting_character_id': character_id,
                             'position': positions[idx], 'vitals': 'alive', 'current_affiliation': character['starting_affiliation']},
                            {'game_id': game_id, 'discord_user_id':player['discord_user_id']})

            # game_players = db.get_table('game_player', indicators={'game_id': game_id})

        await update_game_permissions(ctx, game_id, 'day')
        return


async def update_game_permissions(ctx, game_id, phase):
    # player permissions
    # game_players = db.get_table('game_player', {'game_id': game_id})
    character_permissions = db.get_table('character_permission', joins={'game_player': 'character_id'},
                                         indicators={'game_id': game_id})


    character_permissions = character_permissions[character_permissions['game_phase'].isin([None, phase])]
    #only keep permissions that track living status
    character_map = character_permissions.apply(lambda x: x['vitals_required'] in [None, x['vitals']], axis=1)
    character_permissions = character_permissions[character_map]

    # role permissions
    role_permissions = db.get_table('role_permission', joins={'game_role': 'role_id'}, indicators={'game_id': game_id})
    role_permissions = role_permissions[role_permissions['game_phase'].isin([None, phase])]

    for idx, channel_row in db.get_table('game_channel', {'game_id': game_id}).iterrows():
        channel_id = channel_row['channel_id']
        channel = ctx.guild.get_channel(channel_row['discord_channel_id'])

        channel_char_perms = character_permissions[character_permissions['channel_id'].isin([None, int(channel_id)])]
        role_char_perms = role_permissions[role_permissions['channel_id'].isin([None, int(channel_id)])]

        perms = defaultdict(dict)
        for idx, row in channel_char_perms.iterrows():
            user = ctx.guild.get_member(row['discord_user_id'])
            perms[user][row['permission_name']] = True if int(row['permission_value']) else False

        for idx, row in role_char_perms.iterrows():
            user = ctx.guild.get_role(row['discord_role_id'])
            perms[user][row['permission_name']] = True if int(row['permission_value']) else False

        # ensures default channel cant be seen
        old_targets = list(channel.overwrites.keys())
        if ctx.guild.default_role in old_targets:
            await channel.set_permissions(ctx.guild.default_role, overwrite=discord.PermissionOverwrite(read_messages=False))
            old_targets.remove(ctx.guild.default_role)

        for target, values in perms.items():
            if target in old_targets:
                old_targets.remove(target)
            values = discord.PermissionOverwrite(**values)
            await channel.set_permissions(target, overwrite=values)

        # clears out any extra permissions
        for target in old_targets:
            await channel.set_permissions(target, overwrite=discord.PermissionOverwrite())


@bot.command(name='phase', help="change the game phase, values accepted [day, night]")
@commands.has_role('Admin')
async def game_phase(ctx, phase):
    print('running phase')

    if phase not in ['day', 'night']:
        await ctx.channel.send(f'not a valid phase')
        return

    game_data = await get_game(ctx.channel, 'active')
    if game_data is not None:
        game_id = game_data['game_id']
        await update_game_permissions(ctx, game_id, phase)


def get_game_player_status(ctx, game_id):
    game_players = db.get_table('game_player', {'game_id': game_id})
    print(game_players.dtypes)
    game_players = game_players.sort_values('position')
    guild = ctx.guild

    table = Texttable()
    table.header(['Position', 'User', 'Status']) # todo add in character if deceased

    for idx, row in game_players.iterrows():
        user = guild.get_member(row['discord_user_id'])
        table.add_row([row['position'], user, row['vitals']])
    return f'```{table.draw()}```'


@bot.command(name='game-info', help="prints info about the current game")
@commands.has_role('Admin')
async def game_info (ctx):
    print(db.get_table('game'))
    game_data = await get_game(ctx.channel) #todo set to only "active" after testing
    if game_data is not None:
        game_id = game_data['game_id']

        table = Texttable()
        table.header(['ID', 'Name', 'Status', 'Start Date'])  # todo add in character if deceased

        table.add_row([game_data['game_id'], game_data['game_name'], game_data['status'], game_data['start_date']])

        await ctx.channel.send(f'```{table.draw()}```')


@bot.command(name='game-player-status', help="prints out the current state of all players")
@commands.has_role('Admin')
async def game_player_status(ctx):
    game_data = await get_game(ctx.channel) #todo set to only "active" after testing
    if game_data is not None:
        game_id = game_data['game_id']

        status_post = get_game_player_status(ctx, game_id)
        await ctx.channel.send(f'{status_post}')


@bot.command(name='game-start', help="starts the game, assigns and updates permsissions UNFUNCTIONAL")
@commands.has_role('Admin')
async def game_start (ctx, build='primary'):
    game_data = await get_game(ctx.channel, 'recruiting')
    if game_data is not None:
        game_id = game_data['game_id']
        # todo add try except here
        db.update_table('game', {'status': 'initializing'}, {'game_id': game_id}) #todo add number of players

        await game_assign_characters(ctx, build)
        await update_game_permissions(ctx, game_id, 'day')

        status_post = get_game_player_status(ctx, game_id)
        await ctx.channel.send(f'{status_post}') # todo send this to the "player" channel

        db.update_table('game', {'status': 'active'}, {'game_id': game_id})


@bot.command(name='game-complete', help="completes a game")
@commands.has_role('Admin')
async def game_complete (ctx):
    game_data = await get_game(ctx.channel, 'active')
    if game_data is not None:
        game_id = game_data['game_id']

        db.update_table('game', {'status': 'completed'}, {'game_id': game_id})




@bot.command(name='death', help='provide a characters name and tag to kill in the form of "player#0000"')
@commands.has_role('Admin')
async def death(ctx, player):
    game_data = await get_game(ctx.channel, 'active')
    if game_data is not None:
        game_id = game_data['game_id']

        found_member = None
        for member in ctx.guild.members:
            if str(member) == player:
                found_member = member
                break

        if found_member is None:
            await ctx.channel.send(f'There is no member called "{player}"')
            return

        member_data = db.get_table("game_player", indicators={'game_id': game_id, 'discord_user_id': found_member.id})
        if member_data.empty:
            await ctx.channel.send(f'"{player}" is not a part of this game')
            return

        #todo check if already dead

        db.update_table("game_player", data_to_update={'vitals': 'deceased'},
                        update_conditions={'game_id': game_id, 'discord_user_id': found_member.id})

        role_data = db.get_table('game_role', joins={'role': 'role_id'}, indicators={'game_id': game_id})
        deceased_role_id = ctx.guild.get_role(role_data[role_data['default_value'] == 'deceased'].iloc[0]['discord_role_id'])
        alive_role_id = ctx.guild.get_role(role_data[role_data['default_value'] == 'alive'].iloc[0]['discord_role_id'])
        await found_member.add_roles(deceased_role_id)
        await found_member.remove_roles(alive_role_id)


#todo make these into one function
@bot.event
async def on_raw_reaction_add(payload):
    if payload.member.bot == True:
        return
    channel = bot.get_channel(payload.channel_id)
    if str(channel) == 'game-announcements':
        game_table = db.get_table('game', {'status': 'recruiting'})
        # game_table = game_table[game_table['status'].str.lower() == ]

        guild = bot.get_guild(payload.guild_id)

        for idx, row in game_table.iterrows():
            if payload.message_id == row['discord_announce_message_id'] and payload.emoji.name == globals.GAME_REACTION_EMOJI:

                role_id = db.get_table('game_role', {'game_id': row['game_id'], 'default_value': 'alive'},
                                       joins={'role': 'role_id'}).iloc[0]['discord_role_id']
                role = guild.get_role(role_id)

                member = guild.get_member(payload.user_id)
                await member.add_roles(role)

                # add member to database
                game_player_data = {'game_id': row['game_id'],
                             'discord_user_id': member.id}
                db.insert_into_table('game_player', game_player_data)

                return


@bot.event
async def on_raw_reaction_remove(payload):
    game_table = db.get_table('game', {'status': 'recruiting'})

    channel = bot.get_channel(payload.channel_id)
    if str(channel) == 'game-announcements':

        guild = bot.get_guild(payload.guild_id)
        for idx, row in game_table.iterrows():
            if payload.message_id == row['discord_announce_message_id'] and payload.emoji.name == globals.GAME_REACTION_EMOJI:
                role_id = db.get_table('game_role', {'game_id': row['game_id'], 'default_value': 'alive'},
                                       joins={'role': 'role_id'}).iloc[0]['discord_role_id']
                role = guild.get_role(role_id)

                member = guild.get_member(payload.user_id)
                await member.remove_roles(role)

                db.delete_from_table('game_player', {'game_id': row['game_id'], 'discord_user_id': member.id})

                return


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.errors.CheckFailure):
        await ctx.send('You do not have the correct role for this command.')
    else:
        raise error

