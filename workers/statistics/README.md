# Statistics worker

The worker is an execution adapter, not the owner of scientific rules. In restored
main it claims legacy `run_analysis` and `reproduce_finding` jobs, while the API queues
`run_analysis_from_artifacts`; therefore durable analyses do not execute. CJ-R00 must
connect the artifact-backed job and quarantine inline molecular payloads. CJ-R05 then
generalizes the manifest/engine registry contract. Workers may publish only while
holding the current fenced attempt.
