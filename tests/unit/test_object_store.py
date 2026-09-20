from unittest.mock import Mock

import pytest
from botocore.exceptions import ClientError, EndpointConnectionError

from packages.storage.objects import (
    ObjectStorePermissionError,
    ObjectStoreServiceError,
    S3ObjectStore,
)


def store_with_client(client: Mock) -> S3ObjectStore:
    store = object.__new__(S3ObjectStore)
    store.bucket = "test"
    store.client = client
    return store


def client_error(code: str, status: int) -> ClientError:
    return ClientError(
        {"Error": {"Code": code}, "ResponseMetadata": {"HTTPStatusCode": status}},
        "HeadObject",
    )


def test_s3_not_found_is_false() -> None:
    client = Mock()
    client.head_object.side_effect = client_error("NoSuchKey", 404)
    assert not store_with_client(client).exists("a" * 64)


def test_s3_permission_failure_is_not_missing() -> None:
    client = Mock()
    client.head_object.side_effect = client_error("AccessDenied", 403)
    with pytest.raises(ObjectStorePermissionError):
        store_with_client(client).exists("a" * 64)


def test_s3_service_failure_is_not_missing() -> None:
    client = Mock()
    client.head_object.side_effect = EndpointConnectionError(endpoint_url="http://minio")
    with pytest.raises(ObjectStoreServiceError):
        store_with_client(client).exists("a" * 64)
