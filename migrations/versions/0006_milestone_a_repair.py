"""Milestone A repair: partition sets, analysis execution manifest, input materializations FK cleanup."""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "partition_sets",
        sa.Column("partition_set_id", sa.String(100), primary_key=True),
        sa.Column(
            "snapshot_id",
            sa.String(100),
            sa.ForeignKey("dataset_snapshots.snapshot_id"),
        ),
        sa.Column("seed", sa.String(100)),
        sa.Column("split_fraction", sa.Float),
        sa.Column("assignment_hash", sa.String(71)),
        sa.Column("discovery_case_ids", sa.JSON),
        sa.Column("validation_case_ids", sa.JSON),
        sa.Column("discovery_sample_ids", sa.JSON),
        sa.Column("validation_sample_ids", sa.JSON),
        sa.Column("discovery_aliquot_ids", sa.JSON),
        sa.Column("validation_aliquot_ids", sa.JSON),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_partition_snapshot", "partition_sets", ["snapshot_id"]
    )
    op.create_checkConstraint(
        "ck_partition_case_disjoint",
        "NOT (discovery_case_ids && validation_case_ids)",
        table_name="partition_sets",
    )

    op.add_column(
        "analyses",
        sa.Column(
            "input_materializations",
            sa.JSON,
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column(
        "analyses",
        sa.Column(
            "execution_manifest_hash", sa.String(71), nullable=True
        ),
    )
    op.add_column(
        "analyses",
        sa.Column("partition_set_id", sa.String(100), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("analyses", "partition_set_id")
    op.drop_column("analyses", "execution_manifest_hash")
    op.drop_column("analyses", "input_materializations")
    op.drop_table("partition_sets")