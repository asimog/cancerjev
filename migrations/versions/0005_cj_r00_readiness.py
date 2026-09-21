"""CJ-R00 readiness: attempt fencing, terminal reaping, and immutability.

Revision ID: 0005
Revises: 0004

Additive columns only for the rolling window: old application code ignores
attempt tokens, failure reasons, and snapshot identity versions. Cohorts and
Findings gain the same reject-mutation triggers as other published scientific
resources, and Finding publication gains a per-analysis uniqueness constraint
so concurrent attempts converge instead of duplicating authoritative rows.
"""

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    ALTER TABLE jobs ADD COLUMN attempt_token varchar(64);
    ALTER TABLE jobs ADD COLUMN failure_reason varchar(50);
    ALTER TABLE job_attempts ADD COLUMN attempt_token varchar(64);
    ALTER TABLE dataset_snapshots ADD COLUMN identity_version integer NOT NULL DEFAULT 1;

    CREATE TRIGGER trg_cohorts_immutable BEFORE UPDATE OR DELETE ON cohorts
    FOR EACH ROW EXECUTE FUNCTION cancerjev_reject_immutable_mutation();
    CREATE TRIGGER trg_findings_immutable BEFORE UPDATE OR DELETE ON findings
    FOR EACH ROW EXECUTE FUNCTION cancerjev_reject_immutable_mutation();

    -- Fails loudly if legacy duplicate authoritative publications exist; data is
    -- never silently discarded to satisfy the constraint.
    CREATE UNIQUE INDEX uq_findings_analysis_result
    ON findings(analysis_id, result_hash) WHERE result_hash IS NOT NULL;
    """)


def downgrade() -> None:
    # Guarded downgrade: never leave rows that violate the restored legacy shape.
    op.execute("""
    DROP INDEX uq_findings_analysis_result;
    DROP TRIGGER trg_findings_immutable ON findings;
    DROP TRIGGER trg_cohorts_immutable ON cohorts;
    ALTER TABLE dataset_snapshots DROP COLUMN identity_version;
    ALTER TABLE job_attempts DROP COLUMN attempt_token;
    ALTER TABLE jobs DROP COLUMN failure_reason;
    ALTER TABLE jobs DROP COLUMN attempt_token;
    """)
