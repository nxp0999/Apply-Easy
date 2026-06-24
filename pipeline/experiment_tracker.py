"""
pipeline/experiment_tracker.py

MLflow experiment tracking for --discover runs.

Each run logs:
  params  — scoring thresholds and weights in effect
  metrics — funnel stats (scraped, filtered, scored, avg score, tier counts)
  tags    — platform breakdown, filter reason breakdown

View results:
  mlflow ui   →   http://localhost:5000
"""

import os
import logging
from datetime import datetime

EXPERIMENT_NAME = "apply-easy-discover"


def _get_client():
    import mlflow
    # MLflow 2.x requires a database backend; fall back to local SQLite
    tracking_uri = os.environ.get(
        "MLFLOW_TRACKING_URI",
        "sqlite:///mlruns/mlflow.db",
    )
    os.makedirs("mlruns", exist_ok=True)
    mlflow.set_tracking_uri(tracking_uri)
    return mlflow


def start_run(params: dict) -> object | None:
    """
    Start an MLflow run. Returns the active run context or None if MLflow
    is unavailable (so the pipeline never fails because of tracking).
    """
    try:
        mlflow = _get_client()
        mlflow.set_experiment(EXPERIMENT_NAME)
        run = mlflow.start_run(run_name=datetime.utcnow().strftime("%Y-%m-%d %H:%M"))
        mlflow.log_params(params)
        return run
    except Exception as exc:
        logging.warning(f"MLflow start_run failed (non-fatal): {exc}")
        return None


def log_metrics(metrics: dict) -> None:
    """Log a flat dict of numeric metrics to the active run."""
    try:
        import mlflow
        mlflow.log_metrics(metrics)
    except Exception as exc:
        logging.warning(f"MLflow log_metrics failed (non-fatal): {exc}")


def log_filter_breakdown(drops: dict) -> None:
    """
    Log per-reason filter counts as both metrics and a text artifact.
    drops: {"blacklist": 3, "title": 5, "ghost": 1, ...}
    """
    try:
        import mlflow
        mlflow.log_metrics({f"filtered_{k}": v for k, v in drops.items()})
        lines = "\n".join(f"{k}: {v}" for k, v in sorted(drops.items(), key=lambda x: -x[1]))
        mlflow.log_text(lines, "filter_breakdown.txt")
    except Exception as exc:
        logging.warning(f"MLflow log_filter_breakdown failed (non-fatal): {exc}")


def log_top_jobs(jobs: list) -> None:
    """
    Log a summary of the top-scoring jobs as a text artifact.
    jobs: list of dicts with title, company, fit_score
    """
    try:
        import mlflow
        lines = []
        for j in sorted(jobs, key=lambda x: x.get("fit_score") or 0, reverse=True)[:15]:
            score = j.get("fit_score", "?")
            title = j.get("title", "")[:40]
            co    = j.get("company", "")[:25]
            lines.append(f"[{score:>3}]  {title} @ {co}")
        mlflow.log_text("\n".join(lines), "top_jobs.txt")
    except Exception as exc:
        logging.warning(f"MLflow log_top_jobs failed (non-fatal): {exc}")


def end_run() -> None:
    try:
        import mlflow
        mlflow.end_run()
    except Exception:
        pass


def build_params(config_module) -> dict:
    """Extract loggable params from the config module."""
    return {
        "keyword_prescore_min": getattr(config_module, "KEYWORD_PRESCORE_MIN", "?"),
        "fit_score_threshold":  getattr(config_module, "FIT_SCORE_THRESHOLD", "?"),
        "resume_mode":          getattr(config_module, "RESUME_MODE", "?"),
        "platforms":            str(getattr(config_module, "PLATFORMS", [])),
    }
