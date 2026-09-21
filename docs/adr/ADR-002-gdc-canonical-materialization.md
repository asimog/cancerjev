# ADR-002 — Versioned GDC canonical materialization

**Status:** accepted; current.

## Context

GDC public processed formats vary by modality and workflow. Analyses require stable,
biologically aligned, checksummed application-owned schemas rather than direct reads
of mutable upstream responses or filename-derived identities.

## Decision

`packages/gdc` owns provider mapping and versioned parsers for public mutation MAF,
STAR RNA, gene/segment CNV, and clinical JSON. A materialization starts from a frozen
explicitly open source, verifies UUID/size/MD5/SHA-256, copies bytes to private staging,
resolves case/sample/aliquot through the frozen identity graph, writes canonical
Parquet incrementally, and records diagnostics plus physical/logical hashes.

Resource services own source/output registration and transactions; workers provide
compact orchestration. Parsers do not access the database, object-store SDK, Jev, or
live GDC. New parser/schema behavior creates a versioned materialization.

## Consequences

Strict rejection may make malformed public inputs unavailable rather than guessed.
Scientific engines consume canonical artifacts through `AnalysisInputManifest` after
CJ-R05. R04 adds minimal acquisition and slice receipts without changing parser
ownership.
