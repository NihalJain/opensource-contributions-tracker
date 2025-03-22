# OpenSource Contributions Tracker

OpenSource Contributions Tracker is a powerful and easy-to-use tool designed to help developers and organizations keep
track of their open-source contributions. Whether you're contributing to multiple projects or managing a team of
contributors, this tool provides a centralized place to monitor your progress, celebrate milestones, and showcase your
impact on the open-source community.

## Features

The tool is designed to track and report contributions to open-source projects on GitHub for one user or a group of
users. It generates detailed reports on commits and pull requests made by users across various repositories and
projects. It also displays summary tables and pie charts to visualize the contributions. It groups the contributions by
users and projects, making it easy to identify the most active contributors and the most popular projects. Also provides
insights into the overall contribution metrics like the total number of projects, repositories, and contributions.


## How it works?

The tool works in four main steps:

- **Data Retrieval**: Fetches commits and pull requests from GitHub repositories.
- **Data Processing**: Aggregates and processes the data to provide meaningful insights.
- **Report Generation**: Creates markdown reports with summary tables and pie charts.
- **Automated Execution**: Can be scheduled to run periodically using GitHub Actions.

## How to use?

1. **Fork the repository**.
2. **Update the input data file**
    - Modify the `input/github.json` file to include the list of users and projects you want to track.
    - Set the `start_date` to the date from which you want to start tracking contributions.
    - Add the list of GitHub usernames under `users`.
    - Map the project names to their corresponding GitHub repositories under `project_to_repo_dict` which needs to be
      tracked.
    - Save the changes to the file.
3. **Commit and Push the changes**.
    - NOTE: If you are running the tool locally, you can skip this step. Also without committing the changes, the
      workflow will not be triggered in forked repositories.
4. **Review the report**
    - The tool will automatically generate a report and add it to the `output` directory in file
      `github_contributions_report.md` at the scheduled time.
    - You can view the report to see the summary of contributions by each user and project, along with detailed
      contributions.

## Demo

A sample report generated by the tool can be found [here](output/github_contributions_report.md).

## Local Setup

To run the project locally, follow the steps below:

### Installation

1. **Clone the repository**:
    ```sh
    git clone https://github.com/NihalJain/opensource-contributions-tracker.git
    cd opensource-contributions-tracker
    ```

2. **Install dependencies**:
    ```sh
    pip install -r requirements.txt
    ```

### Configuration

1. **Set up environment variables**:
    - `GITHUB_TOKEN`: Your GitHub personal access token.
    - `HTTP_PROXY` and `HTTPS_PROXY`: (Optional) Proxy settings if required.

2. **Input Data File**:
    - The input data file should be a JSON file located at `input/github.json`.
    - This file should contain the following structure:
        ```json
        {
            "start_date": "YYYY-MM-DD",
            "users": ["user1", "user2"],
            "project_to_repo_dict": {
                "Project1": ["repo1", "repo2"],
                "Project2": ["repo3"]
            }
        }
        ```
    - where
        - `start_date` is the date from which to start tracking contributions
        - `users` is a list of GitHub usernames,
        - and `project_to_repo_dict` maps project names to their corresponding GitHub repositories.

### Usage

1. **Generate the report**:
    ```sh
    python generate_report.py
    ```

2. **View the report**:
    - The report will be generated in the `output` directory as `github_contributions_report.md`.

## Github Actions (Automated workflow)

- **GitHub Actions**:
    - The project includes a GitHub Actions workflow to automate the report generation.
    - The workflow is defined in `.github/workflows/main.yml`.
    - No need to manually trigger the report generation; it will run automatically based on the schedule defined in the
      workflow. By default, it is scheduled to run every 24 hours. This can be modified as per your requirements.
    - You can check the status of the workflow in the "Actions" tab of the GitHub repository.
    - You can also manually trigger the workflow, if needed. (See below!)

- **Updating the Workflow**:
    - If you need to update the workflow, you can modify the `.github/workflows/main.yml` file as per your requirements.
    - The changes will be reflected in the workflow execution. Or you can run the workflow manually to test the changes.

- **Update the github.json file**:
    - In order to update the user/repo list configuration, you can modify the `input/github.json` file as per your
      requirements.
    - See the "Configuration" section above for more details.
    - The changes will be reflected in the report generated by the workflow.

### Steps to trigger the workflow manually

1. Go to the "Actions" tab of the GitHub repository.
2. Click on the workflow you want to run i.e. "Open Source Contribution Tracker Job".
3. Click on the "Run workflow" button on the right side.
4. Select the branch (default is main) and click on the "Run workflow" button.
5. The workflow will be triggered manually. You can check the status of the workflow in the "Actions" tab.
6. Once the workflow is completed, you can check the generated report in the "output" directory. The report will be
   saved as `github_contributions_report.md`.

## Contributing

1. **Fork the repository**.
2. **Create a new branch**:
    ```sh
    git checkout -b feature-branch
    ```
3. **Make your changes**.
4. **Stage your changes**:
    ```sh
    git add .
    ```
5. **Commit your changes**:
    ```sh
    git commit -m "Description of changes"
    ```
6. **Push to the branch**:
    ```sh
    git push origin feature-branch
    ```
7. **Create a pull request**.

## License

This project is licensed under the Apache License 2.0. See the [LICENSE](LICENSE) file for details.

## Contact

For any questions or suggestions, please open an issue or contact the repository
owner [Nihal Jain](https://www.linkedin.com/in/nihaljain/)