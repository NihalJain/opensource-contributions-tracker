"""
Reading the input file (`input/github.json`) and resolving its per-metric settings.
"""
import json

from .log import logger


# The contribution_config metrics that are counted, in the order the report lists them.
METRICS = ('commits', 'open_prs', 'closed_prs', 'open_issues', 'closed_issues', 'code_reviews')


def read_github_input_file(file_path):
    """
    Read GitHub input data from a JSON file.

    Args:
        file_path (str): The path to the JSON file.

    Returns:
        dict: The data read from the JSON file.
    """
    try:
        with open(file_path, 'r') as json_file:
            data = json.load(json_file)
            logger.info(f"Successfully read data from {file_path}")
            return data
    except FileNotFoundError:
        logger.error(f"File not found: {file_path}")
        raise
    except json.JSONDecodeError:
        logger.error(f"Error decoding JSON from file: {file_path}")
        raise
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        raise


def _metric_cfg(contribution_config, key):
    """Return resolved {enabled, count_towards_score} for a metric key. Defaults to all-on."""
    cfg = (contribution_config or {}).get(key, {})
    return {
        'enabled': cfg.get('enabled', True),
        'count_towards_score': cfg.get('count_towards_score', True),
    }


def _line_stats_cfg(contribution_config):
    """
    Return resolved {enabled, refactor_threshold} for the line_stats metric.

    Unlike the other metrics this one is off unless asked for, as the README documents: it costs
    one extra API call per commit and per open PR, which dominates the run time.
    """
    cfg = (contribution_config or {}).get('line_stats', {})
    return {
        'enabled': cfg.get('enabled', False),
        'refactor_threshold': cfg.get('refactor_threshold', None),
    }

def print_input_json_format():
    """
    Print the format of the input JSON file for OpenSource contributions tracking.

    Returns:
        None
    """
    input_json = {
        "start_date": "YYYY-MM-DD",
        "end_date": "YYYY-MM-DD",
        "contribution_config": {
            "commits":       {"enabled": True, "count_towards_score": True},
            "open_prs":      {"enabled": True, "count_towards_score": True},
            "closed_prs":    {"enabled": True, "count_towards_score": False},
            "open_issues":   {"enabled": True, "count_towards_score": True},
            "closed_issues": {"enabled": True, "count_towards_score": True},
            "code_reviews":  {"enabled": True, "count_towards_score": True},
            "line_stats":    {"enabled": False, "refactor_threshold": 0.1}
        },
        "private_repos": "exclude",
        "users": ["user1", "user2"],
        "project_to_repo_dict": {
            "Project 1": ["owner1/repo1", "owner1/repo2"],
            "Project 2": ["owner2/repo3"]
        }
    }
    logger.info("Format of the input JSON file for OpenSource contributions tracking:")
    logger.info(json.dumps(input_json, indent=4))
    logger.info("NOTE: The 'project_to_repo_dict' key is optional."
                "If not provided, the script will use the 'users' key to get the repositories.")
    logger.info("NOTE: The 'private_repos' key is optional and defaults to 'exclude', which leaves private "
                "repositories out of the report. Use 'include' only when the report is not published publicly.")
