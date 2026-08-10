"""RabbitMQ publisher for meeting processing jobs."""

from __future__ import annotations

import json
import logging

import aio_pika
from aio_pika import DeliveryMode, Message
from aio_pika.abc import AbstractChannel, AbstractRobustConnection

from app.auth.config import get_settings

logger = logging.getLogger(__name__)

_connection: AbstractRobustConnection | None = None
_channel: AbstractChannel | None = None


async def connect_rabbitmq() -> None:
    """Open a shared robust connection (called on app startup)."""
    global _connection, _channel
    settings = get_settings()
    if _connection and not _connection.is_closed:
        return
    _connection = await aio_pika.connect_robust(settings.rabbitmq_url)
    _channel = await _connection.channel()
    await _channel.declare_queue(settings.rabbitmq_meeting_queue, durable=True)
    logger.info("RabbitMQ connected; queue=%s", settings.rabbitmq_meeting_queue)


async def close_rabbitmq() -> None:
    global _connection, _channel
    if _channel and not _channel.is_closed:
        await _channel.close()
    if _connection and not _connection.is_closed:
        await _connection.close()
    _channel = None
    _connection = None


async def _ensure_channel() -> AbstractChannel:
    global _connection, _channel
    if _channel is None or _channel.is_closed:
        await connect_rabbitmq()
    assert _channel is not None
    return _channel


async def publish_meeting_id(meeting_id: str) -> None:
    """
    Publish the meeting id for further processing.

    Message body (JSON): {"id": "<meeting_id>"}
    Queue name from RABBITMQ_MEETING_QUEUE (default: meetinsights.meetings).
    """
    settings = get_settings()
    channel = await _ensure_channel()
    await channel.declare_queue(settings.rabbitmq_meeting_queue, durable=True)
    body = json.dumps({"id": str(meeting_id)}).encode("utf-8")
    message = Message(
        body=body,
        content_type="application/json",
        delivery_mode=DeliveryMode.PERSISTENT,
    )
    await channel.default_exchange.publish(
        message,
        routing_key=settings.rabbitmq_meeting_queue,
    )
    logger.info("Published meeting id=%s to queue=%s", meeting_id, settings.rabbitmq_meeting_queue)
