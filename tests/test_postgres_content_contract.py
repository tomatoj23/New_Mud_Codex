from __future__ import annotations

import os

import pytest
from django.db import DatabaseError, IntegrityError, connection, transaction

from new_mud.apps.content.models import BlueprintHead, BlueprintRevision

pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.skipif(
        os.getenv("RUN_POSTGRES_TESTS") != "1",
        reason="requires the PostgreSQL contract-test service",
    ),
]


def create_draft(head: BlueprintHead, *, created_by: str = "contract-test") -> BlueprintRevision:
    return BlueprintRevision.objects.create(
        head=head,
        blueprint_key=head.blueprint_key,
        revision_kind=BlueprintRevision.RevisionKind.DRAFT,
        raw_payload={"kind": "room"},
        content_hash="0" * 64,
        created_by=created_by,
    )


def force_deferred_constraints() -> None:
    with connection.cursor() as cursor:
        cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")


def test_head_pointer_cannot_cross_blueprint_heads() -> None:
    first_head = BlueprintHead.objects.create(
        instance_id="instance", mudlib_key="mudlib", blueprint_key="room.first"
    )
    second_head = BlueprintHead.objects.create(
        instance_id="instance", mudlib_key="mudlib", blueprint_key="room.second"
    )
    second_draft = create_draft(second_head)

    with pytest.raises(IntegrityError), transaction.atomic():
        BlueprintHead.objects.filter(pk=first_head.pk).update(draft_revision=second_draft)
        force_deferred_constraints()


def test_published_pointer_rejects_draft_revision() -> None:
    head = BlueprintHead.objects.create(
        instance_id="instance", mudlib_key="mudlib", blueprint_key="room.only"
    )
    draft = create_draft(head)

    with pytest.raises(IntegrityError), transaction.atomic():
        BlueprintHead.objects.filter(pk=head.pk).update(published_revision=draft)
        force_deferred_constraints()


def test_revision_update_is_rejected_by_database() -> None:
    head = BlueprintHead.objects.create(
        instance_id="instance", mudlib_key="mudlib", blueprint_key="room.immutable"
    )
    draft = create_draft(head)

    with pytest.raises(DatabaseError):
        BlueprintRevision.objects.filter(pk=draft.pk).update(created_by="changed")
