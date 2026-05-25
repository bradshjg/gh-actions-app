import base64
import os
import re
import typing

from github3 import GitHub
from github3.pulls import PullRequest

from flask import Flask
from flask_githubapp import GitHubApp

app = Flask(__name__)

app.config["GITHUBAPP_ID"] = int(os.environ["GITHUBAPP_ID"])
app.config["GITHUBAPP_KEY"] = base64.b64decode(os.environ["GITHUBAPP_KEY_B64"])
app.config["GITHUBAPP_SECRET"] = os.environ["GITHUBAPP_SECRET"]

github_app = GitHubApp(app)


DEPLOY_COMMENT_REGEX = re.compile(
    r"^/deploy\s*(?P<environment>[\w-]+)\s*(?P<no_cache>--no-cache)?"
)


@github_app.on("issue_comment.created")
def deploy():
    """/deploy slash command for pull requests

    The deployment workflow must be called `deployment.yml`, triggger on workflow dispatch, and accept "environment"
    and "use_cache" inputs.

    The comment format is

    /deploy <environment> [--no-cache]
    """
    client = typing.cast(GitHub, github_app.installation_client)
    payload = github_app.payload

    if "pull_request" not in payload["issue"]:
        return

    match = DEPLOY_COMMENT_REGEX.match(payload["comment"]["body"])
    if not match:
        return

    environment = match.group("environment")
    use_cache = not match.group("no_cache")

    owner = payload["repository"]["owner"]["login"]
    repository = payload["repository"]["name"]
    pr_number = payload["issue"]["number"]
    pull_request = typing.cast(
        PullRequest,
        client.pull_request(owner=owner, repository=repository, number=pr_number),
    )
    ref = pull_request.head.ref

    repo_nwo = payload["repository"]["full_name"]
    workflow_name = "deployment.yml"
    dispatch_url = f"https://api.github.com/repos/{repo_nwo}/actions/workflows/{workflow_name}/dispatches"
    response = client.session.post(
        dispatch_url,
        json={
            "ref": ref,
            "inputs": {
                "environment": environment,
                "use_cache": "true" if use_cache else "false",
            },
        },
    )
    response.raise_for_status()
