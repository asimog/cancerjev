"""Freeze explicit materialization input contracts on analysis requests."""

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Historical SHA-only analyses remain readable; never infer scientific lineage.
    op.execute("""
ALTER TABLE analyses ADD COLUMN input_materializations jsonb NOT NULL DEFAULT '[]'::jsonb;
CREATE TRIGGER trg_snapshot_artifacts_immutable BEFORE UPDATE OR DELETE ON snapshot_artifacts
FOR EACH ROW EXECUTE FUNCTION cancerjev_reject_immutable_mutation();
CREATE FUNCTION cancerjev_freeze_analysis_inputs() RETURNS trigger AS $$
BEGIN
  IF NEW.snapshot_id IS DISTINCT FROM OLD.snapshot_id
     OR NEW.cohort_id IS DISTINCT FROM OLD.cohort_id
     OR NEW.engine IS DISTINCT FROM OLD.engine
     OR NEW.engine_version IS DISTINCT FROM OLD.engine_version
     OR NEW.parameters IS DISTINCT FROM OLD.parameters
     OR NEW.expected_input_artifacts IS DISTINCT FROM OLD.expected_input_artifacts
     OR NEW.input_materializations IS DISTINCT FROM OLD.input_materializations THEN
    RAISE EXCEPTION 'analysis scientific inputs are immutable';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER trg_analysis_inputs_immutable BEFORE UPDATE ON analyses
FOR EACH ROW EXECUTE FUNCTION cancerjev_freeze_analysis_inputs();
""")


def downgrade() -> None:
    op.execute("""
DROP TRIGGER trg_analysis_inputs_immutable ON analyses;
DROP FUNCTION cancerjev_freeze_analysis_inputs();
DROP TRIGGER trg_snapshot_artifacts_immutable ON snapshot_artifacts;
ALTER TABLE analyses DROP COLUMN input_materializations;
""")
