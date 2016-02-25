import google.appengine.ext.ndb as ndb


class Secret(ndb.Model):
    """Models an individual Guestbook entry with content and date."""
    _use_memcache = False
    content = ndb.StringProperty(indexed=False)


def get_secret(name):
    secret = Secret.get_by_id(name)
    if secret is None:
        raise ValueError("No secret found with name {!r}.".format(name))

    return secret.content
