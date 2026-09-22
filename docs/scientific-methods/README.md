# Scientific methods

The V1 discovery families and their minimum scientific contracts are defined once in
the [V1 discovery catalogue](../scientific/discovery-catalogue-v1.md): R08 owns D01–D04
(mutation recurrence, mutation relationships, copy number, RNA description), R09 owns
D05–D08 (defined-group expression comparison, CNV/RNA association, mutation/RNA
association, cohort/subtype comparison), and R10 owns D09 (molecular feature →
survival). Registered methods execute through the R05 Engine Registry; no separate
discovery-method registry exists.

Current deterministic primitives include Benjamini–Hochberg correction, frequencies,
expression outliers/variance, CNV-expression and mutation-expression associations, plus
basic survival helpers. They are not a complete registered production engine suite; the
durable artifact worker currently executes only the narrow registered `cnv_rna`
contract. Scientific methods must declare population, eligibility, tested universe,
estimand, effect, uncertainty, multiplicity, missingness, QC, coverage, method version,
and failure behavior. Duplicate biological keys fail; unexamined or unavailable data
is never encoded as negative. R08–R12 deliver the versioned deterministic engine and
search program, including method-specific deterministic candidate gates.

Pathway enrichment, methylation integration, unsupervised molecular-subgroup discovery,
single-cell RNA, fusion/splice analysis, structural-variant discovery, ATAC/chromatin,
spatial genomics, cfDNA, and long-read analyses are explicitly deferred V1.