"""
The two ways to build a report: from the GitHub API, or again from the data files of an earlier run.
"""
import json
import os
import traceback
from datetime import datetime, timedelta

import pandas as pd

from . import aggregate, collect, config, github, privacy, report
from .log import _scrubber, logger


def generate_report(github_conf_path="input/github.json", output_dir="output/",
                    report_fname="github_contributions_report.md", percentage=-1):
    """
    Generate a GitHub contributions report by reading input data, processing it, and creating a markdown report.

    This function reads the input data from a JSON file, processes the GitHub contributions,
    and generates a markdown report with the contributions summary.

    Args:
        github_conf_path (str): The path to the GitHub input JSON file. Defaults to "input/github.json".
        output_dir (str): The directory to save the output markdown report. Defaults to "output/".
        report_fname (str): The filename for the output markdown report. Defaults to "github_contributions_report.md".
        percentage (int): The percentage threshold for grouping smaller values into 'Other'. This value represents the
            percentage of the maximum contribution. Defaults to -1 (no grouping).

    Returns:
        None

    Raises:
        Exception: If an error occurs during the process.
    """
    try:
        # Read input for GitHub from JSON file
        github_conf_data = config.read_github_input_file(github_conf_path)

        # Extract variables from the loaded data
        start_date = github_conf_data.get('start_date')
        end_date = github_conf_data.get('end_date')
        contribution_config = github_conf_data.get('contribution_config', {})
        users = github_conf_data.get('users', [])
        project_to_repo_dict = github_conf_data.get('project_to_repo_dict', {})
        # Checked first so a typo fails before any API call is made
        private_repos = privacy.resolve_private_repos_mode(github_conf_data.get('private_repos'))

        # Set default end_date to tomorrow if not provided
        if not end_date:
            tomorrow = datetime.now() + timedelta(days=1)
            end_date = tomorrow.strftime('%Y-%m-%d')

        # if project to repo dict is empty, use get_repositories_contributed_to to get the repositories
        if not project_to_repo_dict:
            project_to_repo_dict = {}
            for user in users:
                # for each project create one entry
                repo_list = github.get_repositories_contributed_to(user)
                for repo in repo_list:
                    project_to_repo_dict[repo] = [repo]

        # Ensure input is valid
        if not start_date:
            config.print_input_json_format()
            raise ValueError("Start date is required in the input data.")
        if not end_date:
            config.print_input_json_format()
            raise ValueError("End date is required in the input data.")
        if not users:
            config.print_input_json_format()
            raise ValueError("At least one user is required in the input data.")
        if not project_to_repo_dict:
            config.print_input_json_format()
            raise ValueError("At least one project with repositories is required in the input data.")

        # Lower case all the users
        users = [str(user).lower().strip() for user in users]

        # Reports are normally published publicly, so keep private repositories out of everything
        # that follows (searches, logs, files) unless the configuration asks for them.
        repo_infos = {}
        private_to_redact, skip_ranking = [], None
        _scrubber.clear()
        if private_repos == 'redact':
            found = privacy.classify_repositories(project_to_repo_dict)
            private_to_redact = found["private"]
            private_keys = {r.lower() for r in private_to_redact}
            _scrubber.hide(privacy.names_to_hide(found, project_to_repo_dict, users))
            project_to_repo_dict, repo_infos = found["visible"], found["infos"]
            skip_ranking = private_keys
            if private_to_redact:
                logger.info(f"Redacting {len(private_to_redact)} private repositories into one unnamed row per user.")
            if found["unavailable"]:
                logger.warning(f"Excluded {found['unavailable']} repositories this token cannot see "
                               f"(misspelt, renamed or not accessible); check the names in project_to_repo_dict.")
            if not project_to_repo_dict:
                raise ValueError("No repositories are left to report on: none of them is visible to this token.")
        elif private_repos == 'exclude':
            project_to_repo_dict, repo_infos, private_count, unavailable_count = \
                privacy.exclude_non_public_repositories(project_to_repo_dict)
            if private_count:
                logger.info(f"Excluded {private_count} private repositories "
                            f"(set \"private_repos\": \"include\" to keep them; do not publish such a report publicly).")
            if unavailable_count:
                logger.warning(f"Excluded {unavailable_count} repositories this token cannot see "
                               f"(misspelt, renamed or not accessible); check the names in project_to_repo_dict.")
            if not project_to_repo_dict:
                raise ValueError("No public repositories are left to report on after excluding "
                                 f"{private_count} private and {unavailable_count} inaccessible repositories.")
        else:
            logger.warning("private_repos is 'include': private repositories will appear in the report, the "
                           "data files and these logs. Do not publish them publicly.")

        # Log the variables to verify
        logger.info(f"Start Date: {start_date}")
        logger.info(f"End Date: {end_date}")
        logger.info(f"Users: {users}")
        logger.info(f"Project to Repo Dictionary: {project_to_repo_dict}")

        # Create markdown report
        github_data = collect.process_github_data(start_date, end_date, users, project_to_repo_dict, contribution_config,
                                          repo_infos=repo_infos, skip_ranking=skip_ranking)
        rows, activity = github_data
        if private_to_redact:
            rows, activity = privacy.redact_private_rows(rows, activity, private_to_redact)
        github_data_df = aggregate.convert_to_dataframe(rows)
        report.process_data_and_create_report(github_data_df, output_dir, report_fname, percentage, True, start_date, end_date, contribution_config, activity)

    except Exception as e:
        logger.error(f"An error occurred: {e}")
        raise


