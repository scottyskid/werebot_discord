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
from globals import GameStatus
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


def draw_scenario_characters_table(scenario_id):
    scenario_character = db.select_table('scenario_character', indicators={'scenario_id': scenario_id},
                                         joins={'character': 'character_id'})
    scenario_character = scenario_character.sort_values('character_name')

    # groups characters into quantities rather than indvidual items
    characters = defaultdict(lambda: defaultdict(int))
    for idx, character in scenario_character.iterrows():
        characters[character['character_name']]['count'] += 1
        characters[character['character_name']]['weighting'] += character['weighting']

    table = Texttable()
    table.header(['Character', 'Quantity', 'Weighting'])

    total_count = 0
    total_weight = 0

    for key, value in characters.items():
        table.add_row([key, value['count'], value['weighting']])
        total_count += value['count']
        total_weight += value['weighting']

    table.add_row(['TOTAL', total_count, total_weight])

    return table


async def get_scenario_data(ctx, scenario_name):
    scenario_name = scenario_name.lower().replace(' ', '-')
    # todo check total characters added doesnt go over the max_duplicates in the character table

    game_data = await game.get_game(ctx.channel, GameStatus.RECRUITING)
    if game_data is not None and str(ctx.channel).lower() == globals.moderator_channel_name:
        game_id = game_data['game_id']
    elif str(ctx.channel).lower() == 'testing':  # todo figure out what channels to allow this in
        game_id = None
    elif game_data is not None:
        return
    else:
        await ctx.channel.send(f'not allowed on this channel')
        return

    scenario_data = db.select_table('scenario', indicators={'scenario_name': scenario_name})
    scenario_data = scenario_data[scenario_data['game_id'].isin([game_id, None])]
    if scenario_data.empty:
        await ctx.channel.send(f'there is no scenario matching that id available to this game')
        return

    scenario = scenario_data.iloc[0]
    return scenario


async def create(ctx, scenario_name, scope):
    if scope == 'local':
        game_data = await game.get_game(ctx.channel, GameStatus.RECRUITING)
        if game_data is not None and str(ctx.channel).lower() == globals.moderator_channel_name:
            game_id = game_data['game_id']
        else:
            await ctx.channel.send(f'local scope must be created in side a moderator channel of a game')
            return
    elif scope == 'global':
        game_id = None
    else:
        await ctx.channel.send(f'scope provided must be either "local" or "global"')
        return

    scenario_data = db.select_table('scenario')

    if scenario_name in scenario_data[
        'scenario_name'].tolist():  # todo have this only as a requirement insiide the same scope
        await ctx.channel.send(f'that scenario name is already taken, choose another')

    db.insert_into_table('scenario', {'game_id': game_id, 'scenario_name': scenario_name, 'scope': scope})

    # todo send a message saying what the id is


async def list(ctx):
    game_data = await game.get_game(ctx.channel, GameStatus.RECRUITING)
    if game_data is not None and str(ctx.channel).lower() == globals.moderator_channel_name:
        game_id = game_data['game_id']
    elif str(ctx.channel).lower() == 'testing':  # todo figure out what channels to allow this in
        game_id = None
    elif game_data is not None:
        return
    else:
        await ctx.channel.send(f'not allowed on this channel')
        return

    scenario_data = db.select_table('scenario',
                                    joins={'scenario_character': 'scenario_id', 'character': 'character_id'})
    scenario_data = scenario_data[scenario_data['game_id'].isin([game_id, None])]
    scenario_data['count'] = 1

    scenario_data = scenario_data.groupby(['scenario_id', 'scenario_name', 'scope']).sum()[
        ['count', 'weighting']].reset_index()

    table = Texttable()
    table.header(['ID', 'Name', 'Scope', 'Characters', 'Weighting'])

    for idx, row in scenario_data.iterrows():
        table.add_row([row['scenario_id'], row['scenario_name'], row['scope'], row['count'], row['weighting']])

    await ctx.channel.send(f'```{table.draw()}```')


async def character_add(ctx, characters, scenario_name):
    characters = characters.lower()
    scenario_name = scenario_name.lower().replace(' ', '-')
    scenario = await get_scenario_data(ctx, scenario_name)
    if scenario is None:
        return
    scenario_id = scenario['scenario_id']

    character_data = db.select_table('character')
    character_list = await parse_character_list(ctx, characters)
    for character in character_list:

        character_info = character_data[character_data['character_name'] == character]
        if character_info.empty:
            await ctx.channel.send(f'no character named {character}, this has not been included')
            continue

        print(f'adding character {character}')
        character_info = character_info.iloc[0]

        scenario_character_data = {'character_id': character_info['character_id'],
                                   'scenario_id': scenario_id}
        db.insert_into_table('scenario_character', scenario_character_data)

    table = draw_scenario_characters_table(scenario_id)
    await ctx.channel.send(f'Updated Build "{scenario_name}"\n```{table.draw()}```')
    return


async def character_remove(ctx, characters, scenario_name):
    characters = characters.lower()
    scenario_name = scenario_name.lower().replace(' ', '-')
    scenario = await get_scenario_data(ctx, scenario_name)
    if scenario is None:
        return
    scenario_id = scenario['scenario_id']

    game_character_data = db.select_table('scenario_character',
                                          indicators={'scenario_id': scenario_id},
                                          joins={'character': 'character_id'})
    character_list = await parse_character_list(ctx, characters)

    scenario_character_ids_remove = []
    for character in character_list:
        selected = game_character_data[game_character_data['character_name'] == character]
        selected = selected[~selected['scenario_character_id'].isin(scenario_character_ids_remove)]
        if selected.empty:
            await ctx.channel.send(
                f'character "{character}" was not found in scenario "{scenario_name}" and has not been remove (could be due specifying more than were in the build)')
            continue
        row = selected.iloc[0]
        scenario_character_ids_remove.append(row['scenario_character_id'])

    for cur_id in scenario_character_ids_remove:
        db.delete_from_table('scenario_character', indicators={'scenario_character_id': cur_id})

    table = draw_scenario_characters_table(scenario_id)
    await ctx.channel.send(f'Updated Scenario "{scenario_name}"\n```{table.draw()}```')


async def character_list(ctx, scenario_name):
    scenario_name = scenario_name.lower().replace(' ', '-')
    scenario = await get_scenario_data(ctx, scenario_name)
    if scenario is None:
        return
    scenario_id = scenario['scenario_id']

    table = draw_scenario_characters_table(scenario_id)
    await ctx.channel.send(f'Scenario "{scenario_name}"\n```{table.draw()}```')


async def purge(ctx, scenario_name):
    scenario_name = scenario_name.lower().replace(' ', '-')
    scenario = await get_scenario_data(ctx, scenario_name)
    if scenario is None:
        return
    scenario_id = scenario['scenario_id']

    db.delete_from_table('scenario_character', indicators={'scenario_id': scenario_id})
    db.delete_from_table('scenario', indicators={'scenario_id': scenario_id})
    await ctx.channel.send(f'Purged scenario "{scenario_name} and its characters"')
