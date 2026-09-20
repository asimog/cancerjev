from packages.gdc.filters import open_project_files


def test_open_file_filter_cannot_omit_access_boundary() -> None:
    filter_ = open_project_files("TCGA-LUAD")

    assert filter_ == {
        "op": "and",
        "content": [
            {
                "op": "=",
                "content": {"field": "cases.project.project_id", "value": "TCGA-LUAD"},
            },
            {"op": "=", "content": {"field": "files.access", "value": "open"}},
        ],
    }
