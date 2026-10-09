import logging
import logging.handlers
import os

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"

# Given: index into this with the -v count (clamped). 0 = WARNING, 2+ = DEBUG.
LEVELS = (logging.WARNING, logging.INFO, logging.DEBUG)


def configure_logging(
    log_file,
    log_dir="./log",
    when="midnight",
    interval=1,
    backup_count=7,
    log_level=logging.INFO,
) -> None:
    """Set up logging with TimedRotatingFile handler. Call once, from the entry point.

    `verbosity` is the number of -v flags: 0 = WARNING, 1 = INFO, 2+ = DEBUG.
    `log_file` addes a TimedRotatingFileHandler alongside the console handler.
    """
    logging.basicConfig(format=LOG_FORMAT, level=log_level, force=True)

    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, log_file)

    file_handler = logging.handlers.TimedRotatingFileHandler(
        str(log_path), when=when, interval=interval, backupCount=backup_count, utc=True
    )
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT))

    logging.getLogger().addHandler(file_handler)
