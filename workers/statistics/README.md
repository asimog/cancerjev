# Statistics worker

The worker is an execution adapter, not the owner of scientific rules. CJ-R00 connects
`run_analysis_from_artifacts` to the resource-owned execution service using only a
compact Analysis reference; inline molecular payloads are not accepted. CJ-R05 later
generalizes the manifest/engine registry contract. Workers may publish only while
holding the current fenced attempt.
