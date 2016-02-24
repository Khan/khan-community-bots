import urlparse
import collections
import json
import logging

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


class Issue(object):
    """Represents a GitHub issue.

    Pull requests are also considered issues for most purposes, so this can
    represent pull requests as well.
    """

    def __init__(self, repo_id, issue_number, event_activity=None):
        self.repo_id = repo_id
        self.issue_number = issue_number
        self.event_activity = event_activity

    def fetch_event_activity(self, ignore_stored_value=False):
        if ignore_stored_value and self.event_activity is not None:
            return self.event_activity

        url = ("/repos/{repo_id.owner}/{repo_id.name}/issues/{issue_number}"
               "/events").format(
            repo_id=self.repo_id,
            issue_number=self.issue_number)

        self.event_activity = call_github_api(url)
        return self.event_activity


class MainPage(webapp2.RequestHandler):
    def get(self):
        Issue(RepoID("brownhead", "haunted-house"), 1).fetch_event_activity()
        self.response.headers['Content-Type'] = 'text/plain'
        self.response.write('Hello, World!')

app = webapp2.WSGIApplication([
    ('/', MainPage),
], debug=True)
