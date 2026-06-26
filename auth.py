from flask import Blueprint, jsonify, request, make_response
import os
import hmac
import hashlib
import base64
import json
import time

auth_bp = Blueprint('auth', __name__)

# In-memory refresh token store (resets on restart; swap for Redis/DB in production)
refresh_token_store = set()

# JWT Utilities using standard libraries
def base64url_encode(data):
    if isinstance(data, str):
        data = data.encode('utf-8')
    encoded = base64.urlsafe_b64encode(data)
    return encoded.decode('utf-8').rstrip('=')

def base64url_decode(data):
    padding = (4 - len(data) % 4) % 4
    return base64.urlsafe_b64decode(data + '=' * padding)

def generate_jwt(payload, secret):
    header = {"alg": "HS256", "typ": "JWT"}
    header_json = json.dumps(header, separators=(',', ':'))
    payload_json = json.dumps(payload, separators=(',', ':'))

    header_b64 = base64url_encode(header_json)
    payload_b64 = base64url_encode(payload_json)

    signing_input = f"{header_b64}.{payload_b64}"

    signature = hmac.new(
        secret.encode('utf-8'),
        signing_input.encode('utf-8'),
        hashlib.sha256
    ).digest()

    signature_b64 = base64url_encode(signature)
    return f"{signing_input}.{signature_b64}"

def get_secret():
    return os.getenv('JWT_SECRET', 'SuperSecretKeyForTetoToysTokenAuth2026')

def make_refresh_cookie_response(response_data, refresh_token, status=200):
    resp = make_response(jsonify(response_data), status)
    is_production = os.getenv('FLASK_ENV') == 'production'
    resp.set_cookie(
        'refresh_token',
        refresh_token,
        httponly=True,
        samesite='Strict',
        secure=is_production,
        max_age=7 * 24 * 60 * 60,  # 7 days in seconds
        path='/',
    )
    return resp

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({'error': 'invalid_request', 'error_description': 'Email and password are required.'}), 400

    if len(password) < 8:
        return jsonify({'error': 'invalid_request', 'error_description': 'Password must be at least 8 characters.'}), 400

    if email == 'admin@tetotoys.com' and password == 'password123':
        secret = get_secret()

        # Short-lived access token (15 minutes)
        access_payload = {
            'sub': email,
            'email': email,
            'exp': int(time.time()) + 15 * 60,
        }
        access_token = generate_jwt(access_payload, secret)

        # Long-lived refresh token (7 days)
        refresh_payload = {
            'sub': email,
            'email': email,
            'type': 'refresh',
            'exp': int(time.time()) + 7 * 24 * 60 * 60,
        }
        refresh_token = generate_jwt(refresh_payload, secret)
        refresh_token_store.add(refresh_token)

        return make_refresh_cookie_response(
            {'access_token': access_token, 'token_type': 'Bearer', 'expires_in': 900},
            refresh_token,
        )

    return jsonify({'error': 'invalid_grant', 'error_description': 'Invalid email or password.'}), 401

@auth_bp.route('/refresh', methods=['POST'])
def refresh():
    refresh_token = request.cookies.get('refresh_token')

    if not refresh_token or refresh_token not in refresh_token_store:
        return jsonify({'error': 'invalid_token', 'error_description': 'Missing or invalid refresh token.'}), 401

    # Rotate: invalidate old token
    refresh_token_store.discard(refresh_token)

    try:
        payload_part = refresh_token.split('.')[1]
        decoded = json.loads(base64url_decode(payload_part).decode('utf-8'))
        email = decoded['email']
    except Exception:
        return jsonify({'error': 'invalid_token', 'error_description': 'Malformed refresh token.'}), 401

    secret = get_secret()

    new_access_payload = {
        'sub': email,
        'email': email,
        'exp': int(time.time()) + 15 * 60,
    }
    new_access_token = generate_jwt(new_access_payload, secret)

    new_refresh_payload = {
        'sub': email,
        'email': email,
        'type': 'refresh',
        'exp': int(time.time()) + 7 * 24 * 60 * 60,
    }
    new_refresh_token = generate_jwt(new_refresh_payload, secret)
    refresh_token_store.add(new_refresh_token)

    return make_refresh_cookie_response(
        {'access_token': new_access_token, 'token_type': 'Bearer', 'expires_in': 900},
        new_refresh_token,
    )

@auth_bp.route('/logout', methods=['POST'])
def logout():
    refresh_token = request.cookies.get('refresh_token')
    if refresh_token:
        refresh_token_store.discard(refresh_token)

    resp = make_response(jsonify({'message': 'Logged out successfully'}), 200)
    resp.delete_cookie('refresh_token', path='/')
    return resp
