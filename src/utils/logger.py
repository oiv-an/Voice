from __future__ import annotations

from pathlib import Path

from loguru import logger  # type: ignore[import]

from config.settings import LoggingConfig


def setup_logging(config: LoggingConfig) -> None:
    """
    Configure loguru according to LoggingConfig.

    - writes to file with rotation by size
    - logs to stderr
    """
    logger.remove()

    # Console
    logger.add(
        sink=lambda msg: print(msg, end=""),
        level=config.level.upper(),
        colorize=True,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>",
    )

    # File
    log_path = Path(config.file)
    logger.add(
        log_path,
        rotation=config.max_file_size,
        retention=config.backup_count,
        level=config.level.upper(),
        encoding="utf-8",
        enqueue=True,
        backtrace=True,
        diagnose=True,
    )