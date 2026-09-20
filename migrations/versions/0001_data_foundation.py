"""Explicit deterministic data foundation schema.

Revision ID: 0001
"""

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

TABLES = (
    "job_attempts",
    "jobs",
    "audit_events",
    "findings",
    "analyses",
    "cohorts",
    "snapshot_files",
    "aliquots",
    "samples",
    "cases",
    "dataset_objects",
    "dataset_snapshots",
    "projects",
)


def upgrade() -> None:
    op.execute("""
CREATE TABLE projects (project_id varchar(64) PRIMARY KEY, name varchar);
CREATE TABLE dataset_snapshots (snapshot_id varchar(100) PRIMARY KEY, snapshot_hash varchar(71) UNIQUE NOT NULL, project_id varchar(64) NOT NULL REFERENCES projects(project_id), provenance jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE dataset_objects (sha256 varchar(71) PRIMARY KEY, size bigint NOT NULL, media_type varchar(100) NOT NULL);
CREATE TABLE cases (case_id uuid PRIMARY KEY, project_id varchar(64) NOT NULL REFERENCES projects(project_id), submitter_id varchar(100));
CREATE TABLE samples (sample_id uuid PRIMARY KEY, case_id uuid NOT NULL REFERENCES cases(case_id), sample_type varchar(100));
CREATE TABLE aliquots (aliquot_id uuid PRIMARY KEY, sample_id uuid NOT NULL REFERENCES samples(sample_id));
CREATE TABLE snapshot_files (snapshot_id varchar(100) REFERENCES dataset_snapshots(snapshot_id), file_id uuid, md5sum varchar(32) NOT NULL, sha256 varchar(71), PRIMARY KEY(snapshot_id,file_id));
CREATE TABLE cohorts (cohort_id varchar(100) PRIMARY KEY, snapshot_id varchar(100) NOT NULL REFERENCES dataset_snapshots(snapshot_id), definition jsonb NOT NULL, case_ids jsonb NOT NULL, sample_ids jsonb NOT NULL, content_hash varchar(71) UNIQUE NOT NULL, created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE analyses (analysis_id uuid PRIMARY KEY, snapshot_id varchar(100) NOT NULL REFERENCES dataset_snapshots(snapshot_id), state varchar(30) NOT NULL, parameters jsonb NOT NULL);
CREATE TABLE findings (finding_id varchar(100) PRIMARY KEY, analysis_id uuid NOT NULL REFERENCES analyses(analysis_id), payload jsonb NOT NULL);
CREATE TABLE audit_events (event_id uuid PRIMARY KEY, event_type varchar(100) NOT NULL, detail text NOT NULL, created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE jobs (job_id uuid PRIMARY KEY, job_type varchar(80) NOT NULL, state varchar(20) NOT NULL DEFAULT 'queued' CONSTRAINT ck_jobs_state CHECK (state IN ('queued','claimed','running','succeeded','failed','cancelled')), payload jsonb NOT NULL, result jsonb, lease_owner varchar(200), lease_expires_at timestamptz, attempt_count integer NOT NULL DEFAULT 0, max_attempts integer NOT NULL DEFAULT 3, error text, created_at timestamptz NOT NULL DEFAULT now(), started_at timestamptz, completed_at timestamptz);
CREATE INDEX ix_jobs_claim ON jobs(state,job_type,created_at); CREATE INDEX ix_jobs_lease ON jobs(lease_expires_at);
CREATE TABLE job_attempts (attempt_id uuid PRIMARY KEY, job_id uuid NOT NULL REFERENCES jobs(job_id), attempt_number integer NOT NULL, worker_id varchar(200) NOT NULL, started_at timestamptz NOT NULL DEFAULT now(), completed_at timestamptz, error text);
CREATE INDEX ix_job_attempts_job_id ON job_attempts(job_id);
""")


def downgrade() -> None:
    for table in TABLES:
        op.drop_table(table)
