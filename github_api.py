import urlparse
import collections
import json
import logging
import datetime

import google.appengine.api.urlfetch as urlfetch

import secrets

RepoID = collections.namedtuple("RepoID", ["owner", "name"])


def is_contributer(repo_id, user_login):
    return True


def call_github_api(url, method=urlfetch.GET, payload=None):
    full_url = urlparse.urljoin("https://api.github.com", url)
    logging.info("Making %r request to %r.", method, full_url)

    headers = {
        "Accept": "Accept: application/vnd.github.v3+json",
        "Authorization": "Basic " + secrets.get_secret("community-lead-bot-auth"),
    }
    if method == urlfetch.POST and payload is not None:
        headers["Content-Type"] = "application/json"

    encoded_payload = None if payload is None else json.dumps(payload)

    response = urlfetch.fetch(
        full_url,
        headers=headers,
        method=method,
        payload=encoded_payload)
    if response.status_code != 200:
        logging.error("Got error response %r", response.content)
        raise RuntimeError()
    return json.loads(response.content)


def convert_date_time(date_time_string):
    return datetime.datetime.strptime(date_time_string, "%Y-%m-%dT%H:%M:%SZ")


class BaseIssue(object):
    """Represents a GitHub issue.

    Pull requests are also considered issues for most purposes, so this can
    represent pull requests as well.
    """

    CONTROLLED_LABELS = {"idle", "waiting for submitter"}

    def __init__(self, repo_id, number):
        self.repo_id = repo_id
        self.number = number

    def get_base_url(self):
        return ("/repos/{repo_id.owner}/{repo_id.name}/issues/"
                "{number}").format(
            repo_id=self.repo_id,
            number=self.number)

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

    def add_label(self, label):
        current_labels = self.fetch_controlled_label_names()
        if label in current_labels:
            return

        logging.info("Adding label %r to issue %r", label, self)
        call_github_api(self.get_base_url() + "/labels",
                        method=urlfetch.POST, payload=[label])

    def remove_label(self, label):
        current_labels = self.fetch_controlled_label_names()
        if label not in current_labels:
            return

        logging.info("Removing label %r from issue %r", label, self)
        call_github_api(self.get_base_url() + "/labels/" + label,
                        method=urlfetch.DELETE)

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

    def get_applicable_labels(self):
        """Returns a set of labels that apply to this issue."""
        labels = set()
        idle_at = self.get_idle_at()
        if idle_at and datetime.datetime.now() >= idle_at:
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
