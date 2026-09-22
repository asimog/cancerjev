"""Findings filter by the authoritative ``gene_id`` column.

Revision ID: 0007
Revises: 0006

Server-owned publication writes ``gene_id`` and leaves ``gene_symbol`` NULL
because deterministic engines identify genes by stable identifier. The public
``gene`` filter therefore resolves against ``gene_id``; the now-unused
``gene_symbol`` index is replaced so the filter is indexed.
"""

from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    DROP INDEX ix_findings_gene;
    CREATE INDEX ix_findings_gene_id ON findings(gene_id);
    """)


def downgrade() -> None:
    op.execute("""
    DROP INDEX ix_findings_gene_id;
    CREATE INDEX ix_findings_gene ON findings(gene_symbol);
    """)