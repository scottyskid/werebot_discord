""" scenario.py stores all elements to build and retrieve scenarios to set up games

This is a file to assist with building scenarios to put into games
a Scenario is the character cards that will potentially be included in the game
along wtih randomizes to pick scenarios for you
"""

from collections import defaultdict
import logging

from texttable import Texttable

import database as db
import globals
from globals import game_status
from werewolf import game


async def parse_character_list(ctx, characters):
    character_split = characters.split(',')
    character_list = []
    for character in character_split:
        split = character.split('|')
        if len(split) == 1:
            character_list.append(character)
            continue
        elif len(split) == 2:
            if split[1].isdigit():
                for i in range(int(split[1])):
                    character_list.append(split[0])
                continue

        # left here to catch anything that isnt parsed by the if above
        await ctx.channel.send(f'invalid argument "{character}" and has been ignored')

    return character_list


def characters_in_build_table(game_id, build):
    game_character = db.get_table('game_character', indicators={'game_id': game_id, 'build_name': build},
                                  joins={'character': 'character_id'})
    game_character = game_character.sort_values('character_name')

    # groups characters into quantities rather than indvidual items
    characters = defaultdict(int)
    for idx, character in game_character.iterrows():
        characters[character['character_name']] += 1

    table = Texttable()
    table.header(['Character', 'Quantity'])

    for key, value in characters.items():
        table.add_row([key, value])

    table.add_row(['TOTAL', game_character.shape[0]])

    return table


async def character_add(ctx, characters, build):
    build = build.lower()
    characters = characters.lower()
    # todo check total characters added doesnt go over the max_duplicates in the character table

    game_data = await game.get_game(ctx.channel, game_status.RECRUITING)
    if game_data is not None and str(ctx.channel).lower() == globals.moderator_channel_name:
        game_id = game_data['game_id']

        character_data = db.get_table('character')
        character_list = await parse_character_list(ctx, characters)
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

        table = characters_in_build_table(game_id, build)
        await ctx.channel.send(f'Updated Build "{build}"\n```{table.draw()}```')
        return


async def character_remove(ctx, characters, build):
    build = build.lower()
    characters = characters.lower()

    game_data = await game.get_game(ctx.channel, game_status.RECRUITING)
    if game_data is not None and str(ctx.channel).lower() == globals.moderator_channel_name:
        game_id = game_data['game_id']

        game_character_data = db.get_table('game_character', indicators={'game_id': game_id, 'build_name': build},
                                           joins={'character': 'character_id'})
        character_list = await parse_character_list(ctx, characters)

        game_character_ids_remove = []
        for character in character_list:
            selected = game_character_data[game_character_data['character_name'] == character]
            selected = selected[~selected['game_character_id'].isin(game_character_ids_remove)]
            if selected.empty:
                await ctx.channel.send(
                    f'character "{character}" was not found in build "{build}" and has not been remove (could be due specifying more than were in the build)')
                continue
            row = selected.iloc[0]
            game_character_ids_remove.append(row['game_character_id'])

        for cur_id in game_character_ids_remove:
            db.delete_from_table('game_character', indicators={'game_character_id': cur_id})

        table = characters_in_build_table(game_id, build)
        await ctx.channel.send(f'Updated Build "{build}"\n```{table.draw()}```')


async def builds_available(ctx):
    game_data = await game.get_game(ctx.channel, game_status.RECRUITING)
    if game_data is not None and str(ctx.channel).lower() == globals.moderator_channel_name:
        game_id = game_data['game_id']

        builds = db.get_table('game_character', indicators={'game_id': game_id}, joins={'character': 'character_id'})
        builds = builds.groupby('build_name').count().reset_index()[['build_name', 'game_character_id']]

        table = Texttable()
        table.header(['Build Name', 'Total Characters'])

        for idx, row in builds.iterrows():
            table.add_row([row['build_name'], row['game_character_id']])

        await ctx.channel.send(f'```{table.draw()}```')


async def character_list(ctx, build):
    build = build.lower()

    game_data = await game.get_game(ctx.channel, game_status.RECRUITING)
    if game_data is not None and str(ctx.channel).lower() == globals.moderator_channel_name:
        game_id = game_data['game_id']

        table = characters_in_build_table(game_id, build)

        await ctx.channel.send(f'Build "{build}"\n```{table.draw()}```')


async def character_build_purge(ctx, build):
    build = build.lower()

    game_data = await game.get_game(ctx.channel, game_status.RECRUITING)
    if game_data is not None and str(ctx.channel).lower() == globals.moderator_channel_name:
        game_id = game_data['game_id']

        db.delete_from_table('game_character', indicators={'game_id': game_id, 'build_name': build})
        await ctx.channel.send(f'Purged characters in build "{build}"')