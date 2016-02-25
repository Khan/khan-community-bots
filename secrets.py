import google.appengine.ext.ndb as ndb


class Secret(ndb.Model):
    """Stores a single secret in the datastore.

    Do not access this directly. Use `get_secret()` instead.
    """
    _use_memcache = False
    content = ndb.StringProperty(indexed=False)


def get_secret(name):
    """Gets a single secret value by name."""
    secret = Secret.get_by_id(name)
    if secret is None:
        raise ValueError("No secret found with name {!r}.".format(name))

    return secret.content
