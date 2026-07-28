import json
import os
from datetime import datetime, timedelta

from flask import Blueprint, jsonify

import app.extensions as ext
from app.extensions import db

try:
    from zoneinfo import ZoneInfo
except ImportError:  # Python < 3.9
    ZoneInfo = None

store_hours_bp = Blueprint('store_hours', __name__)

# Shared with the admin API (which deletes this key on save) and the other
# storefront backends. Keep the string identical across services.
CACHE_KEY = 'store_hours:all'
CACHE_TTL_SECONDS = 60 * 60  # 1 hour

STORE_TIMEZONE = os.getenv('STORE_TIMEZONE', 'Asia/Jerusalem')


def _format_time(value):
    """MySQL TIME comes back as timedelta (PyMySQL) or str; normalise to 'HH:MM'."""
    if isinstance(value, timedelta):
        total_minutes = int(value.total_seconds() // 60)
        return f'{total_minutes // 60:02d}:{total_minutes % 60:02d}'
    if isinstance(value, str):
        parts = value.split(':')
        if len(parts) >= 2:
            return f'{parts[0].zfill(2)}:{parts[1]}'
    return '00:00'


def _to_minutes(value):
    """'HH:MM' -> minutes since midnight, or None when unparseable."""
    if not isinstance(value, str):
        return None
    parts = value.strip().split(':')
    if len(parts) < 2:
        return None
    try:
        hours, minutes = int(parts[0]), int(parts[1])
    except ValueError:
        return None
    if not (0 <= hours <= 23 and 0 <= minutes <= 59):
        return None
    return hours * 60 + minutes


def _now_in_store_timezone():
    """Returns (day_of_week with Sunday=0, minutes since midnight, 'HH:MM', resolved)."""
    now = None
    resolved = False

    if ZoneInfo is not None:
        try:
            now = datetime.now(ZoneInfo(STORE_TIMEZONE))
            resolved = True
        except Exception as e:
            # Loud on purpose. Silently using server local time produces a WRONG
            # open/closed answer whenever the host isn't in the store's zone — e.g.
            # a UTC container reports "open" for hours after closing. Slim images may
            # ship no IANA database; the `tzdata` PyPI package supplies one.
            print(
                f"[store-hours] Timezone '{STORE_TIMEZONE}' could not be resolved ({e}). "
                'Falling back to server local time — open/closed WILL be wrong unless '
                'the host runs in that zone. Install the tzdata package to fix.'
            )
            now = None

    if now is None:
        now = datetime.now()

    # Python's weekday() is Monday=0; shift to Sunday=0 to match the DB.
    day_of_week = (now.weekday() + 1) % 7
    return day_of_week, now.hour * 60 + now.minute, now.strftime('%H:%M'), resolved


def _compute_is_open_now(days):
    day_of_week, minutes, label, resolved = _now_in_store_timezone()

    today = next((d for d in days if d['day_of_week'] == day_of_week), None)
    if today is None or today['is_closed']:
        return False, label, resolved

    open_min = _to_minutes(today['open_time'])
    close_min = _to_minutes(today['close_time'])
    if open_min is None or close_min is None:
        return False, label, resolved

    return open_min <= minutes < close_min, label, resolved


def _load_from_database():
    rows = db.session.execute(
        db.text(
            'SELECT day_of_week, open_time, close_time, is_closed '
            'FROM store_hours ORDER BY day_of_week ASC'
        )
    ).fetchall()

    return [
        {
            'day_of_week': int(r[0]),
            'open_time': _format_time(r[1]),
            'close_time': _format_time(r[2]),
            'is_closed': bool(r[3]),
        }
        for r in rows
    ]


# GET /api/store-hours — public: weekly schedule + whether the shop is open right now.
@store_hours_bp.route('/store-hours', methods=['GET'])
def get_store_hours():
    try:
        days = None

        # 1. Try the cache. Redis being down must not take the storefront with it.
        try:
            if ext.redis_client is not None:
                cached = ext.redis_client.get(CACHE_KEY)
                if cached:
                    days = json.loads(cached)
        except Exception as e:
            print(f'Store hours cache read failed: {e}')

        # 2. Cache miss — read through to MySQL and repopulate.
        if days is None:
            days = _load_from_database()
            try:
                if ext.redis_client is not None:
                    ext.redis_client.setex(CACHE_KEY, CACHE_TTL_SECONDS, json.dumps(days))
            except Exception as e:
                print(f'Store hours cache write failed: {e}')

        # 3. is_open_now is always computed fresh — never cached, or a stale "true"
        #    could outlive closing time by up to the full TTL.
        is_open_now, server_time, tz_resolved = _compute_is_open_now(days)

        return jsonify({
            'timezone': STORE_TIMEZONE,
            # False => the host lacks IANA tz data and the times below are
            # server-local, not store-local. Surfaced so it's visible without logs.
            'timezone_resolved': tz_resolved,
            'server_time': server_time,
            'is_open_now': is_open_now,
            'days': days,
        }), 200
    except Exception as e:
        return jsonify({'error': 'server_error', 'error_description': str(e)}), 500
