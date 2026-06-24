"""
pipeline/cluster_cache.py
Maps job titles to role clusters and caches tailored resumes per cluster.

Instead of running a full LLM tailor for every job, the pipeline:
  1. Maps the job title to a cluster (ml_ai, data_engineering, etc.)
  2. Checks if a fresh cluster resume already exists on disk
  3. If yes → copies it (zero LLM calls, near-instant)
  4. If no  → runs full tailor and saves result as the new cluster template
"""

import json
import os
import shutil
from datetime import datetime, timedelta

from config import APPROVED_RESUMES_DIR, CLUSTER_CACHE_DAYS, OUTPUT_DIR, ROLE_CLUSTERS

_CACHE_DIR = os.path.join(os.path.dirname(OUTPUT_DIR), "output", "cluster_resumes")


def _cluster_dir(cluster: str) -> str:
    path = os.path.join(_CACHE_DIR, cluster)
    os.makedirs(path, exist_ok=True)
    return path


def map_to_cluster(title: str) -> str | None:
    """Return the cluster key whose keywords best match the job title."""
    title_lower = title.lower()
    for cluster_key, info in ROLE_CLUSTERS.items():
        for kw in info["keywords"]:
            if kw in title_lower:
                return cluster_key
    return None


def get_cached_resume(cluster: str) -> str | None:
    """
    Return cached tailored resume text if the cluster template is fresh
    (within CLUSTER_CACHE_DAYS). Returns None if absent or stale.
    """
    meta_path   = os.path.join(_cluster_dir(cluster), "meta.json")
    resume_path = os.path.join(_cluster_dir(cluster), "resume_tailored.txt")

    if not os.path.exists(meta_path) or not os.path.exists(resume_path):
        return None

    with open(meta_path) as f:
        meta = json.load(f)

    generated_at = datetime.fromisoformat(meta.get("generated_at", "2000-01-01"))
    if datetime.now() - generated_at > timedelta(days=CLUSTER_CACHE_DAYS):
        return None  # stale — let the caller regenerate

    with open(resume_path) as f:
        return f.read()


def save_to_cache(cluster: str, tailored_text: str, job: dict) -> None:
    """Save a freshly tailored resume as the cluster template for future reuse."""
    d = _cluster_dir(cluster)
    with open(os.path.join(d, "resume_tailored.txt"), "w") as f:
        f.write(tailored_text)
    with open(os.path.join(d, "meta.json"), "w") as f:
        json.dump(
            {
                "generated_at":    datetime.now().isoformat(),
                "source_job_title": job.get("title", ""),
                "source_company":   job.get("company", ""),
                "cluster_label":    ROLE_CLUSTERS[cluster]["label"],
            },
            f,
            indent=2,
        )


def save_cluster_pdf(cluster: str, pdf_path: str) -> None:
    """Copy a freshly compiled PDF into the cluster cache for future reuse."""
    if os.path.exists(pdf_path):
        shutil.copy(pdf_path, os.path.join(_cluster_dir(cluster), "resume_tailored.pdf"))


def copy_cluster_pdf(cluster: str, dest_dir: str, pdf_name: str) -> bool:
    """
    Copy the cached cluster PDF into a job directory.
    Returns True on success, False if no cached PDF exists yet.
    """
    src = os.path.join(_cluster_dir(cluster), "resume_tailored.pdf")
    if not os.path.exists(src):
        return False
    shutil.copy(src, os.path.join(dest_dir, "resume_tailored.pdf"))
    shutil.copy(src, os.path.join(dest_dir, pdf_name))
    return True


def get_approved_resume(cluster: str) -> str | None:
    """
    Return the hand-approved resume text from resumes/<cluster>.txt, or None.
    These files are NEVER auto-overwritten — edit them manually to update.
    """
    path = os.path.join(APPROVED_RESUMES_DIR, f"{cluster}.txt")
    if not os.path.exists(path):
        return None
    with open(path) as f:
        text = f.read().strip()
    return text if text else None


