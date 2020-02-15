import logging
import os
import sqlite3

import pandas as pd

import globals


def create_database_tables():
    with sqlite3.connect(globals.DB_FILE_LOCATION) as db:
        try:
            cursor = db.cursor()

            # create table GAME
            cursor.execute('''CREATE TABLE IF NOT EXISTS game(
                                    game_id INTEGER PRIMARY KEY AUTOINCREMENT
                                    ,discord_category_id INTEGER NOT NULL
                                    ,game_name TEXT
                                    ,start_date DATE
                                    ,end_date DATE
                                    ,number_of_players INTEGER
                                    ,status TEXT
                                    ,game_length INTEGER
                                    ,created_datetime DATETIME DEFAULT (datetime('now'))
                                    ,modified_datetime DATETIME DEFAULT (datetime('now'))
                               )''')
            # create table CHANNEL
            cursor.execute('''CREATE TABLE IF NOT EXISTS channel(
                                    channel_id INTEGER PRIMARY KEY AUTOINCREMENT
                                    ,channel_name TEXT
                               )''')
            # create table CHARACTER
            cursor.execute('''CREATE TABLE IF NOT EXISTS character(
                                    character_id INTEGER PRIMARY KEY AUTOINCREMENT
                                    ,character_name TEXT
                                    ,char_short_description TEXT
                                    ,char_card_description TEXT
                                    ,char_full_description TEXT
                                    ,weighting INTEGER
                                    ,max_duplicates INTEGER
                                    ,starting_affiliation TEXT
                                    ,seen_affiliation TEXT
                                    ,created_datetime DATETIME DEFAULT (datetime('now'))
                                    ,modified_datetime DATETIME DEFAULT (datetime('now'))
                                )''')
            # create table EVENT
            cursor.execute('''CREATE TABLE IF NOT EXISTS event(
                                    event_id INTEGER PRIMARY KEY AUTOINCREMENT
                                    ,event_name TEXT
                                    ,event_description TEXT
                                    ,created_datetime DATETIME DEFAULT (datetime('now'))
                                    ,modified_datetime DATETIME DEFAULT (datetime('now'))
                                )''')
            # create table GAME_PLAYER
            cursor.execute('''CREATE TABLE IF NOT EXISTS game_player(
                                    game_player_id INTEGER PRIMARY KEY AUTOINCREMENT
                                    ,game_id INTEGER NOT NULL
                                    ,character_id INTEGER NOT NULL
                                    ,starting_character_id INTEGER NOT NULL
                                    ,discord_user_id INTEGER NOT NULL
                                    ,current_affiliation TEXT
                                    ,position INTEGER
                                    ,living BOOLEAN DEFAULT True
                                    ,rounds_survived INTEGER
                                    ,result TEXT
                                    ,created_datetime DATETIME DEFAULT (datetime('now'))
                                    ,modified_datetime DATETIME DEFAULT (datetime('now'))
                                    ,FOREIGN KEY(game_id) REFERENCES game(game_id)
                                    ,FOREIGN KEY(character_id) REFERENCES character(character_id)
                                    ,FOREIGN KEY(starting_character_id) REFERENCES character(character_id)
                                )''')
            # create table GAME_PLAYER_CONDITION
            cursor.execute('''CREATE TABLE IF NOT EXISTS game_player_condition (
                                    game_player_condition_id INTEGER PRIMARY KEY AUTOINCREMENT
                                    ,game_player_id INTEGER NOT NULL
                                    ,condition TEXT
                                    ,round_received INTEGER
                                    ,active BOOLEAN DEFAULT True
                                    ,duration INTEGER
                                    ,created_datetime DATETIME DEFAULT (datetime('now'))
                                    ,modified_datetime DATETIME DEFAULT (datetime('now'))
                                    ,FOREIGN KEY(game_player_id) REFERENCES game_player(game_player_id)
                                )''')
            # create table GAME_EVENT
            cursor.execute('''CREATE TABLE IF NOT EXISTS game_event(
                                    game_event_id INTEGER PRIMARY KEY AUTOINCREMENT
                                    ,game_id INTEGER NOT NULL
                                    ,event_id INTEGER NOT NULL
                                    ,event_taken TEXT
                                    ,player_acting_id INTEGER
                                    ,player_affected_id INTEGER
                                    ,round INTEGER
                                    ,datetime DATETIME DEFAULT (datetime('now'))
                                    ,created_datetime DATETIME DEFAULT (datetime('now'))
                                    ,modified_datetime DATETIME DEFAULT (datetime('now'))
                                    ,FOREIGN KEY(game_id) REFERENCES game(game_id)
                                    ,FOREIGN KEY(event_id) REFERENCES event(event_id)
                                    ,FOREIGN KEY(player_acting_id) REFERENCES game_player(game_player_id)
                                    ,FOREIGN KEY(player_affected_id) REFERENCES game_player(game_player_id)
                                )''')
            # create table GAME_CHANNEL
            cursor.execute('''CREATE TABLE IF NOT EXISTS game_channel(
                                    game_channel_id INTEGER PRIMARY KEY AUTOINCREMENT
                                    ,game_id INTEGER NOT NULL
                                    ,channel_id INTEGER NOT NULL
                                    ,discord_channel_id INTEGER NOT NULL
                                    ,name TEXT
                                    ,created_datetime DATETIME DEFAULT (datetime('now'))
                                    ,modified_datetime DATETIME DEFAULT (datetime('now'))
                                    ,FOREIGN KEY(game_id) REFERENCES game(game_id)
                                    ,FOREIGN KEY(channel_id) REFERENCES channel(channel_id)
                                )''')
            # create table GAME_PERMISSION
            cursor.execute('''CREATE TABLE IF NOT EXISTS character_permission(
                                    character_permission_id INTEGER PRIMARY KEY AUTOINCREMENT
                                    ,character_id INTEGER NOT NULL
                                    ,channel_id INTEGER NOT NULL
                                    ,permission_name TEXT 
                                    ,permission_level TEXT
                                    ,day_night TEXT
                                    ,alive BOOLEAN
                                    ,created_datetime DATETIME DEFAULT (datetime('now'))
                                    ,modified_datetime DATETIME DEFAULT (datetime('now'))
                                    ,FOREIGN KEY(character_id) REFERENCES character(character_id)
                                    ,FOREIGN KEY(channel_id) REFERENCES channel(channel_id)
                                )''')
            # create table GAME_VOTES
            cursor.execute('''CREATE TABLE IF NOT EXISTS game_vote(
                                    game_vote_id INTEGER PRIMARY KEY AUTOINCREMENT
                                    ,game_id INTEGER NOT NULL
                                    ,voter INTEGER 
                                    ,nominee INTEGER
                                    ,vote_type TEXT
                                    ,round INTEGER
                                    ,datetime DATETIME DEFAULT (datetime('now'))
                                    ,created_datetime DATETIME DEFAULT (datetime('now'))
                                    ,modified_datetime DATETIME DEFAULT (datetime('now'))
                                    ,FOREIGN KEY(game_id) REFERENCES game(game_id)
                                    ,FOREIGN KEY(voter) REFERENCES game_player(game_player_id)
                                    ,FOREIGN KEY(nominee) REFERENCES game_player(game_player_id)
                                )''')

            db.commit()
        except Exception as e:
            db.rollback()
            raise e

