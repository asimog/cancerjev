"""Durable resource metadata and artifact registry.

Revision ID: 0002
Revises: 0001
"""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
ALTER TABLE projects ADD COLUMN primary_site jsonb NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE projects ADD COLUMN created_at timestamptz NOT NULL DEFAULT now();
ALTER TABLE projects ADD COLUMN updated_at timestamptz NOT NULL DEFAULT now();

ALTER TABLE dataset_objects ADD COLUMN logical_role varchar(100) NOT NULL DEFAULT 'legacy';
ALTER TABLE dataset_objects ADD COLUMN storage_backend varchar(30) NOT NULL DEFAULT 'unknown';
ALTER TABLE dataset_objects ADD COLUMN storage_key varchar(1000);
UPDATE dataset_objects SET storage_key = 'legacy/' || replace(sha256, ':', '/') WHERE storage_key IS NULL;
ALTER TABLE dataset_objects ALTER COLUMN storage_key SET NOT NULL;
ALTER TABLE dataset_objects ADD CONSTRAINT uq_dataset_objects_storage_key UNIQUE(storage_key);
ALTER TABLE dataset_objects ADD COLUMN source_gdc_uuid varchar(100);
ALTER TABLE dataset_objects ADD COLUMN source_md5 varchar(32);
ALTER TABLE dataset_objects ADD COLUMN parser_schema_version varchar(100);
ALTER TABLE dataset_objects ADD COLUMN row_count bigint;
ALTER TABLE dataset_objects ADD COLUMN created_at timestamptz NOT NULL DEFAULT now();

ALTER TABLE dataset_snapshots ADD COLUMN status varchar(30) NOT NULL DEFAULT 'published';
ALTER TABLE dataset_snapshots ADD CONSTRAINT ck_snapshots_status CHECK (status IN ('staging','published','failed'));
ALTER TABLE dataset_snapshots ADD COLUMN source_api varchar(500) NOT NULL DEFAULT 'unknown';
ALTER TABLE dataset_snapshots ADD COLUMN gdc_release varchar(100) NOT NULL DEFAULT 'unknown/not-reported';
ALTER TABLE dataset_snapshots ADD COLUMN schema_versions jsonb NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE dataset_snapshots ADD COLUMN policy_versions jsonb NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE dataset_snapshots ADD COLUMN manifest_sha256 varchar(71) REFERENCES dataset_objects(sha256);
ALTER TABLE dataset_snapshots ADD COLUMN coverage_sha256 varchar(71) REFERENCES dataset_objects(sha256);
ALTER TABLE dataset_snapshots ADD COLUMN identity_sha256 varchar(71) REFERENCES dataset_objects(sha256);
ALTER TABLE dataset_snapshots ADD COLUMN provenance_sha256 varchar(71) REFERENCES dataset_objects(sha256);
ALTER TABLE dataset_snapshots ADD COLUMN published_at timestamptz;
UPDATE dataset_snapshots SET published_at = created_at WHERE status = 'published';
CREATE INDEX ix_snapshots_project_created ON dataset_snapshots(project_id, created_at);
CREATE TABLE snapshot_artifacts (
  snapshot_id varchar(100) NOT NULL REFERENCES dataset_snapshots(snapshot_id),
  logical_role varchar(100) NOT NULL,
  sha256 varchar(71) NOT NULL REFERENCES dataset_objects(sha256),
  PRIMARY KEY(snapshot_id, logical_role)
);
CREATE INDEX ix_snapshot_artifacts_sha256 ON snapshot_artifacts(sha256);

ALTER TABLE cohorts ADD COLUMN definition_version varchar(100) NOT NULL DEFAULT '1';
ALTER TABLE cohorts ADD COLUMN exclusion_reasons jsonb NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE cohorts ADD COLUMN selection_policy_version varchar(100) NOT NULL DEFAULT '1';

ALTER TABLE analyses ADD COLUMN cohort_id varchar(100) REFERENCES cohorts(cohort_id);
ALTER TABLE analyses ADD COLUMN engine varchar(100) NOT NULL DEFAULT 'legacy';
ALTER TABLE analyses ADD COLUMN engine_version varchar(100) NOT NULL DEFAULT 'legacy';
ALTER TABLE analyses ADD COLUMN expected_input_artifacts jsonb NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE analyses ADD COLUMN job_id uuid UNIQUE REFERENCES jobs(job_id);
ALTER TABLE analyses ADD COLUMN error text;
ALTER TABLE analyses ADD COLUMN created_at timestamptz NOT NULL DEFAULT now();
ALTER TABLE analyses ADD COLUMN queued_at timestamptz;
ALTER TABLE analyses ADD COLUMN started_at timestamptz;
ALTER TABLE analyses ADD COLUMN completed_at timestamptz;
UPDATE analyses SET state = 'requested' WHERE state NOT IN ('requested','queued','running','completed','failed','cancelled');
ALTER TABLE analyses ADD CONSTRAINT ck_analyses_state CHECK (state IN ('requested','queued','running','completed','failed','cancelled'));
CREATE INDEX ix_analyses_snapshot_created ON analyses(snapshot_id, created_at);
CREATE INDEX ix_analyses_cohort_created ON analyses(cohort_id, created_at);

