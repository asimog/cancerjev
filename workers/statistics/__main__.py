from workers.runtime import run_worker


def analyze(payload: dict) -> dict:
    from workers.statistics.analysis import execute_analysis

    return execute_analysis(payload)


if __name__ == "__main__":
    run_worker(
        ("run_analysis", "reproduce_finding"),
        {"run_analysis": analyze, "reproduce_finding": analyze},
    )
