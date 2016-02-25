def handle_issue_event(issue_or_pr):
    """When an event concerning an issue or PR is received, this method is
    called.
    """
    # Determine if this issue is no longer idle and remove the tag if so.

    # Determine if this issue will become idle or expired soon and store it
    # somewhere we'll look at later when marking things as idle and sending out
    # warnings.
    pass


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
