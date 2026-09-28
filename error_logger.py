"""
error_logger.py
=================
A single log file that only ever receives ERROR-level (and above)
entries -- crashes, failed file loads, failed sends -- so you have one
place to check "what went wrong" without wading through normal
activity noise.
"""
import logging
import os
from logging.handlers import RotatingFileHandler

_LOGGER_NAME = "phone_sender_pro"


def setup_error_logger(script_dir):
    log_dir = os.path.join(script_dir, "Logs")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "errors.log")

    logger = logging.getLogger(_LOGGER_NAME)
    logger.setLevel(logging.ERROR)
    logger.propagate = False
    if not logger.handlers:
        handler = RotatingFileHandler(
            log_path, maxBytes=2 * 1024 * 1024, backupCount=3, encoding="utf-8"
        )
        handler.setLevel(logging.ERROR)
        handler.setFormatter(
            logging.Formatter("%(asctime)s | %(levelname)s | %(message)s", "%Y-%m-%d %H:%M:%S")
        )
        logger.addHandler(handler)
    return logger, log_path


def get_error_logger():
    return logging.getLogger(_LOGGER_NAME)
