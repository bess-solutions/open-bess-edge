"""
src/interfaces/pubsub_publisher.py
===================================
Async Google Cloud Pub/Sub publisher for BESSAI telemetry.

Wraps ``gcloud-aio-pubsub`` to provide:
* JSON serialisation of telemetry payloads.
* Attributes envelope (site_id, schema_version, timestamp) for
  downstream routing and schema evolution.
* Structured logging and OpenTelemetry span injection.
* Graceful connection management with context-manager support.

Usage
-----
::

    async with PubSubPublisher(project_id, topic) as pub:
        await pub.publish({"soc": 85.2, "active_power": 120.5})
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import structlog
from gcloud.aio.pubsub import PublisherClient, PubsubMessage

from src.core.config import get_settings

log: structlog.BoundLogger = structlog.get_logger(__name__)

# Bump this when the telemetry payload schema changes.
_SCHEMA_VERSION = "1.0"

Telemetry = dict[str, Any]


class PublisherError(RuntimeError):
    """Raised when a Pub/Sub publish operation fails unrecoverably."""


class PubSubPublisher:
    """
    Async Pub/Sub publisher scoped to a single topic.

    Parameters
    ----------
    project_id:
        Google Cloud project ID.
    topic_name:
        Pub/Sub topic name (not the full resource path).
    site_id:
        Site identifier injected as a message attribute for routing.
    """

    def __init__(
        self,
        project_id: str,
        topic_name: str,
        site_id: str | None = None,
    ) -> None:
        self._project_id = project_id
        self._topic_name = topic_name
        self._topic_path = f"projects/{project_id}/topics/{topic_name}"
        self._site_id = site_id or get_settings().SITE_ID
        self._client: PublisherClient | None = None
        self._session: Any = None  # aiohttp.ClientSession managed internally

    # ------------------------------------------------------------------
    # Context-manager support
    # ------------------------------------------------------------------

    async def __aenter__(self) -> PubSubPublisher:
        await self._open()
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self._close()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def _open(self) -> None:
        """Initialise the gcloud-aio publisher client."""
        import aiohttp  # optional import — only needed at runtime

        self._session = aiohttp.ClientSession()
        self._client = PublisherClient(session=self._session)
        log.info(
            "pubsub.publisher.opened",
            project=self._project_id,
            topic=self._topic_name,
        )

    async def _close(self) -> None:
        """Close the underlying HTTP session."""
        if self._session is not None:
            await self._session.close()
            self._session = None
        log.info("pubsub.publisher.closed", topic=self._topic_name)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def publish(self, telemetry: Telemetry) -> str:
        """
        Serialise *telemetry* and publish it to the configured topic.

        Parameters
        ----------
        telemetry:
            Dictionary of engineering-unit measurements plus any
            metadata fields (e.g. ``{"soc": 85.2, "active_power": 120.5}``).
            An ``"observed_at"`` ISO-8601 timestamp is injected
            automatically if not present.

        Returns
        -------
        str
            The Pub/Sub message ID returned by the server.

        Raises
        ------
        PublisherError
            If the publish call fails.
        RuntimeError
            If ``publish`` is called before the client is initialised
            (i.e. outside of the async context manager).
        """
        if self._client is None:
            raise RuntimeError(
                "PubSubPublisher must be used as an async context manager."
            )

        # Inject envelope fields
        payload: Telemetry = {
            "site_id": self._site_id,
            "schema_version": _SCHEMA_VERSION,
            "observed_at": telemetry.get(
                "observed_at",
                datetime.now(tz=timezone.utc).isoformat(),
            ),
            **telemetry,
        }

        data: bytes = json.dumps(payload, default=str).encode("utf-8")
        attributes: dict[str, str] = {
            "site_id": self._site_id,
            "schema_version": _SCHEMA_VERSION,
            "content_type": "application/json",
        }

        message = PubsubMessage(data=data, attributes=attributes)

        log.debug(
            "pubsub.publish.start",
            topic=self._topic_name,
            payload_bytes=len(data),
        )

        try:
            response = await self._client.publish(
                self._topic_path, messages=[message]
            )
            # gcloud-aio returns a PublishResponse; message IDs are in .messageIds
            msg_id: str = response.get("messageIds", ["?"])[0]
            log.info(
                "pubsub.publish.success",
                topic=self._topic_name,
                message_id=msg_id,
            )
            return msg_id
        except Exception as exc:
            log.error(
                "pubsub.publish.failed",
                topic=self._topic_name,
                error=str(exc),
            )
            raise PublisherError(
                f"Failed to publish to {self._topic_path}: {exc}"
            ) from exc


# ---------------------------------------------------------------------------
# Module-level convenience factory  (optional singleton pattern)
# ---------------------------------------------------------------------------

_publisher_instance: PubSubPublisher | None = None


def get_publisher() -> PubSubPublisher:
    """
    Return the module-level publisher singleton.

    Initialise once from ``settings``; subsequent calls return the same
    instance.  The caller is responsible for lifecycle (open/close).
    """
    global _publisher_instance
    if _publisher_instance is None:
        cfg = get_settings()
        _publisher_instance = PubSubPublisher(
            project_id=cfg.GCP_PROJECT_ID or "",
            topic_name=cfg.GCP_PUBSUB_TOPIC or "",
        )
    return _publisher_instance
