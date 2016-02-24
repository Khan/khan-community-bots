import os
import urlparse
import collections
import json
import logging
import datetime
import base64

import google.appengine.api.urlfetch as urlfetch
import webapp2

import secrets

RepoID = collections.namedtuple("RepoID", ["owner", "name"])


def call_github_api(url, method=urlfetch.GET, payload=None):
    full_url = urlparse.urljoin("https://api.github.com", url)
    logging.info("Making %r request to %r.", method, full_url)

    headers = {
        "Accept": "Accept: application/vnd.github.v3+json",
        "Authorization": "Basic " + secrets.COMMUNITY_LEAD_BOT_AUTH,
    }
    if method == urlfetch.POST and payload is not None:
        headers["Content-Type"] = "application/json"

    encoded_payload = None if payload is None else json.dumps(payload)

    logging.info("%r %r", encoded_payload, headers)

    response = urlfetch.fetch(
        full_url,
        headers=headers,
        method=method,
        payload=encoded_payload)
    if response.status_code != 200:
        logging.error("Got error response %r", response.content)
        raise RuntimeError()
    return json.loads(response.content)


def is_contributer(repo_id, user_login):
    return True


def convert_date_time(date_time_string):
    return datetime.datetime.strptime(date_time_string, "%Y-%m-%dT%H:%M:%SZ")


class Issue(object):
    """Represents a GitHub issue.

    Pull requests are also considered issues for most purposes, so this can
    represent pull requests as well.
    """

    CONTROLLED_LABELS = {"idle"}

    def __init__(self, repo_id, issue_number):
        self.repo_id = repo_id
        self.issue_number = issue_number

    def get_base_url(self):
        return ("/repos/{repo_id.owner}/{repo_id.name}/issues/"
                "{issue_number}").format(
            repo_id=self.repo_id,
            issue_number=self.issue_number)

    def fetch_issue_data(self):
        return call_github_api(self.get_base_url())

    def fetch_event_activity(self):
        return call_github_api(self.get_base_url() + "/events")

    def fetch_comments(self):
        return call_github_api(self.get_base_url() + "/comments")

    def fetch_labels(self):
        return call_github_api(self.get_base_url() + "/labels")

    def get_idle_at(self):
        comments = self.fetch_comments()

        # If any contributor has commented on this issue, than it has been
        # implicitly accepted and will never become idle.
        if any(is_contributer(self.repo_id, comment["user"]["login"])
               for comment in comments):
            return None

        # Otherwise, it'll expire a set time after the issue was created
        issue_data = self.fetch_issue_data()
        return convert_date_time(issue_data["created_at"]) + datetime.timedelta(days=7)

    def set_labels(self, labels):
        if not labels.issubset(self.CONTROLLED_LABELS):
            raise ValueError(
                "Uncontrolled labels present: %r" % (
                    labels - self.CONTROLLED_LABELS))

        current_labels = {i["name"] for i in self.fetch_labels()
                          if i["name"] in self.CONTROLLED_LABELS}

        to_delete = current_labels - labels
        for label in to_delete:
            logging.info("Removing label %r from issue %r", label, self)
            call_github_api(self.get_base_url() + "/labels/" + label,
                            method=urlfetch.DELETE)

        to_add = labels - current_labels
        logging.info("Adding labels %r to issue %r", to_add, self)
        call_github_api(self.get_base_url() + "/labels",
                        method=urlfetch.POST, payload=list(to_add))


class MainPage(webapp2.RequestHandler):
    def get(self):
        self.response.headers['Content-Type'] = 'text/plain'

        test_issue = Issue(RepoID("brownhead", "haunted-house"), 1)
        test_issue.set_labels(set())
        self.response.write("Hello")

app = webapp2.WSGIApplication([
    ('/', MainPage),
], debug=True)
