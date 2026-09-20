"""Scientific source bindings and versioned canonical materialization lineage."""

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
CREATE TABLE materialization_sources (
  source_id varchar(71) PRIMARY KEY,
  snapshot_id varchar(100) NOT NULL REFERENCES dataset_snapshots(snapshot_id),
  sha256 varchar(71) NOT NULL REFERENCES dataset_objects(sha256),
  source_file_id varchar(100),
  source_metadata jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE materializations (
  materialization_id varchar(71) PRIMARY KEY,
  snapshot_id varchar(100) NOT NULL REFERENCES dataset_snapshots(snapshot_id),
  source_id varchar(71) NOT NULL REFERENCES materialization_sources(source_id),
  output_sha256 varchar(71) NOT NULL REFERENCES dataset_objects(sha256),
  diagnostics_sha256 varchar(71) NOT NULL REFERENCES dataset_objects(sha256),
  modality varchar(40) NOT NULL,
  measurement_type varchar(50) NOT NULL,
  parser_name varchar(100) NOT NULL,
  parser_version varchar(40) NOT NULL,
  schema_version varchar(40) NOT NULL,
  normalization_version varchar(100) NOT NULL,
  selection_version varchar(100) NOT NULL,
  logical_sha256 varchar(71) NOT NULL,
  row_count bigint NOT NULL CONSTRAINT ck_materialization_rows CHECK (row_count >= 0),
  diagnostics_summary jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_materializations_lookup ON materializations(snapshot_id, modality, measurement_type);
CREATE TRIGGER trg_materialization_sources_immutable BEFORE UPDATE OR DELETE ON materialization_sources
FOR EACH ROW EXECUTE FUNCTION cancerjev_reject_immutable_mutation();
CREATE TRIGGER trg_materializations_immutable BEFORE UPDATE OR DELETE ON materializations
FOR EACH ROW EXECUTE FUNCTION cancerjev_reject_immutable_mutation();
""")


def downgrade() -> None:
    op.execute("DROP TABLE materializations; DROP TABLE materialization_sources;")
