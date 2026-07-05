"""
Structured logging via loguru.

Usage:
    from utils.logging import setup_logging, get_logger

    setup_logging(level="INFO")
    logger = get_logger(__name__)
    logger.info("message")
"""
import sys
from pathlib import Path

from loguru import logger


def setup_logging(
    log_dir: str = "logs",
    level: str = "INFO",
    console: bool = True,
    file: bool = True,
    json_file: bool = False,
) -> None:
    """
    Configure loguru globally.

    Args:
        log_dir: directory for log files
        level: minimum log level (DEBUG/INFO/WARNING/ERROR)
        console: enable colorized console output
        file: enable daily-rotating text log
        json_file: enable JSONL log for machine processing
    """
    logger.remove()

    if console:
        logger.add(
            sys.stderr,
            format=(
                "<green>{time:HH:mm:ss}</green> | "
                "<level>{level: <8}</level> | "
                "<cyan>{extra[name]}</cyan> | "
                "<level>{message}</level>"
            ),
            level=level,
            colorize=True,
        )

    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    if file:
        logger.add(
            log_path / "quant_{time:YYYYMMDD}.log",
            format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {extra[name]} | {message}",
            level="DEBUG",
            rotation="00:00",
            retention="30 days",
            encoding="utf-8",
        )

    if json_file:
        logger.add(
            log_path / "quant_{time:YYYYMMDD}.jsonl",
            level="DEBUG",
            rotation="00:00",
            retention="7 days",
            serialize=True,
        )


def get_logger(name: str = None):
    """
    Get a logger instance bound with a module name.

    Args:
        name: typically __name__ of the calling module

    Returns:
        loguru logger with 'name' extra field bound
    """
    if name is None:
        return logger
    return logger.bind(name=name)
