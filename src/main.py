import logging
import os

from dotenv import load_dotenv
import pandas as pd

import globals
from bot import bot

if __name__ == '__main__':
    globals.setup_logging(globals.BASE_DIR / 'logging_config.yaml', logging.DEBUG)

    pd.set_option('display.max_rows', 500)
    pd.set_option('display.max_columns', 500)
    pd.set_option('display.width', 1000)

    load_dotenv()
    TOKEN = os.getenv('DISCORD_TOKEN')

    bot.run(TOKEN)