ALTER TABLE findings ADD COLUMN snapshot_id varchar(100) REFERENCES dataset_snapshots(snapshot_id);
UPDATE findings f SET snapshot_id = a.snapshot_id FROM analyses a WHERE a.analysis_id = f.analysis_id;
ALTER TABLE findings ALTER COLUMN snapshot_id SET NOT NULL;
ALTER TABLE findings ADD COLUMN cohort_id varchar(100) REFERENCES cohorts(cohort_id);
UPDATE findings f SET cohort_id = a.cohort_id FROM analyses a WHERE a.analysis_id = f.analysis_id;
ALTER TABLE findings ADD COLUMN finding_type varchar(100) NOT NULL DEFAULT 'legacy';
ALTER TABLE findings ADD COLUMN gene_id varchar(100);
ALTER TABLE findings ADD COLUMN gene_symbol varchar(100);
ALTER TABLE findings ADD COLUMN analysis_version varchar(100) NOT NULL DEFAULT 'legacy';
ALTER TABLE findings ADD COLUMN result_hash varchar(71);
ALTER TABLE findings ADD COLUMN created_at timestamptz NOT NULL DEFAULT now();
CREATE INDEX ix_findings_snapshot ON findings(snapshot_id);
CREATE INDEX ix_findings_cohort ON findings(cohort_id);
CREATE INDEX ix_findings_analysis ON findings(analysis_id);
CREATE INDEX ix_findings_type ON findings(finding_type);
CREATE INDEX ix_findings_gene ON findings(gene_symbol);
CREATE INDEX ix_findings_result_hash ON findings(result_hash);

ALTER TABLE audit_events ADD COLUMN actor_id varchar(200) NOT NULL DEFAULT 'system';
ALTER TABLE audit_events ADD COLUMN resource_type varchar(100) NOT NULL DEFAULT 'legacy';
ALTER TABLE audit_events ADD COLUMN resource_id varchar(200) NOT NULL DEFAULT 'legacy';
ALTER TABLE audit_events ADD COLUMN context jsonb NOT NULL DEFAULT '{}'::jsonb;
CREATE INDEX ix_audit_resource ON audit_events(resource_type, resource_id, created_at);

CREATE TABLE idempotency_records (
  scope varchar(100) NOT NULL,
  idempotency_key varchar(200) NOT NULL,
  request_hash varchar(71) NOT NULL,
  resource_type varchar(100) NOT NULL,
  resource_id varchar(200) NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY(scope, idempotency_key)
);
""")


def downgrade() -> None:
    op.execute("""
DROP TABLE idempotency_records;
DROP INDEX ix_audit_resource;
ALTER TABLE audit_events DROP COLUMN context, DROP COLUMN resource_id, DROP COLUMN resource_type, DROP COLUMN actor_id;
DROP INDEX ix_findings_result_hash; DROP INDEX ix_findings_gene; DROP INDEX ix_findings_type; DROP INDEX ix_findings_analysis; DROP INDEX ix_findings_cohort; DROP INDEX ix_findings_snapshot;
ALTER TABLE findings DROP COLUMN created_at, DROP COLUMN result_hash, DROP COLUMN analysis_version, DROP COLUMN gene_symbol, DROP COLUMN gene_id, DROP COLUMN finding_type, DROP COLUMN cohort_id, DROP COLUMN snapshot_id;
DROP INDEX ix_analyses_cohort_created; DROP INDEX ix_analyses_snapshot_created;
ALTER TABLE analyses DROP CONSTRAINT ck_analyses_state;
ALTER TABLE analyses DROP COLUMN completed_at, DROP COLUMN started_at, DROP COLUMN queued_at, DROP COLUMN created_at, DROP COLUMN error, DROP COLUMN job_id, DROP COLUMN expected_input_artifacts, DROP COLUMN engine_version, DROP COLUMN engine, DROP COLUMN cohort_id;
ALTER TABLE cohorts DROP COLUMN selection_policy_version, DROP COLUMN exclusion_reasons, DROP COLUMN definition_version;
DROP TABLE snapshot_artifacts;
DROP INDEX ix_snapshots_project_created;
ALTER TABLE dataset_snapshots DROP CONSTRAINT ck_snapshots_status;
ALTER TABLE dataset_snapshots DROP COLUMN published_at, DROP COLUMN provenance_sha256, DROP COLUMN identity_sha256, DROP COLUMN coverage_sha256, DROP COLUMN manifest_sha256, DROP COLUMN policy_versions, DROP COLUMN schema_versions, DROP COLUMN gdc_release, DROP COLUMN source_api, DROP COLUMN status;
ALTER TABLE dataset_objects DROP COLUMN created_at, DROP COLUMN row_count, DROP COLUMN parser_schema_version, DROP COLUMN source_md5, DROP COLUMN source_gdc_uuid;
ALTER TABLE dataset_objects DROP CONSTRAINT uq_dataset_objects_storage_key;
ALTER TABLE dataset_objects DROP COLUMN storage_key, DROP COLUMN storage_backend, DROP COLUMN logical_role;
ALTER TABLE projects DROP COLUMN updated_at, DROP COLUMN created_at, DROP COLUMN primary_site;
""")
