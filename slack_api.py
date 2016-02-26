import json

import google.appengine.api.urlfetch as urlfetch

import secrets

def send_message(message):
    url = secrets.get_secret("slack-webhook-url")

    urlfetch.fetch(
        url,
        method="POST",
        headers={"Content-Type": "application/json"},
        payload=json.dumps({
            "username": "Community Lead Bot",
            "icon_emoji": ":github:",
            "text": message,
        }))
