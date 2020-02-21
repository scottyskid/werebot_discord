from __future__ import print_function
from datetime import datetime
import logging
import os
import sqlite3

from dotenv import load_dotenv
from gsheets import Sheets
import os.path
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
                                    ,discord_announce_message_id INTEGER NOT NULL
                                    ,game_name TEXT
                                    ,start_date DATE
                                    ,end_date DATE
                                    ,number_of_players INTEGER
                                    ,status TEXT
                                    ,phase TEXT
                                    ,game_length INTEGER
                                    ,created_datetime DATETIME DEFAULT (datetime('now', 'localtime'))
                                    ,modified_datetime DATETIME DEFAULT (datetime('now', 'localtime'))
                               )''')
            # create table CHANNEL
            cursor.execute('''CREATE TABLE IF NOT EXISTS channel(
                                    channel_id INTEGER PRIMARY KEY
                                    ,channel_name TEXT
                                    ,channel_order INTEGER
                                    ,channel_topic TEXT
                                    ,channel_type TEXT
                                    ,created_datetime DATETIME DEFAULT (datetime('now', 'localtime'))
                                    ,modified_datetime DATETIME DEFAULT (datetime('now', 'localtime'))
                               )''')
            # create table CHARACTER
            cursor.execute('''CREATE TABLE IF NOT EXISTS character(
                                    character_id INTEGER PRIMARY KEY
                                    ,character_display_name TEXT
                                    ,character_name TEXT
                                    ,weighting INTEGER
                                    ,max_duplicates INTEGER
                                    ,difficulty INTEGER
                                    ,starting_affiliation TEXT
                                    ,seen_affiliation TEXT
                                    ,char_short_description TEXT
                                    ,char_card_description TEXT
                                    ,char_full_description TEXT
                                    ,created_datetime DATETIME DEFAULT (datetime('now', 'localtime'))
                                    ,modified_datetime DATETIME DEFAULT (datetime('now', 'localtime'))
                                )''')
            # create table EVENT
            cursor.execute('''CREATE TABLE IF NOT EXISTS event(
                                    event_id INTEGER PRIMARY KEY
                                    ,event_name TEXT
                                    ,event_description TEXT
                                    ,character_acting_id INTEGER
                                    ,created_datetime DATETIME DEFAULT (datetime('now', 'localtime'))
                                    ,modified_datetime DATETIME DEFAULT (datetime('now', 'localtime'))
                                    ,FOREIGN KEY(character_acting_id) REFERENCES character(character_id)
                                )''')
            # create table ROLE
            cursor.execute('''CREATE TABLE IF NOT EXISTS role(
                                    role_id INTEGER PRIMARY KEY
                                    ,role_name TEXT
                                    ,role_description TEXT
                                    ,default_value TEXT
                                    ,created_datetime DATETIME DEFAULT (datetime('now', 'localtime'))
                                    ,modified_datetime DATETIME DEFAULT (datetime('now', 'localtime'))
                                )''')
            # create table ROLE_PERMISSION
            cursor.execute('''CREATE TABLE IF NOT EXISTS role_permission (
                                   role_permission_id INTEGER PRIMARY KEY AUTOINCREMENT
                                   ,channel_id INTEGER
                                   ,permission_name INTEGER
                                   ,permission_value INTEGER
                                   ,role_id TEXT
                                   ,game_status TEXT
                                   ,game_phase TEXT
                                   ,created_datetime DATETIME DEFAULT (datetime('now', 'localtime'))
                                   ,modified_datetime DATETIME DEFAULT (datetime('now', 'localtime'))
                                   ,FOREIGN KEY(channel_id) REFERENCES channel(channel_id)
                                   ,FOREIGN KEY(role_id) REFERENCES role(role_id)
                               )''')
            # create table GAME_PLAYER
            cursor.execute('''CREATE TABLE IF NOT EXISTS game_player(
                                    game_player_id INTEGER PRIMARY KEY AUTOINCREMENT
                                    ,game_id INTEGER NOT NULL
                                    ,character_id INTEGER
                                    ,starting_character_id INTEGER
                                    ,discord_user_id INTEGER NOT NULL
                                    ,current_affiliation TEXT
                                    ,position INTEGER
                                    ,vitals BOOLEAN DEFAULT True
                                    ,rounds_survived INTEGER
                                    ,result TEXT
                                    ,created_datetime DATETIME DEFAULT (datetime('now', 'localtime'))
                                    ,modified_datetime DATETIME DEFAULT (datetime('now', 'localtime'))
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
                                    ,created_datetime DATETIME DEFAULT (datetime('now', 'localtime'))
                                    ,modified_datetime DATETIME DEFAULT (datetime('now', 'localtime'))
                                    ,FOREIGN KEY(game_player_id) REFERENCES game_player(game_player_id)
                                )''')
            # create table GAME_CHARACTER
            cursor.execute('''CREATE TABLE IF NOT EXISTS game_character (
                                   game_character_id INTEGER PRIMARY KEY AUTOINCREMENT
                                   ,game_id INTEGER NOT NULL
                                   ,character_id INTEGER NOT NULL
                                   ,build_name TEXT
                                   ,will_play BOOLEAN DEFAULT True
                                   ,created_datetime DATETIME DEFAULT (datetime('now', 'localtime'))
                                   ,modified_datetime DATETIME DEFAULT (datetime('now', 'localtime'))
                                   ,FOREIGN KEY(game_id) REFERENCES game(game_id)
                                   ,FOREIGN KEY(character_id) REFERENCES character(character_id)
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
                                    ,created_datetime DATETIME DEFAULT (datetime('now', 'localtime'))
                                    ,modified_datetime DATETIME DEFAULT (datetime('now', 'localtime'))
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
                                    ,created_datetime DATETIME DEFAULT (datetime('now', 'localtime'))
                                    ,modified_datetime DATETIME DEFAULT (datetime('now', 'localtime'))
                                    ,FOREIGN KEY(game_id) REFERENCES game(game_id)
                                    ,FOREIGN KEY(channel_id) REFERENCES channel(channel_id)
                                )''')
            # create table GAME_ROLE
            cursor.execute('''CREATE TABLE IF NOT EXISTS game_role(
                                    game_role_id INTEGER PRIMARY KEY AUTOINCREMENT
                                    ,game_id INTEGER NOT NULL
                                    ,role_id INTEGER NOT NULL
                                    ,discord_role_id INTEGER NOT NULL
                                    ,game_role_name TEXT
                                    ,created_datetime DATETIME DEFAULT (datetime('now', 'localtime'))
                                    ,modified_datetime DATETIME DEFAULT (datetime('now', 'localtime'))
                                    ,FOREIGN KEY(game_id) REFERENCES game(game_id)
                                    ,FOREIGN KEY(role_id) REFERENCES role(role_id)
                                )''')
            # create table CHARACTER_PERMISSION
            cursor.execute('''CREATE TABLE IF NOT EXISTS character_permission(
                                    character_permission_id INTEGER PRIMARY KEY AUTOINCREMENT
                                    ,character_id INTEGER NOT NULL
                                    ,channel_id INTEGER NOT NULL
                                    ,permission_name TEXT 
                                    ,permission_value TEXT
                                    ,game_status TEXT
                                    ,game_phase TEXT
                                    ,vitals_required TEXT
                                    ,created_datetime DATETIME DEFAULT (datetime('now', 'localtime'))
                                    ,modified_datetime DATETIME DEFAULT (datetime('now', 'localtime'))
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
                                    ,created_datetime DATETIME DEFAULT (datetime('now', 'localtime'))
                                    ,modified_datetime DATETIME DEFAULT (datetime('now', 'localtime'))
                                    ,FOREIGN KEY(game_id) REFERENCES game(game_id)
                                    ,FOREIGN KEY(voter) REFERENCES game_player(game_player_id)
                                    ,FOREIGN KEY(nominee) REFERENCES game_player(game_player_id)
                                )''')

            db.commit()
        except Exception as e:
            db.rollback()
            raise e


def insert_into_table(table:str, data):
    columns = ''
    values  = []
    num_values = 0

    with sqlite3.connect(globals.DB_FILE_LOCATION) as db:
        if type(data) == pd.DataFrame:
            data.to_sql(table, db, if_exists='append', index=False)
            return None
        elif type(data) == dict:
            for key, value in data.items():
                if value is None:
                    continue
                columns += f'{key}, '
                values.append(str(value)) # todo sort out how this works with boolean values
            values = tuple(values)
            num_values = len(values)

        try:
            cursor = db.cursor()
            qmarks = '?,' * num_values
            query = f"INSERT INTO {table} ({columns[:-2]}) VALUES ({qmarks[:-1]});"

            cursor.execute(query, values)
        except Exception as e:
            db.rollback()
            raise e


def game_insert(discord_category_id, game_name, start_date=None, end_date=None, number_of_players=None, status=None, game_length=None):
    insert_into_table('game', locals())


def get_table(table:str, indicators:dict=None, joins:dict=None):
    query = f'SELECT * from {table}'
    if joins is not None:
        for key, value in joins.items():
            query += f'\nLEFT OUTER JOIN {key} USING ({value})'
    if indicators is not None:
        query += "\nWHERE "
        cnt = 0
        for key, value in indicators.items():
            if cnt > 0:
                query += '\nAND '
            query += f"cast({key} as text)='{value}'"
            cnt += 1
    query += ';'
    with sqlite3.connect(globals.DB_FILE_LOCATION) as db:
        return pd.read_sql_query(query, db)


def get_table_schema(table: str):
    with sqlite3.connect(globals.DB_FILE_LOCATION) as db:
        return pd.read_sql_query(f"pragma table_info('{table}')", db)


def delete_from_table(table: str, indicators=None):
    query = f"DELETE FROM {table} "
    if indicators is not None:
        query += "WHERE "
        cnt = 0
        for key, value in indicators.items():
            if cnt > 0:
                query += ' AND '
            query += f"{key}='{value}'"
            cnt += 1
    query += ';'

    with sqlite3.connect(globals.DB_FILE_LOCATION) as db:
        try:
            cursor = db.cursor()

            cursor.execute(query)
        except Exception as e:
            db.rollback()
            raise e

def update_table(table: str, data_to_update: dict, update_conditions: dict):
    values = []
    num = 0
    with sqlite3.connect(globals.DB_FILE_LOCATION) as db:

        try:
            cursor = db.cursor()

            data_to_update['modified_datetime'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            query = f"UPDATE {table}"
            for key, value in data_to_update.items():
                query += ", " if num else '\nSET '
                query += f"{key} = ?"
                values.append(str(value))
                num += 1
            num = 0
            for key, value in update_conditions.items():
                query += " AND " if num else '\nWHERE '
                query += f"{key} = ?"
                values.append(str(value))
                num += 1

            query += f";"
            values = tuple(values)

            cursor.execute(query, values)
        except Exception as e:
            db.rollback()
            raise e



def insert_default_data():
    sheets = Sheets.from_files(globals.BASE_DIR / 'credentials.json', globals.BASE_DIR / 'storage.json')
    workbook = sheets[os.getenv('GOOGLE_SHEET_DEFAULT_DATA_FILE_ID')]
    tables = ['character', 'event', 'channel', 'character_permission', 'role_permission', 'role']
    for table in tables:
        insert_into_table(table, workbook.find(table).to_frame())


if __name__ == '__main__':
    globals.setup_logging(globals.BASE_DIR / 'logging_config.yaml', logging.DEBUG)
    load_dotenv()
    try:
        os.remove(globals.DB_FILE_LOCATION)
    except FileNotFoundError:
        pass
    create_database_tables()

    insert_default_data()


