"""event.py manages all game events that take place and character interactions

This file sets the logic for how abilities interact and events that happen in the game
"""

import database as db
import globals
from globals import GameStatus
from werewolf import game


async def death(ctx, player):
    game_data = await game.get_game(ctx.channel, GameStatus.ACTIVE)
    if game_data is not None and str(ctx.channel).lower() == globals.moderator_channel_name:
        game_id = game_data['game_id']

        found_member = None
        for member in ctx.guild.members:
            if str(member) == player:
                found_member = member
                break

        if found_member is None:
            await ctx.channel.send(f'There is no member called "{player}"')
            return

        member_data = db.select_table("game_player",
                                      indicators={'game_id': game_id, 'discord_user_id': found_member.id})
        if member_data.empty:
            await ctx.channel.send(f'"{player}" is not a part of this game')
            return

        # todo check if already dead

        db.update_table("game_player", data_to_update={'vitals': 'deceased'},
                        update_conditions={'game_id': game_id, 'discord_user_id': found_member.id})

        role_data = db.select_table('game_role', joins={'role': 'role_id'}, indicators={'game_id': game_id})
        deceased_role_id = ctx.guild.get_role(
            role_data[role_data['default_value'] == 'deceased'].iloc[0]['discord_role_id'])
        alive_role_id = ctx.guild.get_role(role_data[role_data['default_value'] == 'alive'].iloc[0]['discord_role_id'])
        await found_member.add_roles(deceased_role_id)
        await found_member.remove_roles(alive_role_id)
