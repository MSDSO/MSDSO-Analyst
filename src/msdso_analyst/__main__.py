import logging
import os
import sys

from dotenv import load_dotenv

from msdso_analyst.bot import MSDSOAnalyst
from msdso_analyst.config import DEFAULT_CONFIG_PATH, ConfigError, load_server_config, load_token


def main():
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    try:
        token = load_token()
        config = load_server_config(os.environ.get("MSDSO_CONFIG", DEFAULT_CONFIG_PATH))
    except ConfigError as e:
        sys.exit(f"error: {e}")
    MSDSOAnalyst(config).run(token)


if __name__ == "__main__":
    main()
