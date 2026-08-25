import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


class ImmutableModel(models.Model):
    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError(f"{type(self).__name__} rows are immutable")
        return super().save(*args, **kwargs)


class BlueprintHead(models.Model):
    head_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    instance_id = models.CharField(max_length=128)
    mudlib_key = models.CharField(max_length=128)
    blueprint_key = models.CharField(max_length=128)
    draft_revision = models.ForeignKey(
        "BlueprintRevision",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="draft_for_heads",
    )
    published_revision = models.ForeignKey(
        "BlueprintRevision",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="published_for_heads",
    )
    edit_version = models.PositiveBigIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("instance_id", "mudlib_key", "blueprint_key"),
                name="content_head_namespace_key_uniq",
            ),
            models.UniqueConstraint(
                fields=("head_id", "blueprint_key"),
                name="content_head_id_key_uniq",
            ),
            models.CheckConstraint(
                condition=Q(edit_version__gte=1),
                name="content_head_edit_gte_1",
            ),
        ]


class BlueprintRevision(ImmutableModel):
    class RevisionKind(models.TextChoices):
        DRAFT = "draft"
        PUBLISHED = "published"

    class PublicationReason(models.TextChoices):
        SEED_BOOTSTRAP = "seed_bootstrap"
        CONTENT_PUBLISH = "content_publish"
        DEPENDENCY_RECOMPILE = "dependency_recompile"
        ROLLBACK_RECOMPILE = "rollback_recompile"

    revision_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    head = models.ForeignKey(BlueprintHead, on_delete=models.PROTECT, related_name="revisions")
    blueprint_key = models.CharField(max_length=128)
    revision_kind = models.CharField(max_length=16, choices=RevisionKind.choices)
    source_revision = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="derived_revisions"
    )
    source_seed_bundle_id = models.CharField(max_length=128, null=True, blank=True)
    raw_payload = models.JSONField()
    compiled_payload = models.JSONField(null=True, blank=True)
    content_hash = models.CharField(max_length=64)
    compiled_hash = models.CharField(max_length=64, null=True, blank=True)
    resolved_dependency_hash = models.CharField(max_length=64, null=True, blank=True)
    compiler_contract_version = models.CharField(max_length=64, null=True, blank=True)
    publication_reason = models.CharField(
        max_length=32, choices=PublicationReason.choices, null=True, blank=True
    )
    created_in_batch = models.ForeignKey(
        "ContentReleaseBatch",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="created_revisions",
    )
    created_by = models.CharField(max_length=128)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("revision_id", "head"), name="content_revision_id_head_uniq"
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        revision_kind="draft",
                        compiled_payload__isnull=True,
                        compiled_hash__isnull=True,
                        resolved_dependency_hash__isnull=True,
                        compiler_contract_version__isnull=True,
                        publication_reason__isnull=True,
                        created_in_batch__isnull=True,
                    )
                    | Q(
                        revision_kind="published",
                        compiled_payload__isnull=False,
                        compiled_hash__isnull=False,
                        resolved_dependency_hash__isnull=False,
                        compiler_contract_version__isnull=False,
                        publication_reason__isnull=False,
                        created_in_batch__isnull=False,
                    )
                ),
                name="content_revision_kind_fields_valid",
            ),
        ]


class ResolvedBlueprintDependency(ImmutableModel):
    class DependencyKind(models.TextChoices):
        PARENT = "parent"
        BLUEPRINT_REF = "blueprint_ref"

    id = models.BigAutoField(primary_key=True)
    source_revision = models.ForeignKey(
        BlueprintRevision, on_delete=models.PROTECT, related_name="blueprint_dependencies"
    )
    dependency_path = models.CharField(max_length=512)
    dependency_kind = models.CharField(max_length=32, choices=DependencyKind.choices)
    ordinal = models.PositiveIntegerField()
    target_head = models.ForeignKey(
        BlueprintHead, on_delete=models.PROTECT, related_name="incoming_blueprint_dependencies"
    )
    target_revision = models.ForeignKey(
        BlueprintRevision, on_delete=models.PROTECT, related_name="incoming_revision_dependencies"
    )
    target_blueprint_key = models.CharField(max_length=128)
    expected_kind = models.CharField(max_length=64)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("source_revision", "dependency_kind", "dependency_path", "ordinal"),
                name="content_blueprint_dependency_uniq",
            )
        ]


