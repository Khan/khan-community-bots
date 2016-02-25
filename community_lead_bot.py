import github_api

def get_issue_idle_at(issue):
    """Get the time at which the issue will become idle.

    If this time is in the past, then the issue is currently idle.

    An issue is idle if a contributer has not commented on it within a
    configurable time span (defaults to 7 days). Once a contributor comments
    on an issue, it will never become idle.
    """
    comments = issue.fetch_comments()

    # If any contributor has commented on this issue, than it has been
    # implicitly accepted and will never become idle.
    if any(github_api.is_contributer(issue.repo_id, comment["user"]["login"])
           for comment in comments):
        return None

    # Otherwise, it'll expire a set time after the issue was created
    issue_data = issue.fetch_issue_data()
    return convert_date_time(issue_data["created_at"]) + datetime.timedelta(days=7)


def get_pull_request_idle_at(pull_request):
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
    current_labels = pull_request.fetch_controlled_label_names()
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
    events = pull_request.fetch_event_activity()
    last_unlabeled = get_latest(
        convert_date_time(event["created_at"]) for event in events
        if event["event"] == "unlabeled" and
           event["label"]["name"] == "waiting for submitter")

    # Figure out the last time a contributor commented on this PR
    comments = pull_request.fetch_comments()
    last_commented = get_latest(
        convert_date_time(comment["created_at"]) for comment in comments
        if github_api.is_contributer(pull_request.repo_id, comment["user"]["login"]))

    created_at = convert_date_time(pull_request.fetch_issue_data()["created_at"])
    return get_latest([created_at, last_unlabeled, last_commented]) + datetime.timedelta(days=7)


def handle_issue_event(issue_or_pr):
    """When an event concerning an issue or PR is received, this method is
    called.
    """
    # Determine if this issue is no longer idle and remove the tag if so.
    idle_at = None
    if isinstance(issue_or_pr, github_api.Issue):
        idle_at = get_issue_idle_at(issue_or_pr)
    elif isinstance(issue_or_pr, github_api.PullRequest):
        idle_at = get_pull_request_idle_at(issue_or_pr)
    else:
        raise ValueError("Did not receive an Issue or Pull Request")

    if idle_at is None:
        issue_or_pr.remove_label("idle")

    # Determine if this issue will become idle or expired soon and store it
    # somewhere we'll look at later when marking things as idle and sending out
    # warnings.


def handle_idle_check(issue_or_pr):
    """This is called whenever we suspect an issue or PR may have become
    idle."""
    # Determine if this issue is idle and mark it if so.
    pass


def handle_expire_check(issue_or_pr):
    """This is called whenever we suspect an issue or PR may have expired."""
    # Determine if this issue is expired and close it if so, as well as post
    # the expired message.
    pass


def ping_leads_of_idle_issues():
    """This is called every day and sends slack messages to community leads.

    If any issues or PRs are idle, we'll message the corresponding leads.
    """
    pass


def send_daily_summary():
    """This posts a summary of our repos to the #open-source slack room."""
    pass