def generate_report_with_local_data(github_data_csv_path="output/github_contribution_data.csv",
                                    activity_data_json_path="output/github_activity_data.json",
                                    output_dir="output/",
                                    report_fname="github_contributions_report.md", percentage=-1):
    """
    Generate a GitHub contributions report by reading input data, processing it, and creating a markdown report.

    This function reads the input data from a CSV file, processes the GitHub contributions,
    and generates a markdown report with the contributions summary.

    Args:
        github_data_csv_path (str): The path to the GitHub input CSV file. Defaults to "output/github_contribution_data.csv".
        activity_data_json_path (str): The path to the activity data JSON file produced by a previous live run.
            Defaults to "output/github_activity_data.json". Pass None to skip the Activity Details section.
        output_dir (str): The directory to save the output markdown report. Defaults to "output/".
        report_fname (str): The filename for the output markdown report. Defaults to "github_contributions_report.md".
        percentage (int): The percentage threshold for grouping smaller values into 'Other'. This value represents the
            percentage of the maximum contribution. Defaults to -1 (no grouping).

    Returns:
        None

    Raises:
        Exception: If an error occurs during the process.
    """
    try:
        # Read input for GitHub from CSV file
        github_data_df = pd.read_csv(github_data_csv_path)

        # Load cached activity data (PR / issue objects) if available
        activity_data = None
        if activity_data_json_path and os.path.exists(activity_data_json_path):
            with open(activity_data_json_path, 'r') as af:
                activity_data = json.load(af)
            logger.info(f"Loaded activity data from '{activity_data_json_path}'")
        else:
            logger.warning("Activity data JSON not found; Activity Details section will be omitted from the report.")

        # Create markdown report
        report.process_data_and_create_report(github_data_df, output_dir, report_fname, percentage,
                                       shouldDump=False, activity_data=activity_data)

    except Exception as e:
        logger.error(f"An error occurred: {e}")
        raise


def main():
    try:
        logger.info("Script started.")
        # You can customize the input JSON file path, output directory, and report filename as follows:
        # generate_report(github_conf_path="input/github.json", output_dir="output/", report_fname="github_contributions_report.md")
        generate_report()

        # In order to generate the report with local data, in case you have the data
        # Comment the above code line i.e. generate_report()
        # Next, uncomment the below code line
        # generate_report_with_local_data()
        logger.info("Script completed successfully.")
        # Ensure an exit code of 0 upon successful completion, required by test workflow
        exit(0)
    except Exception as e:
        logger.error(f"Failed to complete job: {e}")
        logger.error(traceback.format_exc())
        exit(-1)
