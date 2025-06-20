import logging
import os
import traceback
from logging.handlers import RotatingFileHandler

import pendulum


class MoscowFormatter(logging.Formatter):
    """Кастомный форматтер логов с поддержкой временной зоны Europe/Moscow."""

    grey = "\x1b[38;21m"
    green = "\x1b[32;1m"
    yellow = "\x1b[33;1m"
    red = "\x1b[31;1m"
    bold_red = "\x1b[41m"
    reset = "\x1b[0m"
    format_str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    FORMATS = {
        logging.DEBUG: grey + format_str + reset,
        logging.INFO: green + format_str + reset,
        logging.WARNING: yellow + format_str + reset,
        logging.ERROR: red + format_str + reset,
        logging.CRITICAL: bold_red + format_str + reset,
    }

    def converter(self, timestamp):
        """Конвертация времени из timestamp в pendulum с нужной зоной."""
        return pendulum.from_timestamp(timestamp, tz="Europe/Moscow").timetuple()

    def format(self, record):
        record.asctime = self.formatTime(record, self.datefmt)
        if record.exc_info:
            stack = traceback.extract_tb(record.exc_info[2])
            if stack:
                filename = stack[-1].filename
                lineno = stack[-1].lineno
                code_line = stack[-1].line.strip() if stack[-1].line else "???"
                record.msg = (
                    f"{record.msg}\n"
                    f"File: {filename}, Line: {lineno}\n"
                    f"Code: {code_line}\n"
                    f"Traceback:\n{''.join(traceback.format_tb(record.exc_info[2]))}"
                )

        log_fmt = self.FORMATS.get(record.levelno, self.format_str)
        formatter = logging.Formatter(log_fmt, datefmt="%Y-%m-%d %H:%M:%S %Z")
        formatter.converter = self.converter  # 👈 подмена времени
        record.levelname = record.levelname.ljust(8)
        return formatter.format(record)


def setup_logger(
    name: str,
    log_file: str = os.getenv("LOG_FILE", "bot.log"),
    log_dir: str = "logs",
) -> logging.Logger:
    logger = logging.getLogger(name)

    if logger.handlers:  # avoid re-adding handlers
        return logger

    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    logger.setLevel(getattr(logging, log_level, logging.INFO))

    os.makedirs(log_dir, exist_ok=True)

    file_handler = RotatingFileHandler(
        os.path.join(log_dir, log_file),
        maxBytes=500_000,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.ERROR)
    file_handler.setFormatter(MoscowFormatter())
    logger.addHandler(file_handler)

    if os.getenv("CONSOLE_LOGGING", "true").lower() == "true":
        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(getattr(logging, log_level, logging.INFO))
        stream_handler.setFormatter(MoscowFormatter())
        logger.addHandler(stream_handler)

    logger.propagate = False
    return logger
