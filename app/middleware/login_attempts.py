"""
Per-account failed-login throttle, counted in Redis.

The IP rate limiter caps how fast any one host can call the API; this caps how
many times a *specific account* may be guessed, no matter how many hosts try.
The two are complementary: distributed credential stuffing spreads across IPs
but still converges on one email.

The counter is keyed by a hash of the email, not the email itself, so Redis
never holds a plaintext list of who has been attacked.

Key format matches the other backends: login_fail:{service}:{emailHash}
"""

import hashlib
import os

import app.extensions as ext

SERVICE = os.getenv('LOGIN_LOCKOUT_SERVICE', 'storefront-flask')
MAX_ATTEMPTS = int(os.getenv('LOGIN_LOCKOUT_MAX_ATTEMPTS', '5'))
LOCKOUT_SECONDS = int(os.getenv('LOGIN_LOCKOUT_SECONDS', '900'))


def _key_for(email):
    normalized = str(email).strip().lower()
    # Truncated: 96 bits is ample to avoid collisions and keeps the key short.
    digest = hashlib.sha256(normalized.encode('utf-8')).hexdigest()[:24]
    return f'login_fail:{SERVICE}:{digest}'


def get_lockout_remaining(email):
    """
    Seconds remaining on the lockout, or 0 when the account may attempt a login.
    Fails open — a Redis outage must not lock everyone out.
    """
    if ext.redis_client is None or not email:
        return 0
    try:
        key = _key_for(email)
        attempts = int(ext.redis_client.get(key) or 0)
        if attempts < MAX_ATTEMPTS:
            return 0

        ttl = ext.redis_client.ttl(key)
        return ttl if ttl and ttl > 0 else LOCKOUT_SECONDS
    except Exception as e:
        print(f'Login lockout check failed, allowing attempt: {e}')
        return 0


def record_failure(email):
    """
    Records a failed attempt. The TTL is set on the first failure and not extended
    afterwards, so the window is "N failures within LOCKOUT_SECONDS" rather than a
    lockout a persistent attacker can keep alive indefinitely.
    """
    if ext.redis_client is None or not email:
        return
    try:
        key = _key_for(email)
        attempts = ext.redis_client.incr(key)
        if attempts == 1:
            ext.redis_client.expire(key, LOCKOUT_SECONDS)
    except Exception as e:
        # Best effort — never block a login because the counter couldn't be written.
        print(f'Login failure counter write failed: {e}')


def reset_attempts(email):
    """Clears the counter after a successful login."""
    if ext.redis_client is None or not email:
        return
    try:
        ext.redis_client.delete(_key_for(email))
    except Exception:
        pass
