"""Artifact reference owns role and storage locator; objects are content only.

Revision ID: 0006
Revises: 0005

`dataset_objects` is content-addressed by `sha256`, so identical bytes collapse
to one row. Logical role and storage location are contextual to the reference
that selects those bytes: the same content may be a `cases` artifact in one
snapshot and reused elsewhere, and legacy snapshot-relative paths differ per
snapshot. Storing them on the shared object silently discarded every
registration after the first. This moves `logical_role`, `storage_backend`, and
`storage_key` onto `snapshot_artifacts`, where the existing composite primary
key `(snapshot_id, logical_role)` already makes each reference explicit.

The downgrade can only reconstruct an object locator from a
`snapshot_artifacts` reference. Objects without one (materialization sources and
diagnostics) would otherwise receive a fabricated, unresolvable locator, so the
downgrade fails closed before changing anything and asks for a forward fix.
"""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    DROP TRIGGER trg_snapshot_artifacts_immutable ON snapshot_artifacts;

    ALTER TABLE snapshot_artifacts ADD COLUMN storage_backend varchar(30);
    ALTER TABLE snapshot_artifacts ADD COLUMN storage_key varchar(1000);

    UPDATE snapshot_artifacts sa
    SET storage_backend = obj.storage_backend,
        storage_key = obj.storage_key
    FROM dataset_objects obj
    WHERE obj.sha256 = sa.sha256;

    ALTER TABLE snapshot_artifacts ALTER COLUMN storage_backend SET NOT NULL;
    ALTER TABLE snapshot_artifacts ALTER COLUMN storage_key SET NOT NULL;

    CREATE TRIGGER trg_snapshot_artifacts_immutable BEFORE UPDATE OR DELETE ON snapshot_artifacts
    FOR EACH ROW EXECUTE FUNCTION cancerjev_reject_immutable_mutation();

    ALTER TABLE dataset_objects DROP CONSTRAINT uq_dataset_objects_storage_key;
    ALTER TABLE dataset_objects
      DROP COLUMN storage_key, DROP COLUMN storage_backend, DROP COLUMN logical_role;
    """)


def downgrade() -> None:
    unreferenced = op.get_bind().scalar(
        sa.text(
            "SELECT count(*) FROM dataset_objects obj WHERE NOT EXISTS ("
            "SELECT 1 FROM snapshot_artifacts sa WHERE sa.sha256 = obj.sha256)"
        )
    )
    if unreferenced:
        raise RuntimeError(
            f"refusing destructive downgrade: {unreferenced} dataset_objects have no "
            "snapshot_artifacts reference, so their storage locator cannot be restored; "
            "forward-fix, or register a reference for every object before downgrading"
        )
    op.execute("""
    DROP TRIGGER trg_snapshot_artifacts_immutable ON snapshot_artifacts;
    DROP TRIGGER trg_dataset_objects_immutable ON dataset_objects;

    ALTER TABLE dataset_objects ADD COLUMN logical_role varchar(100) NOT NULL DEFAULT 'legacy';
    ALTER TABLE dataset_objects ADD COLUMN storage_backend varchar(30) NOT NULL DEFAULT 'unknown';
    ALTER TABLE dataset_objects ADD COLUMN storage_key varchar(1000);

    -- Deterministic per-object restoration: one reference per digest, ordered by role.
    UPDATE dataset_objects obj
    SET logical_role = src.logical_role,
        storage_backend = src.storage_backend,
        storage_key = src.storage_key
    FROM (
      SELECT DISTINCT ON (sha256) sha256, logical_role, storage_backend, storage_key
      FROM snapshot_artifacts ORDER BY sha256, logical_role
    ) src
    WHERE obj.sha256 = src.sha256;

    UPDATE dataset_objects
    SET storage_key = 'legacy/' || replace(sha256, ':', '/')
    WHERE storage_key IS NULL;

    ALTER TABLE dataset_objects ALTER COLUMN storage_key SET NOT NULL;
    ALTER TABLE dataset_objects
      ADD CONSTRAINT uq_dataset_objects_storage_key UNIQUE(storage_key);

    CREATE TRIGGER trg_dataset_objects_immutable BEFORE UPDATE OR DELETE ON dataset_objects
    FOR EACH ROW EXECUTE FUNCTION cancerjev_reject_immutable_mutation();

    ALTER TABLE snapshot_artifacts DROP COLUMN storage_key, DROP COLUMN storage_backend;

    CREATE TRIGGER trg_snapshot_artifacts_immutable BEFORE UPDATE OR DELETE ON snapshot_artifacts
    FOR EACH ROW EXECUTE FUNCTION cancerjev_reject_immutable_mutation();
    """)
