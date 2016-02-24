import urlparse
import collections
import json
import logging
import datetime

import google.appengine.api.urlfetch as urlfetch
import webapp2

RepoID = collections.namedtuple("RepoID", ["owner", "name"])

def call_github_api(url):
    response = urlfetch.fetch(
        urlparse.urljoin("https://api.github.com", url),
        headers={
            "Accept": "Accept: application/vnd.github.v3+json"
        })
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

    def __init__(self, repo_id, issue_number):
        self.repo_id = repo_id
        self.issue_number = issue_number

    def fetch_issue_data(self):
        url = ("/repos/{repo_id.owner}/{repo_id.name}/issues/"
               "{issue_number}").format(
            repo_id=self.repo_id,
            issue_number=self.issue_number)

        return call_github_api(url)

    def fetch_event_activity(self):
        url = ("/repos/{repo_id.owner}/{repo_id.name}/issues/{issue_number}"
               "/events").format(
            repo_id=self.repo_id,
            issue_number=self.issue_number)

        return call_github_api(url)

    def fetch_comments(self):
        url = ("/repos/{repo_id.owner}/{repo_id.name}/issues/{issue_number}"
               "/comments").format(
            repo_id=self.repo_id,
            issue_number=self.issue_number)

        return call_github_api(url)

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


class MainPage(webapp2.RequestHandler):
    def get(self):
        self.response.headers['Content-Type'] = 'text/plain'
        self.response.write(repr(Issue(RepoID("brownhead", "haunted-house"), 1).get_idle_at()))

app = webapp2.WSGIApplication([
    ('/', MainPage),
], debug=True)