def insert_into_table(table, data):
    columns = ''
    values  = []

    if type(data) == dict: # todo extent do dataframes and lists
        for key, value in data.items():
            if value is None:
                continue
            columns += f'{key}, '
            values.append(value)
        values = tuple(values)


    with sqlite3.connect(globals.DB_FILE_LOCATION) as db:
        try:
            cursor = db.cursor()
            qmarks = '?,' * len(values)
            query = f"INSERT INTO {table} ({columns[:-2]}) VALUES ({qmarks[:-1]});"

            cursor.execute(query, values)
        except Exception as e:
            db.rollback()
            raise e



def game_insert(discord_category_id, game_name, start_date=None, end_date=None, number_of_players=None, status=None, game_length=None):
    insert_into_table('game', locals())



def get_table(table):
    with sqlite3.connect(globals.DB_FILE_LOCATION) as db:
        return pd.read_sql_query(f'select * from {table}', db)


def get_table_schema(table):
    with sqlite3.connect(globals.DB_FILE_LOCATION) as db:
        return pd.read_sql_query(f"pragma table_info('{table}')", db)


if __name__ == '__main__':
    globals.setup_logging(globals.BASE_DIR / 'logging_config.yaml', logging.DEBUG)
    try:
        os.remove(globals.DB_FILE_LOCATION)
    except FileNotFoundError:
        pass
    create_database_tables()

    # game_insert(1, 'FIRE', number_of_players=1, game_length=1)
    #
    # # insert_into_table('game', {'discord_category_id':1, 'game_name':'FIRE', 'start_date':None, 'end_date':'NULL', 'number_of_players':None})
    #
    # print(get_table_schema('game'))
    # print(get_table('game').iloc[0])
    # print(get_table('game').dtypes)


