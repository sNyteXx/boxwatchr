# rspamd local.d overrides

Place `.conf` files here to customize rspamd. They are copied into rspamd's `local.d` on container startup.

Do not create `classifier-bayes.conf` or `redis.conf` here. Both are auto-generated at startup and will overwrite anything you put here.
