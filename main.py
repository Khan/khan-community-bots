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


class BaseIssue(object):
    """Represents a GitHub issue.

    Pull requests are also considered issues for most purposes, so this can
    represent pull requests as well.
    """

    CONTROLLED_LABELS = {"idle", "waiting for submitter"}

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

    def fetch_controlled_label_names(self):
        """Fetches the labels associated with the issue.

        Returns only the names of controlled labels in a set.
        """
        return {i["name"] for i in self.fetch_labels()
                if i["name"] in self.CONTROLLED_LABELS}

    def set_labels(self, labels, ignore=None):
        if not labels.issubset(self.CONTROLLED_LABELS):
            raise ValueError(
                "Uncontrolled labels present: %r" % (
                    labels - self.CONTROLLED_LABELS))

        current_labels = self.fetch_controlled_label_names()
        current_labels -= ignore if ignore else set()

        to_delete = current_labels - labels
        for label in to_delete:
            logging.info("Removing label %r from issue %r", label, self)
            call_github_api(self.get_base_url() + "/labels/" + label,
                            method=urlfetch.DELETE)

        to_add = labels - current_labels
        logging.info("Adding labels %r to issue %r", to_add, self)
        call_github_api(self.get_base_url() + "/labels",
                        method=urlfetch.POST, payload=list(to_add))

    def _get_expired_at(self, expire_time_delta):
        """Get the time at which this issue will become expired.

        If this time is in the past, then this issue is currently expired.

        An issue is expired if it has been labeled with `waiting for submitter`
        continuously for the last `expire_time_delta`.
        """
        events = self.fetch_event_activity()

        # Get the last labeling and unlabeling event involving the `waiting for
        # submitter` label.
        labeling_events = [
            event for event in events
            if event["event"] in ["labeled", "unlabeled"] and
               event["label"]["name"] == "waiting for submitter"]
        last_event = labeling_events[-1] if labeling_events else None

        # If the issue is not currently labeled as waiting for submitter, it
        # cannot expire.
        if last_event["event"] == "unlabled":
            return None

        return convert_date_time(last_event["created_at"]) + expire_time_delta


class Issue(BaseIssue):
    def __init__(self, *args, **kwargs):
        super(Issue, self).__init__(*args, **kwargs)

    def get_idle_at(self):
        """Get the time at which this issue will become idle.

        If this time is in the past, then this issue is currently idle.

        An issue is idle if a contributer has not commented on it within a
        configurable time span (defaults to 7 days).
        """

        comments = self.fetch_comments()

        # If any contributor has commented on this issue, than it has been
        # implicitly accepted and will never become idle.
        if any(is_contributer(self.repo_id, comment["user"]["login"])
               for comment in comments):
            return None

        # Otherwise, it'll expire a set time after the issue was created
        issue_data = self.fetch_issue_data()
        return convert_date_time(issue_data["created_at"]) + datetime.timedelta(days=7)

    def get_applicable_labels(self):
        """Returns a set of labels that apply to this issue."""
        labels = set()
        if datetime.datetime.now() >= self.get_idle_at():
            labels.add("idle")
        return labels

    def process(self):
        """Does any actions required for an issue.

        This will check to see if we need to do anything, and then do it.
        """
        desired_labels = self.get_applicable_labels()
        self.set_labels(desired_labels, ignore={"waiting for submitter"})


class PullRequest(BaseIssue):
    def __init__(self, *args, **kwargs):
        super(PullRequest, self).__init__(*args, **kwargs)

    def get_idle_at(self):
        """Gets the time at which this pull request will become idle.

        If this time is in the past, then this pull request is currently idle.

        To define what it takes for a PR to be idle... The amount of time it
        takes for a PR to become idle is configurable and let's say that time
        delta is `idle_time_delta`. An issue is idle if neither of these two
        events have occurred within the last `idle_time_delta`: (1) a
        contributor has commented, or (2) the label `waiting for submitter` has
        been removed. A PR cannot be idle if the `waiting for submitter` label
        is currently atttached to it.
        """
        # Figure out if we're waiting for the submitter (in which case we
        # cannot become idle).
        current_labels = self.fetch_controlled_label_names()
        if "waiting for submitter" in current_labels:
            return None

        def get_latest(sequence):
            """Get the latest datetime in a sequence of them.

            None values will be ignored, and None will be returned if the
            sequence is empty.
            """
            pruned_sequence = [i for i in sequence if i is not None]
            if not pruned_sequence:
                return None

            return max(pruned_sequence)

        # Figure out that last time the "waiting for submitter" label was removed
        # from this PR.
        events = self.fetch_event_activity()
        last_unlabeled = get_latest(
            convert_date_time(event["created_at"]) for event in events
            if event["event"] == "unlabeled" and
               event["label"]["name"] == "waiting for submitter")

        # Figure out the last time a contributor commented on this PR
        comments = self.fetch_comments()
        last_commented = get_latest(
            convert_date_time(comment["created_at"]) for comment in comments
            if is_contributer(self.repo_id, comment["user"]["login"]))

        created_at = convert_date_time(self.fetch_issue_data()["created_at"])
        return get_latest([created_at, last_unlabeled, last_commented]) + datetime.timedelta(days=7)

    def get_applicable_labels(self):
        """Returns a set of labels that apply to this pull request."""
        labels = set()
        if datetime.datetime.now() >= self.get_idle_at():
            labels.add("idle")
        return labels

    def process(self):
        """Does any actions required for an pull request.

        This will check to see if we need to do anything, and then do it.
        """
        desired_labels = self.get_applicable_labels()
        self.set_labels(desired_labels, ignore={"waiting for submitter"})


class MainPage(webapp2.RequestHandler):
    def get(self):
        self.response.headers['Content-Type'] = 'text/plain'

        test_pull_request = PullRequest(RepoID("brownhead", "haunted-house"), 2)
        self.response.write(test_pull_request.get_idle_at().strftime("%Y-%m-%d %H:%M:%S"))

app = webapp2.WSGIApplication([
    ('/', MainPage),
], debug=True)
