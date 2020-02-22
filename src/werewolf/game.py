""" game.py stores all elements to run a game of werewolf in

The file contains the main high level functions to run a game
including create, remove, start, complete, phase
"""

from collections import defaultdict
from datetime import date, timedelta
from dateutil.parser import parse
import logging
import random

import discord
from texttable import Texttable

import database as db
import globals
from globals import game_status


async def get_game(channel, check_status: game_status = None):
    game_data = db.get_table('game', {'discord_category_id': channel.category.id})
    if not game_data.empty:
        game_data = game_data.iloc[0]

        if check_status is not None and game_data['status'].lower() != check_status.value:
            await channel.send(f'{game_data["game_name"]} is not in the {check_status} stage, this will have no affect')
            return None
        return game_data
    return None


async def create(ctx, game_name, starting_date):
    game_name = game_name.upper()

    #####################
    ### CHECKS      #####
    #####################
    # check that the inputs are valid
    try:
        starting_date = parse(starting_date, yearfirst=True).date()
    except ValueError:
        await ctx.message.channel.send(
            f'ensure starting date is in the format of "YYYY-MM-DD" you provided: {starting_date} ')
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

    # check game name is not already being used
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

    # send an announcemnt for the game
    announcement_message = await announcement_channel.send(
        f'''New game called {game_name} will be starting on {starting_date}. If you would like to register for this game, react to this post with a {globals.GAME_REACTION_EMOJI} Registrations will close at 5pm on {starting_date}. Roles will be assigned and more instructions will follow.''')
    await announcement_message.add_reaction(globals.GAME_REACTION_EMOJI)

    # add game data to database
    game_data = {'discord_category_id': game_category.id,
                 'game_name': game_name,
                 'status': game_status.CREATING.value,
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

    # add role data to db
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
                           'category': game_category,
                           'position': channel['channel_order'],
                           'topic': channel['channel_topic']}
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
    db.update_table('game', {'status': game_status.RECRUITING.value}, {'game_id': game_id})
    await update_game_permissions(ctx, game_id, 'day')


async def remove(ctx, game_name):
    # todo only allow to be done inside the moderator channel of a game
    game_name = game_name.upper()
    guild = ctx.guild
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

    db.update_table('game', {'status': game_status.REMOVED.value}, {'game_id': game_id})


async def update_game_permissions(ctx, game_id, phase):
    # player permissions
    # game_players = db.get_table('game_player', {'game_id': game_id})
    character_permissions = db.get_table('character_permission', joins={'game_player': 'character_id'},
                                         indicators={'game_id': game_id})

    character_permissions = character_permissions[character_permissions['game_phase'].isin([None, phase])]
    # only keep permissions that track living status
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
            await channel.set_permissions(ctx.guild.default_role,
                                          overwrite=discord.PermissionOverwrite(read_messages=False))
            old_targets.remove(ctx.guild.default_role)

        for target, values in perms.items():
            if target in old_targets:
                old_targets.remove(target)
            values = discord.PermissionOverwrite(**values)
            await channel.set_permissions(target, overwrite=values)

        # clears out any extra permissions
        for target in old_targets:
            await channel.set_permissions(target, overwrite=discord.PermissionOverwrite())

    db.update_table('game', data_to_update={'phase': phase}, update_conditions={'game_id': game_id})


def get_game_player_status(ctx, game_id):
    game_players = db.get_table('game_player', {'game_id': game_id})
    print(game_players.dtypes)
    game_players = game_players.sort_values('position')
    guild = ctx.guild

    table = Texttable()
    table.header(['Virtual Position', 'User', 'Status'])  # todo add in character if deceased

    for idx, row in game_players.iterrows():
        user = guild.get_member(row['discord_user_id'])
        table.add_row([row['position'], user, row['vitals']])
    return f'```{table.draw()}```'


