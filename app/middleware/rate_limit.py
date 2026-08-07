"""
Per-IP token bucket, held in Redis so every instance shares one budget.

Each client gets a bucket of RATE_LIMIT_*_BURST tokens that refills continuously
at limit/window tokens per second. A request spends one token; if the bucket is
empty the request is rejected.

Chosen over a fixed window because a fixed window lets a client spend its whole
budget at the end of one window and again at the start of the next — a 2x burst at
the boundary. A bucket smooths that out: burst size is capped by capacity and the
long-run average can never exceed the refill rate.

Key format matches the other backends: ratelimit:{service}:{scope}:{ip}
"""

import os

from flask import jsonify, request

import app.extensions as ext

SERVICE_NAME = os.getenv('RATE_LIMIT_SERVICE', 'storefront-flask')

ENABLED = os.getenv('RATE_LIMIT_ENABLED', 'true').lower() != 'false'

# Sustained rate: LIMIT tokens per WINDOW seconds. BURST is the bucket capacity
# (largest instantaneous burst) and defaults to the limit.
GLOBAL_LIMIT = int(os.getenv('RATE_LIMIT_GLOBAL', '100'))
GLOBAL_WINDOW = int(os.getenv('RATE_LIMIT_GLOBAL_WINDOW', '60'))
GLOBAL_BURST = int(os.getenv('RATE_LIMIT_GLOBAL_BURST', str(GLOBAL_LIMIT)))

# Login/refresh/register/reset are what actually get brute-forced.
AUTH_LIMIT = int(os.getenv('RATE_LIMIT_AUTH', '10'))
AUTH_WINDOW = int(os.getenv('RATE_LIMIT_AUTH_WINDOW', '60'))
AUTH_BURST = int(os.getenv('RATE_LIMIT_AUTH_BURST', str(AUTH_LIMIT)))

STRICT_PREFIXES = [
    p.strip()
    for p in os.getenv('RATE_LIMIT_STRICT_PREFIXES', '/api/auth').split(',')
    if p.strip()
]

# X-Forwarded-For is client-settable, so only trust it behind a proxy you control —
# otherwise anyone can forge an identity and sidestep the limit entirely.
TRUST_FORWARDED = os.getenv('RATE_LIMIT_TRUST_PROXY', 'false').lower() == 'true'

# Token bucket, evaluated atomically so concurrent requests can't both read the
# same token count and each decide they may proceed.
#
# Time comes from redis.call('TIME'), not the caller: instances may have skewed
# clocks, and the bucket must advance on a single shared timeline. Safe to
# replicate since Redis 5 propagates script *effects* rather than the script.
#
# Must stay byte-identical to the C# and node copies so all services agree.
TOKEN_BUCKET_SCRIPT = """
local key      = KEYS[1]
local capacity = tonumber(ARGV[1])
local refill   = tonumber(ARGV[2])
local wanted   = tonumber(ARGV[3])

local t   = redis.call('TIME')
local now = tonumber(t[1]) + (tonumber(t[2]) / 1000000)

local bucket = redis.call('HMGET', key, 'tokens', 'ts')
local tokens = tonumber(bucket[1])
local ts     = tonumber(bucket[2])

if tokens == nil or ts == nil then
  tokens = capacity
  ts     = now
end

local elapsed = now - ts
if elapsed > 0 then
  tokens = math.min(capacity, tokens + (elapsed * refill))
end

local allowed = 0
if tokens >= wanted then
  tokens  = tokens - wanted
  allowed = 1
end

redis.call('HSET', key, 'tokens', tokens, 'ts', now)
-- Reclaim idle buckets once they would have refilled completely.
redis.call('EXPIRE', key, math.ceil(capacity / refill) + 1)

local retry = 0
if allowed == 0 then
  retry = math.ceil((wanted - tokens) / refill)
end

return { allowed, math.floor(tokens), retry }
"""

# Populated on first use; register_script calls via EVALSHA and falls back to EVAL
# automatically if the server has forgotten the script (e.g. after SCRIPT FLUSH).
_token_bucket = None


def _get_script():
    global _token_bucket
    if _token_bucket is None and ext.redis_client is not None:
        _token_bucket = ext.redis_client.register_script(TOKEN_BUCKET_SCRIPT)
    return _token_bucket


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
        capacity = max(1, AUTH_BURST if is_strict else GLOBAL_BURST)
        scope = 'auth' if is_strict else 'global'

        # Tokens per second. Guarded so a misconfigured 0 limit can't divide by zero.
        refill_per_second = max(0.0001, limit / window)
        key = f'ratelimit:{SERVICE_NAME}:{scope}:{_resolve_client_id()}'

        try:
            script = _get_script()
            allowed_flag, tokens_left, retry = script(
                keys=[key], args=[capacity, refill_per_second, 1]
            )
            allowed = int(allowed_flag) == 1
            remaining = int(tokens_left)
            retry_after = max(1, int(retry))
        except Exception as e:
            # Fail open. A Redis outage must degrade to "unlimited", never to "down".
            print(f'Rate limit check failed, allowing request: {e}')
            return None

        # Stashed for after_request, which attaches them to every response.
        request.rate_limit_headers = {
            'X-RateLimit-Limit': str(capacity),
            'X-RateLimit-Remaining': str(max(0, remaining)),
        }

        if not allowed:
            response = jsonify({
                'error': 'rate_limited',
                'error_description': (
                    f'Too many requests. Please try again in {retry_after} seconds.'
                ),
            })
            response.status_code = 429
            response.headers['Retry-After'] = str(retry_after)
            response.headers['X-RateLimit-Reset'] = str(retry_after)
            for header, value in request.rate_limit_headers.items():
                response.headers[header] = value
            return response

        return None

    @app.after_request
    def _attach_rate_limit_headers(response):
        for header, value in getattr(request, 'rate_limit_headers', {}).items():
            response.headers.setdefault(header, value)
        return response
