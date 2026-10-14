"""
Generate the GitHub contributions report: `python generate_report.py`.

The code lives in the `tracker` package; this script is the entry point the workflows and the README use.
"""
from tracker.cli import generate_report, generate_report_with_local_data, main  # noqa: F401

if __name__ == "__main__":
    main()
