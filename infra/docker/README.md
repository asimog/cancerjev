# Docker infrastructure

The root `compose.yaml` is the development entry point. Add service-specific images here as workers are implemented. Bulk transfer images must use the official NCI-GDC `gdc-client`, not a locally reimplemented downloader.
