
from enum import Enum
import logging.config
from pathlib import Path

import yaml



BASE_DIR = Path(__file__).resolve().parent.parent
DB_FILE_LOCATION = BASE_DIR / 'data' / 'uw.db'

GAME_REACTION_EMOJI  = '🐺'

moderator_channel_name = 'moderator'

class GameStatus(Enum):
    CREATING = 'creating'
    RECRUITING = 'recruiting'
    INITIALIZING = 'initializing'
    ACTIVE = 'active'
    COMPLETED = 'completed'
    REMOVED = 'removed'



def setup_logging(default_path, default_level=logging.WARNING):
    """Setup logging configuration

    """
    path = default_path
    if path.exists():
        with open(path, 'rt') as f:
            config = yaml.safe_load(f.read())
        logging.config.dictConfig(config)
    else:
        logging.basicConfig(level=default_level)
        logging.warning('logging.yaml not imported')
