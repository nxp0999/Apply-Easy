"""
clean_unprocessed.py
Removes all unprocessed jobs from the DB and their output folders.
Keeps all jobs that have already been scored and processed.

Usage:
    python3 clean_unprocessed.py
"""

import os
import sqlite3
import shutil
from config import DB_PATH, OUTPUT_DIR


def main():
    if not os.path.exists(DB_PATH):
        print("No database found. Nothing to clean.")
        return

    conn = sqlite3.connect(DB_PATH)

    unprocessed = conn.execute(
        "SELECT job_id FROM applications WHERE fit_score IS NULL"
    ).fetchall()

    processed = conn.execute(
        "SELECT COUNT(*) FROM applications WHERE fit_score IS NOT NULL"
    ).fetchone()[0]

    total = conn.execute(
        "SELECT COUNT(*) FROM applications"
    ).fetchone()[0]

    print(f"\nDatabase summary:")
    print(f"  Total jobs      : {total}")
    print(f"  Processed       : {processed}  ← will be KEPT")
    print(f"  Unprocessed     : {len(unprocessed)}  ← will be REMOVED")

    if not unprocessed:
        print("\nNothing to clean — all jobs are processed.")
        conn.close()
        return

    confirm = input("\nProceed? (yes/no): ").strip().lower()
    if confirm != "yes":
        print("Cancelled.")
        conn.close()
        return

    # Remove output folders
    removed_folders = 0
    for (job_id,) in unprocessed:
        job_dir = os.path.join(OUTPUT_DIR, job_id)
        if os.path.isdir(job_dir):
            shutil.rmtree(job_dir)
            removed_folders += 1

    # Remove from DB
    conn.execute("DELETE FROM applications WHERE fit_score IS NULL")
    conn.commit()
    conn.close()

    print(f"\n✓ Removed {len(unprocessed)} unprocessed jobs from DB.")
    print(f"✓ Removed {removed_folders} output folders.")
    print(f"✓ {processed} processed jobs preserved.")
    print("\nRun: python3 main.py --scrape   to pull fresh jobs.")


if __name__ == "__main__":
    main()
