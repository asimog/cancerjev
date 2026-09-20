import hashlib
import json
from pathlib import Path

import pytest

from packages.gdc.identity import FrozenIdentityResolver
from packages.gdc.mappings.identity import map_file_hit
from packages.schemas.identity import CaseRecord
from packages.schemas.snapshot import SnapshotObject

FIXTURES = Path(__file__).parent / "fixtures" / "gdc"


@pytest.fixture
def gdc_fixture():
    def load(name):
        path = FIXTURES / name
        if name == "clinical.json":
            cases = tuple(
                CaseRecord(case_id=c["case_id"], project_id="TCGA-LUAD")
                for c in json.loads(path.read_text())["data"]["hits"]
            )
            return path, None, FrozenIdentityResolver(cases, (), (), ())
        metadata = json.loads((FIXTURES / (name + ".metadata.json")).read_text())
        file, cases, samples, aliquots, links = map_file_hit(metadata["source"])
        # Excerpts are separate test objects; these checksum overrides are not upstream claims.
        source = SnapshotObject(**file.model_dump()).model_copy(
            update={
                "file_name": name,
                "file_size": path.stat().st_size,
                "md5sum": hashlib.md5(path.read_bytes()).hexdigest(),
            }
        )
        return (
            path,
            source,
            FrozenIdentityResolver(tuple(cases), tuple(samples), tuple(aliquots), tuple(links)),
        )

    return load
