import os
import time
from boxwatchr.database import initialize
from boxwatchr.rules import load_rules, watch_rules
from boxwatchr.logger import get_logger
from boxwatchr import config

logger = get_logger("boxwatchr.main")


def main():
    logger.info("Boxwatchr starting up")
    logger.info("Testing mode: %s", config.TESTING)

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