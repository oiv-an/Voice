from __future__ import annotations

from pathlib import Path
import os

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

    # File with reverse logging (newest at top) and size limit
    log_path = Path(config.file)
    
    def reverse_sink(message):
        """Writes log message to the beginning of the file."""
        try:
            # Ensure directory exists
            log_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Read existing content
            existing_content = ""
            if log_path.exists():
                try:
                    with log_path.open("r", encoding="utf-8") as f:
                        existing_content = f.read()
                except Exception:
                    pass
            
            # Prepend new message
            new_content = message + existing_content
            
            # Truncate if exceeds 1MB (approx 10^6 chars)
            max_size = 1024 * 1024
            if len(new_content) > max_size:
                # Find the last newline before max_size to avoid cutting lines
                cut_index = new_content.rfind('\n', 0, max_size)
                if cut_index != -1:
                    new_content = new_content[:cut_index+1]
                else:
                    new_content = new_content[:max_size]
            
            # Write back
            with log_path.open("w", encoding="utf-8") as f:
                f.write(new_content)
                
        except Exception as e:
            print(f"Failed to write to log file: {e}")

    logger.add(
        sink=reverse_sink,
        level=config.level.upper(),
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        enqueue=True, # Thread-safe
        backtrace=True,
        diagnose=True,
    )