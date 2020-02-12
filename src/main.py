import logging
import os

from dotenv import load_dotenv

import globals
from bot import bot

if __name__ == '__main__':
    globals.setup_logging(globals.BASE_DIR / 'logging_config.yaml', logging.DEBUG)

    load_dotenv()
    TOKEN = os.getenv('DISCORD_TOKEN')

    bot.run(TOKEN)
