import sys
from loguru import logger

logger.remove()
logger.add(
    sys.stderr,
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{line}</cyan> — <level>{message}</level>",
    level="DEBUG",
    colorize=True,
)
logger.add(
    "cad2urdf.log",
    rotation="5 MB",
    retention="7 days",
    level="DEBUG",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{line} — {message}",
)

def get_logger(name: str):
    return logger.bind(name=name)