class ResolvedRegistryDependency(ImmutableModel):
    id = models.BigAutoField(primary_key=True)
    source_revision = models.ForeignKey(
        BlueprintRevision, on_delete=models.PROTECT, related_name="registry_dependencies"
    )
    dependency_path = models.CharField(max_length=512)
    ordinal = models.PositiveIntegerField()
    registry_kind = models.CharField(max_length=64)
    registry_key = models.CharField(max_length=128)
    registry_version = models.CharField(max_length=32)
    definition_hash = models.CharField(max_length=64)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("source_revision", "dependency_path", "ordinal"),
                name="content_registry_dependency_uniq",
            )
        ]


class ContentReleaseHead(models.Model):
    release_head_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    instance_id = models.CharField(max_length=128)
    mudlib_key = models.CharField(max_length=128)
    target_content_release = models.CharField(max_length=128)
    active_batch = models.ForeignKey(
        "ContentReleaseBatch",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="active_for_release_heads",
    )
    release_version = models.PositiveBigIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("instance_id", "mudlib_key", "target_content_release"),
                name="content_release_head_namespace_uniq",
            ),
            models.CheckConstraint(
                condition=(
                    Q(release_version=0, active_batch__isnull=True)
                    | Q(release_version__gte=1, active_batch__isnull=False)
                ),
                name="content_release_head_state_valid",
            ),
        ]


class ContentReleaseBatch(ImmutableModel):
    batch_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    release_head = models.ForeignKey(
        ContentReleaseHead, on_delete=models.PROTECT, related_name="batches"
    )
    release_version = models.PositiveBigIntegerField()
    parent_batch = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="child_batches"
    )
    manifest_version = models.CharField(max_length=32)
    source_seed_bundle_id = models.CharField(max_length=128, null=True, blank=True)
    release_hash = models.CharField(max_length=64)
    created_by = models.CharField(max_length=128)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("batch_id", "release_head"), name="content_batch_id_head_uniq"
            ),
            models.UniqueConstraint(
                fields=("release_head", "release_version"),
                name="content_batch_head_version_uniq",
            ),
            models.CheckConstraint(
                condition=Q(release_version__gte=1), name="content_batch_version_gte_1"
            ),
        ]


class ContentReleaseItem(ImmutableModel):
    release_item_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    batch = models.ForeignKey(ContentReleaseBatch, on_delete=models.PROTECT, related_name="items")
    release_head = models.ForeignKey(
        ContentReleaseHead, on_delete=models.PROTECT, related_name="release_items"
    )
    blueprint_head = models.ForeignKey(
        BlueprintHead, on_delete=models.PROTECT, related_name="release_items"
    )
    blueprint_key = models.CharField(max_length=128)
    published_revision = models.ForeignKey(
        BlueprintRevision, on_delete=models.PROTECT, related_name="release_items"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("batch", "blueprint_head"), name="content_item_batch_head_uniq"
            ),
            models.UniqueConstraint(
                fields=("batch", "blueprint_key"), name="content_item_batch_key_uniq"
            ),
        ]


class ContentStartupFailure(ImmutableModel):
    failure_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    instance_id = models.CharField(max_length=128)
    mudlib_key = models.CharField(max_length=128)
    target_content_release = models.CharField(max_length=128)
    seed_bundle_id = models.CharField(max_length=128)
    artifact_hash = models.CharField(max_length=64, null=True, blank=True)
    error_code = models.CharField(max_length=128)
    error_message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(
                fields=("instance_id", "mudlib_key", "target_content_release", "created_at"),
                name="content_startup_failure_ns_idx",
            )
        ]