async def game_assign_characters(ctx, scenario):
    scenario = scenario.lower()

    game_data = await get_game(ctx.channel, game_status.INITIALIZING)
    if game_data is not None and str(ctx.channel).lower() == globals.moderator_channel_name:
        game_id = game_data['game_id']

        game_players = db.get_table('game_player', indicators={'game_id': game_id})
        game_characters = db.get_table('game_character',
                                       indicators={'game_id': game_id, 'scenario_name': scenario}).sample(
            frac=1)

        correct_chars = await game_has_correct_chars(ctx, game_id, scenario)
        if not correct_chars:
            return

        await ctx.channel.send(f'you have {game_players.shape[0]} players and {game_characters.shape[0]}  characters')

        positions = list(range(1, game_players.shape[0] + 1))
        random.shuffle(positions)
        table = Texttable()
        table.header(['User', 'Role Assigned'])
        for idx, player in game_players.iterrows():
            user = ctx.guild.get_member(player['discord_user_id'])
            character_id = game_characters['character_id'].iloc[idx]
            character = db.get_table('character', indicators={'character_id': character_id}).iloc[0]

            table.add_row([user, character["character_display_name"]])

            db.update_table('game_player', {'character_id': character_id, 'starting_character_id': character_id,
                                            'position': positions[idx], 'vitals': 'alive',
                                            'current_affiliation': character['starting_affiliation']},
                            {'game_id': game_id, 'discord_user_id': player['discord_user_id']})

            # game_players = db.get_table('game_player', indicators={'game_id': game_id})

        await ctx.channel.send(f'```{table.draw()}```')
        await update_game_permissions(ctx, game_id, 'day')
        return


async def game_has_correct_chars(ctx, game_id, scenario) -> bool:
    game_players = db.get_table('game_player', indicators={'game_id': game_id})
    game_characters = db.get_table('game_character', indicators={'game_id': game_id, 'scenario_name': scenario}).sample(
        frac=1)
    if game_players.shape[0] != game_characters.shape[0] or game_players.shape[0] <= 0:
        await ctx.channel.send(
            f'players ({game_players.shape[0]}) and characters ({game_characters.shape[0]}) must be equal')
        return False
    return True


async def phase_set(ctx, phase):
    game_data = await get_game(ctx.channel, game_status.ACTIVE)
    if game_data is not None and str(ctx.channel).lower() == globals.moderator_channel_name:
        if phase not in ['day', 'night']:
            await ctx.channel.send(f'not a valid phase')
            return

        game_id = game_data['game_id']
        await update_game_permissions(ctx, game_id, phase)

    # todo post when complete (maybe do that in update_permissions
    # todo split into functions for phase-day


async def info(ctx):
    game_data = await get_game(ctx.channel)
    if game_data is not None and str(ctx.channel).lower() == globals.moderator_channel_name:
        game_id = game_data['game_id']

        table = Texttable()
        table.header(['ID', 'Name', 'Status', 'Phase', 'Start Date', 'Players'])  # todo add in character if deceased

        table.add_row([game_data['game_id'], game_data['game_name'], game_data['status'], game_data['phase'],
                       game_data['start_date'], game_data['number_of_players']])

        await ctx.channel.send(f'```{table.draw()}```')


async def player_status(ctx):
    game_data = await get_game(ctx.channel)  # todo set to only "active" after testing
    if game_data is not None and str(ctx.channel).lower() == globals.moderator_channel_name:
        game_id = game_data['game_id']

        status_post = get_game_player_status(ctx, game_id)
        await ctx.channel.send(f'{status_post}')


async def start(ctx, scenario):
    game_data = await get_game(ctx.channel, game_status.RECRUITING)
    if game_data is not None and str(ctx.channel).lower() == globals.moderator_channel_name:
        game_id = game_data['game_id']

        correct_chars = await game_has_correct_chars(ctx, game_id, scenario)
        if not correct_chars:
            return

        db.update_table('game', {'status': game_status.INITIALIZING.value},
                        {'game_id': game_id})  # todo add number of players

        await game_assign_characters(ctx, scenario)
        await update_game_permissions(ctx, game_id, 'day')

        status_post = get_game_player_status(ctx, game_id)
        await ctx.channel.send(f'{status_post}')  # todo send this to the "player" channel

        num_of_players = db.get_table('game_player', indicators={'game_id': game_id}).shape[0]

        db.update_table('game', {'status': game_status.ACTIVE.value, 'number_of_players': num_of_players},
                        {'game_id': game_id})


async def complete(ctx):
    game_data = await get_game(ctx.channel, game_status.ACTIVE)
    if game_data is not None and str(ctx.channel).lower() == globals.moderator_channel_name:
        game_id = game_data['game_id']

        db.update_table('game', {'status': game_status.COMPLETED.value, 'end_date': date.today()}, {'game_id': game_id})
