import sys

from loguru import logger


def setup_logging(log_level: str = "INFO") -> None:
    logger.remove()

    # Human-readable stderr for development
    logger.add(
        sys.stderr,
        level=log_level,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{line}</cyan> — "
            "<level>{message}</level>"
        ),
    )

    # JSON file sink for production
    logger.add(
        "logs/app.log",
        level="DEBUG",
        serialize=True,
        rotation="10 MB",
        retention="30 days",
        compression="gz",
        enqueue=True,
        backtrace=True,
        diagnose=False,
    )
