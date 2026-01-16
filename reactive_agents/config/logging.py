from enum import Enum
import logging
import traceback
import sys
from colorlog import StreamHandler, ColoredFormatter


class LogLevel(str, Enum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class LoggerAdapter(logging.LoggerAdapter):
    def __init__(self, logger, extra):
        super().__init__(logger, extra)
        self.logger = logger
        self.extra = extra

    def log(self, level, msg, *args, **kwargs):
        if kwargs.get("exc_info"):
            # Format exception with full traceback
            exc_info = kwargs["exc_info"]
            if exc_info is True:
                exc_info = sys.exc_info()
            if isinstance(exc_info, BaseException):
                exc_info = (type(exc_info), exc_info, exc_info.__traceback__)
            if exc_info and isinstance(exc_info, tuple) and len(exc_info) == 3:
                msg += "\n" + "".join(
                    traceback.format_exception(exc_info[0], exc_info[1], exc_info[2])
                )

        if kwargs.get("extra", {}).get("formatter"):
            self.logger.handlers[0].setFormatter(kwargs["extra"]["formatter"])

        self.logger.log(level, msg, *args, **kwargs)


class_color_map = {
    "agent": {
        "INFO": "light_blue",
        "DEBUG": "cyan",
        "ERROR": "red",
        "WARNING": "yellow",
        "CRITICAL": "red,bg_white",
    },
    "tool": {
        "INFO": "yellow",
        "DEBUG": "cyan",
        "ERROR": "red",
        "WARNING": "yellow",
        "CRITICAL": "red,bg_white",
    },
    "agent_response": {
        "INFO": "green",
        "DEBUG": "cyan",
        "ERROR": "red",
        "WARNING": "yellow",
        "CRITICAL": "red,bg_white",
    },
}

# Configure root logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)  # Default to INFO for production use

# Create console handler with detailed formatting
handler = StreamHandler()
handler.setLevel(logging.INFO)

# Create a formatter that includes timestamp and stack info for errors
formatter = ColoredFormatter(
    "%(asctime)s %(log_color)s%(class_name)s:%(levelname)s%(reset)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    reset=True,
    log_colors={
        "DEBUG": "cyan",
        "INFO": "light_blue",
        "WARNING": "yellow",
        "ERROR": "red",
        "CRITICAL": "red,bg_white",
    },
)

handler.setFormatter(formatter)
logger.addHandler(handler)

# Prevent logs from propagating to the root logger
logger.propagate = False


def configure_logging(level: LogLevel = LogLevel.INFO, quiet: bool = False):
    """
    Configure logging level for the framework.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        quiet: If True, suppress all output except CRITICAL
    """
    if quiet:
        level = LogLevel.CRITICAL

    log_level = getattr(logging, level.value.upper())
    logger.setLevel(log_level)

    for handler in logger.handlers:
        handler.setLevel(log_level)


def get_logger(name: str, class_name: str = "agent") -> logging.LoggerAdapter:
    """
    Get a logger adapter with class name context.

    Args:
        name: Logger name
        class_name: Class name for colored output (agent, tool, agent_response)

    Returns:
        LoggerAdapter configured for the component
    """
    base_logger = logging.getLogger(name)
    return LoggerAdapter(base_logger, {"class_name": class_name})
