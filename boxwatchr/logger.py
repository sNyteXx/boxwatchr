import logging
from datetime import datetime, timezone
from boxwatchr import config

class DatabaseHandler(logging.Handler):
    def emit(self, record):
        try:
            from boxwatchr.database import enqueue_log
        except Exception:
            return

        logged_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        email_id = getattr(record, "email_id", None)
        enqueue_log(record.levelname, record.name, record.getMessage(), logged_at, email_id)

def get_logger(name):
    logger = logging.getLogger(name)
    logger.setLevel(config.LOG_LEVEL)

    if not logger.handlers:
        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(config.LOG_LEVEL)

        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )

        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)

        db_handler = DatabaseHandler()
        db_handler.setLevel(logging.DEBUG)
        db_handler.setFormatter(formatter)
        logger.addHandler(db_handler)

    return logger
