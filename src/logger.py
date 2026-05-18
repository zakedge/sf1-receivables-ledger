import logging


def setup_logger():
    """
    Set up application logger.

    Logs will be written to:
    logs/app.log
    """

    logging.basicConfig(
        filename="logs/app.log",
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    return logging.getLogger(__name__)