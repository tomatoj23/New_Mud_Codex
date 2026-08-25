import json
from types import SimpleNamespace

import psycopg
import pytest
from channels.db import database_sync_to_async
from channels.testing import HttpCommunicator, WebsocketCommunicator
from django.db import connections
from django.test import override_settings
from django.urls import reverse

from new_mud.apps.content.models import BlueprintHead
from new_mud.apps.content.runtime import ContentRuntime
from new_mud.asgi import application, create_application
from new_mud.process_guard import (
    release_single_process_leases,
    single_process_lease_key,
)


@pytest.fixture(autouse=True)
def release_process_leases_after_test():
    yield
    release_single_process_leases()


def test_liveness(client):
    response = client.get(reverse("health-live"))

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "new-mud", "version": "1"}


@pytest.mark.django_db(transaction=True)
@override_settings(CONTENT_INSTANCE_ID="http-readiness-instance")
def test_http_readiness_returns_verified_content_identity(client) -> None:
    startup = ContentRuntime(instance_id="http-readiness-instance").start()
    assert startup.identity is not None

    response = client.get(reverse("health-ready"))

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "database": "ready",
        "content": {
            "status": "ready",
            "startup_status": "verified",
            "mudlib_key": "jinyong.core",
            "seed_bundle_id": "jinyong.seed.v1",
            "target_content_release": "jinyong.release",
            "artifact_hash": ("073ac8cce19d4375a230de0b471e1ee2e58664645b34416de695f0b9ecdf8a24"),
            "release_head_id": str(startup.identity.release_head_id),
            "batch_id": str(startup.identity.batch_id),
            "release_version": 1,
            "release_hash": startup.identity.release_hash,
            "blueprint_count": 1,
        },
    }


@pytest.mark.django_db(transaction=True)
@override_settings(CONTENT_INSTANCE_ID="http-not-ready-instance")
def test_http_readiness_reports_content_failure_without_hiding_database_health(client) -> None:
    response = client.get(reverse("health-ready"))

    assert response.status_code == 503
    payload = response.json()
    assert payload["status"] == "not_ready"
    assert payload["database"] == "ready"
    assert payload["content"]["status"] == "not_ready"
    assert payload["content"]["error"] == {
        "code": "CONTENT_RELEASE_VALIDATION_FAILED",
        "message": "content release is not initialized",
    }


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@override_settings(CONTENT_INSTANCE_ID="websocket-readiness-instance")
async def test_websocket_health_returns_verified_content_identity() -> None:
    startup = await database_sync_to_async(
        ContentRuntime(instance_id="websocket-readiness-instance").start
    )()
    assert startup.identity is not None
    communicator = WebsocketCommunicator(application, "/ws/v1/health/")

    connected, _ = await communicator.connect()
    assert connected
    assert await communicator.receive_json_from() == {
        "type": "health.ready",
        "status": "ok",
        "version": "1",
        "database": "ready",
        "content": {
            "status": "ready",
            "startup_status": "verified",
            "mudlib_key": "jinyong.core",
            "seed_bundle_id": "jinyong.seed.v1",
            "target_content_release": "jinyong.release",
            "artifact_hash": ("073ac8cce19d4375a230de0b471e1ee2e58664645b34416de695f0b9ecdf8a24"),
            "release_head_id": str(startup.identity.release_head_id),
            "batch_id": str(startup.identity.batch_id),
            "release_version": 1,
            "release_hash": startup.identity.release_hash,
            "blueprint_count": 1,
        },
    }
    await communicator.wait()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@override_settings(
    CONTENT_INSTANCE_ID="asgi-startup-instance",
    CONTENT_STARTUP_ENABLED=True,
)
async def test_asgi_process_startup_bootstraps_content_before_readiness() -> None:
    started_application = await database_sync_to_async(create_application)()
    communicator = HttpCommunicator(
        started_application,
        "GET",
        "/api/v1/health/ready",
        headers=[(b"host", b"localhost")],
    )

    response = await communicator.get_response()
    payload = json.loads(response["body"])
    await communicator.wait()

    assert response["status"] == 200
    assert payload["status"] == "ok"
    assert payload["content"]["status"] == "ready"
    assert payload["content"]["startup_status"] == "verified"
    assert payload["content"]["release_version"] == 1
    assert payload["content"]["blueprint_count"] == 1


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@override_settings(
    CONTENT_INSTANCE_ID="asgi-failed-startup-instance",
    CONTENT_STARTUP_ENABLED=True,
)
async def test_asgi_failed_content_startup_remains_diagnosable() -> None:
    await database_sync_to_async(BlueprintHead.objects.create)(
        instance_id="asgi-failed-startup-instance",
        mudlib_key="jinyong.core",
        blueprint_key="room.partial.start",
    )
    started_application = await database_sync_to_async(create_application)()
    communicator = HttpCommunicator(
        started_application,
        "GET",
        "/api/v1/health/ready",
        headers=[(b"host", b"localhost")],
    )

    response = await communicator.get_response()
    payload = json.loads(response["body"])
    await communicator.wait()

    assert response["status"] == 503
    assert payload["status"] == "not_ready"
    assert payload["database"] == "ready"
    assert payload["content"]["error"] == {
        "code": "CONTENT_RELEASE_SCOPE_MISMATCH",
        "message": "content namespace is partially initialized",
    }


