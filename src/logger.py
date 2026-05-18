import logging


def setup_logger(log_file):
    """
    Set up application logger.

    Logs will be written to the configured log file.
    """

    logging.basicConfig(
        filename=log_file,
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    return logging.getLogger(__name__)