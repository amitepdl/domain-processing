from __future__ import annotations

import json
import time
from collections.abc import Callable

import pika
from pika.adapters.blocking_connection import BlockingChannel, BlockingConnection

from app.config import (
    RABBITMQ_HOST,
    RABBITMQ_PASSWORD,
    RABBITMQ_PORT,
    RABBITMQ_PREFETCH,
    RABBITMQ_QUEUE,
    RABBITMQ_USER,
    RETRY_INTERVAL_SECONDS,
    RETRY_MAX_ATTEMPTS,
)


def _connection_params() -> pika.ConnectionParameters:
    return pika.ConnectionParameters(
        host=RABBITMQ_HOST,
        port=RABBITMQ_PORT,
        credentials=pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASSWORD),
        heartbeat=60,
        blocked_connection_timeout=30,
        connection_attempts=1,
    )


def wait_for_rabbitmq() -> None:
    last_error: Exception | None = None
    for _ in range(RETRY_MAX_ATTEMPTS):
        try:
            connection = pika.BlockingConnection(_connection_params())
            connection.close()
            return
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            time.sleep(RETRY_INTERVAL_SECONDS)
    raise RuntimeError(f"RabbitMQ was not ready: {last_error}") from last_error


def connect() -> BlockingConnection:
    last_error: Exception | None = None
    for _ in range(RETRY_MAX_ATTEMPTS):
        try:
            return pika.BlockingConnection(_connection_params())
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            time.sleep(RETRY_INTERVAL_SECONDS)
    raise RuntimeError(f"Could not connect to RabbitMQ: {last_error}") from last_error


def declare_queue(channel: BlockingChannel) -> None:
    channel.queue_declare(queue=RABBITMQ_QUEUE, durable=True)


def publish_domain_jobs(messages: list[dict]) -> None:
    if not messages:
        return
    connection = connect()
    try:
        channel = connection.channel()
        declare_queue(channel)
        for message in messages:
            channel.basic_publish(
                exchange="",
                routing_key=RABBITMQ_QUEUE,
                body=json.dumps(message),
                properties=pika.BasicProperties(
                    delivery_mode=2,
                    content_type="application/json",
                ),
            )
    finally:
        connection.close()


def consume(handler: Callable[[dict], None]) -> None:
    while True:
        connection = connect()
        try:
            channel = connection.channel()
            declare_queue(channel)
            channel.basic_qos(prefetch_count=RABBITMQ_PREFETCH)

            def _callback(ch: BlockingChannel, method, _properties, body: bytes) -> None:
                payload = json.loads(body.decode("utf-8"))
                handler(payload)
                ch.basic_ack(delivery_tag=method.delivery_tag)

            channel.basic_consume(queue=RABBITMQ_QUEUE, on_message_callback=_callback)
            channel.start_consuming()
        except Exception:
            time.sleep(RETRY_INTERVAL_SECONDS)
        finally:
            try:
                connection.close()
            except Exception:  # noqa: BLE001
                pass
