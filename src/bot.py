# bot.py

from collections import defaultdict
from datetime import date, timedelta
from dateutil.parser import parse
import logging

import discord
from discord.ext import commands
import pandas as pd

import database as db
import globals

bot = commands.Bot(command_prefix='!')

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')


def gen_role_overwrites_dict_channel_create(guild, game_name, channel_id=None):
    """
    generates the overwrite dictionary used in creating the new channels
    """
    perm_table = db.get_table('role_permission', joins={'role':'role_id'})

    dfs = [perm_table[perm_table['channel_id'].isna()]]
    # merges the category defaults with the channel specific
    if channel_id is not None:
        dfs.append(perm_table[perm_table['channel_id']==channel_id])
    perm_table = pd.concat(dfs)

    # creates the the consolodiation dict to be used in the final dict
    perm_dict = defaultdict(dict)
    for idx, row in perm_table.iterrows():
        permission_value = None if row['permission_value'] is None else row['permission_value'] == 1
        perm_dict[row['role_name']][row['permission_name']] = permission_value

    # get the value from role that checks it is the default role
    role = db.get_table('role')
    default_everyone = role[role['default_everyone'] == 1]['role_name'].iloc[0]

    final_dict = {}
    for key, value in perm_dict.items():
        if key == default_everyone:
            role = guild.default_role
        else:
            role = None
            for role in guild.roles:
                if role.name == f'{game_name}-{key}':
                    break
                else:
                    role = None
        if role is None:
            statement = f'was passed a Role of  None when should have been {key}'
            logging.warning(statement)
            print(statement)

        final_dict[role] = discord.PermissionOverwrite(**value)
    return final_dict



@bot.command(name='game-create')
@commands.has_role('Admin')
async def game_init(ctx, game_name='WOLF', starting_date=(date.today() + timedelta(days=1)).strftime("%y-%m-%d")):
    game_name = game_name.upper()

    # check that the inputs  are valuid
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

    if existing_category is not None:
        await ctx.message.channel.send(f'{game_name} game already exists')
        return
    # else:
    print(f'Creating a new game: {game_name}')
    ## create roles (had to be done before game)
    role = db.get_table('role')
    roles_created = {}
    for idx, row in role.iterrows():
        if row['default_everyone'] == 1:
            continue
        created_role = await guild.create_role(name=f'{game_name}-{row["role_name"]}')
        roles_created[row['role_id']] = created_role

        print(f'role created named {created_role.name}')

    category_permissions = gen_role_overwrites_dict_channel_create(guild, game_name)

    game_category = await guild.create_category(game_name, overwrites=category_permissions)


    #send an announcemnt for the game
    announcement_channel = bot.get_channel(676761050133168148)
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


    #add role data to db (has to be added after game createion)
    for idx, role in roles_created.items():

        game_role_data = {'game_id': int(game_id),
                     'role_id': idx,
                     'discord_role_id': role.id,
                     'game_role_name': role.name}
        db.insert_into_table('game_role', game_role_data)

    channels = db.get_table('channel')
    for idx, channel in channels.iterrows():
        overwrites = gen_role_overwrites_dict_channel_create(guild, game_name, channel['channel_id'])
        channel_options = {'name': channel['channel_name'],
                            'overwrites':overwrites,
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

    print(f'Removing game {category.name}')

    game_data = db.get_table('game', {'discord_category_id':category.id}).iloc[0]
    game_id = game_data['game_id']

    for ch in category.channels:
        await ch.delete()
    await category.delete()


    game_role = db.get_table('game_role', {'game_id': game_id})
    for idx, row in game_role.iterrows():
        role = guild.get_role(row['discord_role_id'])
        await role.delete()



@bot.command(name='character-add', help='Add a character to staging, can only be used in a game category')
@commands.has_role('Admin')
async def character_add(ctx, characters, build='primary'):
    build = build.lower()
    characters = characters.lower()

    category = ctx.channel.category
    # print(ctx.category)
    game_data = db.get_table('game', {'discord_category_id': category.id})
    if not game_data.empty:
        game_data = game_data.iloc[0]
        game_id = game_data['game_id']

        if game_data['status'].lower() != 'recruiting':
            await ctx.channel.send(f'{game_data["game_name"]} has left the recruiting stage, this will have no affect')
            return

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

        await ctx.channel.send(f'SUCCESS! you have a total of {game_character.shape[0]} characters in build {build}')
        return


@bot.command(name='character-build-list', help='List all characters in selected build')
@commands.has_role('Admin')
async def character_list(ctx, build='primary'):
    build = build.lower()

    category = ctx.channel.category
    # print(ctx.category)
    game_data = db.get_table('game', {'discord_category_id': category.id})
    if not game_data.empty:
        game_data = game_data.iloc[0]
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

    category = ctx.channel.category
    # print(ctx.category)
    game_data = db.get_table('game', {'discord_category_id': category.id})
    if not game_data.empty:
        game_data = game_data.iloc[0]
        game_id = game_data['game_id']
        db.delete_from_table('game_character', indicators={'game_id': game_id, 'build_name': build})

@bot.event
async def on_raw_reaction_add(payload):
    if payload.member.bot == True:
        return
    # todo only check for  game-announcements
    game_table = db.get_table('game') # todo change to new structure
    game_table = game_table[game_table['status'].str.lower() == 'recruiting']

    guild = bot.get_guild(payload.guild_id)

    # get the value from role that checkes it is the defualt role
    role = db.get_table('role')
    default_player = role[role['default_player'] == 1]['role_name'].iloc[0]

    for idx, row in game_table.iterrows():
        if payload.message_id == row['discord_announce_message_id'] and payload.emoji.name == '🐺':

            member = guild.get_member(payload.user_id)
            role = discord.utils.get(guild.roles, name=f"{row['game_name']}-{default_player}")
            await member.add_roles(role)

            # add member to database
            game_player_data = {'game_id': row['game_id'],
                         'discord_user_id': member.id}
            db.insert_into_table('game_player', game_player_data)

            return


@bot.event
async def on_raw_reaction_remove(payload):
    game_table = db.get_table('game')
    game_table = game_table[game_table['status'].str.lower() == 'recruiting']

    # get the value from role that checkes it is the defualt role
    role = db.get_table('role')
    default_player = role[role['default_player'] == 1]['role_name'].iloc[0]

    guild = bot.get_guild(payload.guild_id)
    for idx, row in game_table.iterrows():
        if payload.message_id == row['discord_announce_message_id'] and payload.emoji.name == globals.GAME_REACTION_EMOJI:
            member = guild.get_member(payload.user_id)

            role = discord.utils.get(guild.roles, name=f"{row['game_name']}-{default_player}")
            await member.remove_roles(role)

            db.delete_from_table('game_player', {'game_id': row['game_id'], 'discord_user_id': member.id})

            return


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.errors.CheckFailure):
        await ctx.send('You do not have the correct role for this command.')
    else:
        raise error