def promote_to_approved(cluster: str, text: str | None = None) -> str:
    """
    Copy the current cluster cache resume into resumes/<cluster>.txt,
    making it the hand-approved version for this cluster.
    Pass text directly to promote an arbitrary string instead.
    Returns the path of the approved file.
    """
    os.makedirs(APPROVED_RESUMES_DIR, exist_ok=True)
    dest = os.path.join(APPROVED_RESUMES_DIR, f"{cluster}.txt")
    if text is None:
        cached = get_cached_resume(cluster)
        if not cached:
            raise FileNotFoundError(
                f"No cached resume for cluster '{cluster}' — run --process first."
            )
        text = cached
    with open(dest, "w") as f:
        f.write(text)
    # Also copy PDF if present
    pdf_src  = os.path.join(_cluster_dir(cluster), "resume_tailored.pdf")
    pdf_dest = os.path.join(APPROVED_RESUMES_DIR, f"{cluster}.pdf")
    if os.path.exists(pdf_src) and not os.path.exists(pdf_dest):
        shutil.copy(pdf_src, pdf_dest)
    return dest


def list_all_resumes() -> list[dict]:
    """
    Return the full resume status for every cluster:
      source: 'approved' | 'cached' | 'none'
      age_days: int | None
      stale: bool
    """
    result = []
    for cluster_key, info in ROLE_CLUSTERS.items():
        approved_path = os.path.join(APPROVED_RESUMES_DIR, f"{cluster_key}.txt")
        meta_path     = os.path.join(_CACHE_DIR, cluster_key, "meta.json")
        pdf_approved  = os.path.join(APPROVED_RESUMES_DIR, f"{cluster_key}.pdf")
        pdf_cached    = os.path.join(_CACHE_DIR, cluster_key, "resume_tailored.pdf")

        has_approved = os.path.exists(approved_path)
        has_cached   = os.path.exists(meta_path)

        if has_approved:
            mtime    = datetime.fromtimestamp(os.path.getmtime(approved_path))
            age_days = (datetime.now() - mtime).days
            source   = "approved"
        elif has_cached:
            with open(meta_path) as f:
                meta = json.load(f)
            mtime    = datetime.fromisoformat(meta.get("generated_at", "2000-01-01"))
            age_days = (datetime.now() - mtime).days
            source   = "cached"
        else:
            age_days = None
            source   = "none"

        result.append({
            "cluster":      cluster_key,
            "label":        info["label"],
            "source":       source,
            "age_days":     age_days,
            "stale":        source == "cached" and (age_days or 0) >= CLUSTER_CACHE_DAYS,
            "has_pdf":      os.path.exists(pdf_approved) or os.path.exists(pdf_cached),
            "approved_pdf": os.path.exists(pdf_approved),
        })
    return result


def cache_status() -> list[dict]:
    """Return a summary of all cached cluster templates (for dashboard/CLI)."""
    result = []
    for cluster_key, info in ROLE_CLUSTERS.items():
        meta_path = os.path.join(_CACHE_DIR, cluster_key, "meta.json")
        pdf_path  = os.path.join(_CACHE_DIR, cluster_key, "resume_tailored.pdf")
        if os.path.exists(meta_path):
            with open(meta_path) as f:
                meta = json.load(f)
            generated_at = datetime.fromisoformat(meta["generated_at"])
            age_days = (datetime.now() - generated_at).days
            result.append({
                "cluster":     cluster_key,
                "label":       info["label"],
                "age_days":    age_days,
                "stale":       age_days >= CLUSTER_CACHE_DAYS,
                "has_pdf":     os.path.exists(pdf_path),
                "source_job":  meta.get("source_job_title", "—"),
            })
        else:
            result.append({
                "cluster": cluster_key,
                "label":   info["label"],
                "age_days": None,
                "stale":    True,
                "has_pdf":  False,
                "source_job": "—",
            })
    return result
