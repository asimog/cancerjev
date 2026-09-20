from workers.runtime import run_worker


def analyze(payload: dict) -> dict:
    from workers.statistics.dispatcher import run_analysis_from_artifacts
    return run_analysis_from_artifacts(payload)


if __name__ == "__main__":
    run_worker(
        ("run_analysis_from_artifacts",),
        {"run_analysis_from_artifacts": analyze},
    )
