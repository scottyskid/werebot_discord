"""bot.py sets up all bot commands

This file manages all bot interactions including commands and events
not much work is done in this file, it is mostly designed as a switching board
to point events and commands to certain logic
"""

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
from globals import game_status
from werewolf import game, event, scenario

bot = commands.Bot(command_prefix='!')

def setup(bot):
    bot.add_cog(Game(bot))
    bot.add_cog(Scenario(bot))
    bot.add_cog(Event(bot))

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')


class Game(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='game-create',
                      help='Create a game and its associated Category, channels, roles and permissions')
    @commands.has_role('Admin')
    async def game_create(self, ctx, game_name='WOLF',
                          starting_date=(date.today() + timedelta(days=1)).strftime("%y-%m-%d")):
        return await game.create(ctx, game_name, starting_date)

    @commands.command(name='game-remove', help='WANING: Removes the entire game from the server (unrecoverable)')
    @commands.has_role('Admin')
    async def game_remove(self, ctx):
        return await game.remove(ctx)

    @commands.command(name='game-info', help="prints info about the current game")
    @commands.has_role('Admin')
    async def game_info(self, ctx):
        return await game.info(ctx)

    @commands.command(name='game-start', help="starts the game, assigns and updates permsissions")
    @commands.has_role('Admin')
    async def game_start(self, ctx, scenario='primary'):
        return await game.start(ctx, scenario)

    @commands.command(name='game-complete', help="completes a game")
    @commands.has_role('Admin')
    async def game_complete(self, ctx):
        return await game.complete(ctx)

    @commands.command(name='game-player-status', help="prints out the current state of all players")
    @commands.has_role('Admin')
    async def game_player_status(self, ctx):
        return await game.player_status(ctx)

    @commands.command(name='game-phase-set', help="change the game phase, values accepted [day, night]")
    @commands.has_role('Admin')
    async def game_phase_set(self, ctx, phase):
        return await game.phase_set(ctx, phase)

    @commands.command(name='game-assign-characters',
                      help='Deprechiated. Randomly assigns the characters of a scenario to characters')
    @commands.has_role('Admin')
    async def game_assign_characters(self, ctx, scenario='primary'):
        return await game.game_assign_characters(ctx, scenario)


class Scenario(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='scenario-create', help='Creates a new scenario')
    @commands.has_role('Admin')
    async def scenario_create(self, ctx, scenario_name='primary',
                              scope='local'):  # todo remove scenario_name default when finished testing
        return await scenario.create(ctx, scenario_name, scope)

    @commands.command(name='scenario-list-available', help='List all available scenarios to this game')
    @commands.has_role('Admin')
    async def scenario_list(self, ctx):
        return await scenario.list(ctx)

    @commands.command(name='scenario-character-add',
                      help='Add a character to scenario, lower case comma seperated list of characters to add. Pass quantities after name seperated by pipe "|". NO SPACES. e.g. "werewolf|2,villager|4,seer"')
    @commands.has_role('Admin')
    async def scenario_character_add(self, ctx, characters, scenario_name='primary'):
        return await scenario.character_add(ctx, characters, scenario_name)

    @commands.command(name='scenario-character-remove',
                      help='Remove a character from a scenario, characters can be provieded in the same manner as character-add')
    @commands.has_role('Admin')
    async def character_remove(self, ctx, characters, scenario_name='primary'):
        return await scenario.character_remove(ctx, characters, scenario_name)

    @commands.command(name='scenario-character-list', help='List all characters in selected scenario')
    @commands.has_role('Admin')
    async def character_list(self, ctx, scenario_name='primary'):
        return await scenario.character_list(ctx, scenario_name)

    @commands.command(name='scenario-purge', help='Removes all characters in selected scenario')
    @commands.has_role('Admin')
    async def character_scenario_purge(self, ctx, scenario_name='primary'):
        return await scenario.purge(ctx, scenario_name)


class Event(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='death', help='provide a characters name and tag to kill in the form of "player#0000"')
    @commands.has_role('Admin')
    async def death(self, ctx, player):
        return await event.death(ctx, player)


#todo make these into one function
@bot.event
async def on_raw_reaction_add(payload):
    if payload.member.bot == True:
        return
    channel = bot.get_channel(payload.channel_id)
    if str(channel) == 'game-announcements':
        game_table = db.select_table('game', {'status': game_status.RECRUITING.value})
        # game_table = game_table[game_table['status'].str.lower() == ]

        guild = bot.get_guild(payload.guild_id)

        for idx, row in game_table.iterrows():
            if payload.message_id == row[
                'discord_announce_message_id'] and payload.emoji.name == globals.GAME_REACTION_EMOJI:
                role_id = db.select_table('game_role', {'game_id': row['game_id'], 'default_value': 'alive'},
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
    game_table = db.select_table('game', {'status': game_status.RECRUITING.value})

    channel = bot.get_channel(payload.channel_id)
    if str(channel) == 'game-announcements':

        guild = bot.get_guild(payload.guild_id)
        for idx, row in game_table.iterrows():
            if payload.message_id == row[
                'discord_announce_message_id'] and payload.emoji.name == globals.GAME_REACTION_EMOJI:
                role_id = db.select_table('game_role', {'game_id': row['game_id'], 'default_value': 'alive'},
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