@pytest.mark.django_db(transaction=True)
@override_settings(
    CONTENT_INSTANCE_ID="leased-asgi-instance",
    CONTENT_STARTUP_ENABLED=True,
)
def test_asgi_startup_holds_a_database_lease_against_other_processes() -> None:
    create_application()
    database = connections["default"]
    database.ensure_connection()
    assert database.connection is not None

    with (
        psycopg.connect(
            database.connection.info.dsn,
            password=database.settings_dict["PASSWORD"],
            autocommit=True,
        ) as contender,
        contender.cursor() as cursor,
    ):
        cursor.execute(
            "SELECT pg_try_advisory_lock(%s, %s)",
            single_process_lease_key(),
        )
        acquired = cursor.fetchone()

    assert acquired == (False,)


@pytest.mark.django_db(transaction=True)
@override_settings(
    CONTENT_INSTANCE_ID="lost-lease-instance",
    CONTENT_STARTUP_ENABLED=True,
)
def test_readiness_fails_when_another_process_takes_a_lost_lease(client) -> None:
    create_application()
    release_single_process_leases()
    database = connections["default"]
    database.ensure_connection()
    assert database.connection is not None

    with (
        psycopg.connect(
            database.connection.info.dsn,
            password=database.settings_dict["PASSWORD"],
            autocommit=True,
        ) as contender,
        contender.cursor() as cursor,
    ):
        cursor.execute(
            "SELECT pg_try_advisory_lock(%s, %s)",
            single_process_lease_key(),
        )
        assert cursor.fetchone() == (True,)

        response = client.get(reverse("health-ready"))

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "database": "ready",
        "process": "lease_unavailable",
        "error": {
            "code": "CONTENT_RELEASE_CONFLICT",
            "message": "another ASGI process already owns the deployment lease",
        },
    }


@pytest.mark.django_db(transaction=True)
def test_readiness_fails_closed_when_process_lease_query_loses_database(
    client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class BrokenLease:
        def __init__(self) -> None:
            self.closed = False

        def cursor(self) -> None:
            raise psycopg.OperationalError("lease connection dropped")

        def close(self) -> None:
            self.closed = True

    broken_lease = BrokenLease()

    def connect_with_broken_lease(*args: object, **kwargs: object) -> BrokenLease:
        del args, kwargs
        return broken_lease

    monkeypatch.setattr(
        "new_mud.process_guard.psycopg",
        SimpleNamespace(Error=psycopg.Error, connect=connect_with_broken_lease),
    )

    response = client.get(reverse("health-ready"))

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "database": "ready",
        "process": "lease_unavailable",
        "error": {
            "code": "CONTENT_RELEASE_CONFLICT",
            "message": "PostgreSQL process lease is unavailable",
        },
    }
    assert broken_lease.closed is True
