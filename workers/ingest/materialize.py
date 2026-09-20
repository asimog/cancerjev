"""Compact durable materialization jobs; local payload API lives in packages.gdc."""

from packages.database.config import resolve_database_url
from packages.database.session import session_factory
from packages.resources.materialization import MaterializationService
from packages.resources.service import DurableResourceService
from packages.schemas.materialization import MaterializationRequest
from packages.storage.config import StorageSettings


def materialize_snapshot(payload: dict) -> dict:
    request = MaterializationRequest.model_validate(payload)
    settings = StorageSettings()
    factory = session_factory(resolve_database_url())
    with factory.begin() as session:
        return MaterializationService(
            DurableResourceService(session), settings.store(), settings,
        ).run(request)
