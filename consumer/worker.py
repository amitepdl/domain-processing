import logging

from app.db import migrate, wait_for_database
from app.rabbitmq.client import consume, wait_for_rabbitmq
from app.worker import handle_message

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("consumer")


def main() -> None:
    wait_for_database()
    migrate()
    wait_for_rabbitmq()
    logger.info("Consumer started")
    consume(handle_message)


if __name__ == "__main__":
    main()
