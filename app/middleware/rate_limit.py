"""
Per-IP request limits, counted in Redis so every instance shares one budget.

Fixed-window counter: INCR a key named for the current window, set its TTL on
first hit, reject once the count exceeds the limit. Cheap (one round trip) and
good enough to stop floods and credential stuffing. The trade-off versus a
sliding window is burstiness at window boundaries — a client can spend its full
budget at the end of one window and again at the start of the next.

Key format matches the other backends: ratelimit:{service}:{scope}:{ip}:{window}
"""

import os
import time

from flask import jsonify, request

import app.extensions as ext

SERVICE_NAME = os.getenv('RATE_LIMIT_SERVICE', 'storefront-flask')

ENABLED = os.getenv('RATE_LIMIT_ENABLED', 'true').lower() != 'false'
GLOBAL_LIMIT = int(os.getenv('RATE_LIMIT_GLOBAL', '100'))
GLOBAL_WINDOW = int(os.getenv('RATE_LIMIT_GLOBAL_WINDOW', '60'))
# Login/refresh/register/reset are what actually get brute-forced.
AUTH_LIMIT = int(os.getenv('RATE_LIMIT_AUTH', '10'))
AUTH_WINDOW = int(os.getenv('RATE_LIMIT_AUTH_WINDOW', '60'))

STRICT_PREFIXES = [
    p.strip()
    for p in os.getenv('RATE_LIMIT_STRICT_PREFIXES', '/api/auth').split(',')
    if p.strip()
]

# X-Forwarded-For is client-settable, so only trust it behind a proxy you control —
# otherwise anyone can forge an identity and sidestep the limit entirely.
TRUST_FORWARDED = os.getenv('RATE_LIMIT_TRUST_PROXY', 'false').lower() == 'true'


def _resolve_client_id():
    if TRUST_FORWARDED:
        forwarded = request.headers.get('X-Forwarded-For')
        if forwarded:
            return forwarded.split(',')[0].strip()
    return request.remote_addr or 'unknown'


def register_rate_limiter(app):
    """Installs before_request/after_request hooks implementing the limit."""

    @app.before_request
    def _enforce_rate_limit():
        # CORS preflights are issued by the browser, not the caller — charging them
        # would halve every cross-origin client's effective budget.
        if not ENABLED or ext.redis_client is None or request.method == 'OPTIONS':
            return None

        path = request.path or ''
        is_strict = any(path.startswith(prefix) for prefix in STRICT_PREFIXES)

        limit = AUTH_LIMIT if is_strict else GLOBAL_LIMIT
        window = max(1, AUTH_WINDOW if is_strict else GLOBAL_WINDOW)
        scope = 'auth' if is_strict else 'global'

        now = int(time.time())
        window_index = now // window
        key = f'ratelimit:{SERVICE_NAME}:{scope}:{_resolve_client_id()}:{window_index}'

        try:
            count = ext.redis_client.incr(key)
            # Only the request that created the key sets the TTL, so the window
            # doesn't slide forward on every hit.
            if count == 1:
                ext.redis_client.expire(key, window)
        except Exception as e:
            # Fail open. A Redis outage must degrade to "unlimited", never to "down".
            print(f'Rate limit check failed, allowing request: {e}')
            return None

        reset_seconds = max(1, (window_index + 1) * window - now)

        # Stashed for after_request, which attaches them to every response.
        request.rate_limit_headers = {
            'X-RateLimit-Limit': str(limit),
            'X-RateLimit-Remaining': str(max(0, limit - count)),
            'X-RateLimit-Reset': str(reset_seconds),
        }

        if count > limit:
            response = jsonify({
                'error': 'rate_limited',
                'error_description': (
                    f'Too many requests. Please try again in {reset_seconds} seconds.'
                ),
            })
            response.status_code = 429
            response.headers['Retry-After'] = str(reset_seconds)
            for header, value in request.rate_limit_headers.items():
                response.headers[header] = value
            return response

        return None

    @app.after_request
    def _attach_rate_limit_headers(response):
        for header, value in getattr(request, 'rate_limit_headers', {}).items():
            response.headers.setdefault(header, value)
        return response
