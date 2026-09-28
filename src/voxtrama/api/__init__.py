"""Public surface of the API entrypoint.

Nothing re-exported here: every caller already imports
voxtrama.api.app directly (gunicorn's own "voxtrama.api.app:app", every
test's "from voxtrama.api.app import create_app"). Re-exporting app
and create_app at package level meant `import voxtrama.api.<anything>`
always pulled in app.py, which imports every router in api.routes,
including ones that import from voxtrama.rendering, which imports back
into api. A package that only has to exist should not be the thing
that closes that loop.
"""
