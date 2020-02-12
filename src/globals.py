
import logging.config
from pathlib import Path

import yaml



BASE_DIR = Path(__file__).resolve().parent.parent


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
