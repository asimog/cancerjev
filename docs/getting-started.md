# Getting started

Set `CANCERJEV_DATABASE_URL` for local commands. Compose supplies the same value to the API, workers,
and migration service. Run `docker compose up --build`, then open `http://localhost:3000` (web),
`http://localhost:8000/docs` (API), or `http://localhost:9001` (MinIO). The Projects page queries the
live open GDC API. Creating a logical snapshot may take time because pagination intentionally exhausts
the project's open file metadata. Bulk payload transfer requires the official `gdc-client`; it is
intentionally not bundled in the current API image and live payload acquisition remains deferred to PR 9.
