import os
import time
import requests
from boxwatchr import config
from boxwatchr.database import initialize
from boxwatchr.rules import load_rules, watch_rules
from boxwatchr.logger import get_logger

logger = get_logger("boxwatchr.main")


def wait_for_rspamd():
    url = f"http://{config.RSPAMD_HOST}:{config.RSPAMD_PORT}/ping"
    logger.info("Waiting for rspamd to be ready at %s", url)
    while True:
        try:
            response = requests.get(url, timeout=2)
            if response.text.strip() == "pong":
                logger.info("rspamd is ready")
                return
        except Exception:
            pass
        logger.debug("rspamd not ready yet, retrying in 2 seconds")
        time.sleep(2)


def main():
    logger.info("Boxwatchr starting up")
    logger.info("Testing mode: %s", config.TESTING)

    wait_for_rspamd()

    logger.info("Initializing database")
    initialize()

    logger.info("Loading rules from rules.yaml")
    load_rules("rules.yaml")

    logger.info("Watching rules.yaml for changes")
    observer = watch_rules("rules.yaml")

    logger.info("Boxwatchr is running. Email processing not yet implemented.")

    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        logger.info("Shutting down")
        observer.stop()
        observer.join()


if __name__ == "__main__":
    main()