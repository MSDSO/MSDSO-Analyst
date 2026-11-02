import logging
import os
import sys

from dotenv import load_dotenv

from msdso_analyst.bot import MSDSOAnalyst
from msdso_analyst.config import DEFAULT_CONFIG_PATH, DEFAULT_DB_PATH, ConfigError, load_server_config, load_token
from msdso_analyst.storage import Storage

log = logging.getLogger("msdso_analyst")


def main():
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    try:
        token = load_token()
        config = load_server_config(os.environ.get("MSDSO_CONFIG", DEFAULT_CONFIG_PATH))
    except ConfigError as e:
        sys.exit(f"error: {e}")

    storage = Storage(os.environ.get("MSDSO_DB", DEFAULT_DB_PATH))
    if storage.seed_role_groups(config.role_group_seeds):
        log.info("Seeded %d role groups from the server config", len(config.role_group_seeds))
    try:
        MSDSOAnalyst(config, storage).run(token)
    finally:
        storage.close()


if __name__ == "__main__":
    main()
