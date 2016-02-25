import json

import webapp2

import community_lead_bot
import github_api


class UnexpectedGithubEvent(RuntimeError):
    def __init__(self, event):
        self.event = event

    def __repr__(self):
        return "UnexpectedGithubEvent(event={!r})".format(self.event)


class HealthCheck(webapp2.RequestHandler):
    def get(self):
        limit_info = github_api.call_github_api("/rate_limit")
        if limit_info["rate"]["limit"] < 5000:
            raise RuntimeError("Using unauthenticated rate.")

        self.response.headers["Content-Type"] = "text/plain"
        self.response.write("ok")


class IssueWebhook(webapp2.RequestHandler):
    """Handler for webhooks concerning issues."""

    def construct_issue(self):
        """Creates an Issue with the information contained in the request.

        This will interpret the payload based on the event type. If the event
        type is not recognized, an UnexpectedGithubEvent will be raised.
        """
        payload_json = json.loads(self.request.body)
        event_type = self.request.headers["X-Github-Event"]
        if event_type != "issues" and event_type != "issue_comment":
            raise UnexpectedGithubEvent(event_type)

        return github_api.Issue(
            github_api.RepoID(payload_json["repository"]["owner"]["login"],
                              payload_json["repository"]["name"]),
            payload_json["issue"]["number"])

    def post(self):
        issue = self.construct_issue()
        community_lead_bot.handle_issue_event(issue)

        self.response.headers["Content-Type"] = "text/plain"
        self.response.write("ok")

app = webapp2.WSGIApplication([
    ("/health-check", HealthCheck),
    ("/community-lead-bot/webhooks/github/issue", IssueWebhook),
])
