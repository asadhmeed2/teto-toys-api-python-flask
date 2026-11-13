# Loaded automatically by gunicorn from the working directory.
# gunicorn writes its own "Server: gunicorn" line on every response, ignoring the
# app's header; overwrite the module global it reads so the stack isn't advertised.
import gunicorn.http.wsgi

gunicorn.http.wsgi.SERVER = "teto-toys"
