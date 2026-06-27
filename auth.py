from flask import Blueprint, jsonify, request, make_response, current_app
import os
import jwt
from datetime import datetime, timedelta, timezone

auth_bp = Blueprint('auth', __name__)

ISSUER = 'tatotoys-api'
AUDIENCE = 'tatotoys-frontend'
REFRESH_TOKEN_TTL = 7 * 24 * 60 * 60  # 7 days in seconds

def get_secret():
    return os.getenv('JWT_SECRET', 'SuperSecretKeyForTetoToysTokenAuth2026')

def get_redis():
    return current_app.extensions['redis']

def generate_token(email, expire_delta, token_type='access'):
    payload = {
        'sub': email,
        'email': email,
        'role': 'User',
        'exp': datetime.now(timezone.utc) + expire_delta,
        'iss': ISSUER,
        'aud': AUDIENCE,
    }

    if token_type == 'refresh':
        payload['token_type'] = 'refresh'

    return jwt.encode(payload, get_secret(), algorithm='HS256')

def make_refresh_cookie_response(response_data, refresh_token, status=200):
    resp = make_response(jsonify(response_data), status)
    is_production = os.getenv('FLASK_ENV') == 'production'
    resp.set_cookie(
        'refresh_token',
        refresh_token,
        httponly=True,
        samesite='Strict',
        secure=is_production,
        max_age=REFRESH_TOKEN_TTL,
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
        access_token = generate_token(email, timedelta(minutes=15))
        refresh_token = generate_token(email, timedelta(days=7), token_type='refresh')

        # Store refresh token in Redis with 7-day TTL
        get_redis().setex(f'refresh:{refresh_token}', REFRESH_TOKEN_TTL, '1')

        return make_refresh_cookie_response(
            {'access_token': access_token, 'token_type': 'Bearer', 'expires_in': 900},
            refresh_token,
        )

    return jsonify({'error': 'invalid_grant', 'error_description': 'Invalid email or password.'}), 401

@auth_bp.route('/refresh', methods=['POST'])
def refresh():
    refresh_token = request.cookies.get('refresh_token')

    if not refresh_token or not get_redis().exists(f'refresh:{refresh_token}'):
        return jsonify({'error': 'invalid_token', 'error_description': 'Missing or invalid refresh token.'}), 401

    # Rotate: invalidate old token
    get_redis().delete(f'refresh:{refresh_token}')

    try:
        # Token already validated via Redis — decode without verifying expiry
        decoded = jwt.decode(
            refresh_token,
            get_secret(),
            algorithms=['HS256'],
            audience=AUDIENCE,
            options={'verify_exp': False},
        )
        email = decoded['email']
    except Exception:
        return jsonify({'error': 'invalid_token', 'error_description': 'Malformed refresh token.'}), 401

    new_access_token = generate_token(email, timedelta(minutes=15))
    new_refresh_token = generate_token(email, timedelta(days=7), token_type='refresh')

    get_redis().setex(f'refresh:{new_refresh_token}', REFRESH_TOKEN_TTL, '1')

    return make_refresh_cookie_response(
        {'access_token': new_access_token, 'token_type': 'Bearer', 'expires_in': 900},
        new_refresh_token,
    )

@auth_bp.route('/logout', methods=['POST'])
def logout():
    refresh_token = request.cookies.get('refresh_token')
    if refresh_token:
        get_redis().delete(f'refresh:{refresh_token}')

    resp = make_response(jsonify({'message': 'Logged out successfully'}), 200)
    resp.delete_cookie('refresh_token', path='/')
    return resp

@auth_bp.route('/me', methods=['GET'])
def me():
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.lower().startswith('bearer '):
        return jsonify({'error': 'unauthorized', 'error_description': 'Missing or invalid Authorization header.'}), 401

    token = auth_header[7:]
    try:
        decoded = jwt.decode(
            token,
            get_secret(),
            algorithms=['HS256'],
            issuer=ISSUER,
            audience=AUDIENCE,
        )
        return jsonify({'email': decoded['email'], 'role': decoded.get('role', 'User')}), 200
    except jwt.ExpiredSignatureError:
        return jsonify({'error': 'unauthorized', 'error_description': 'Token has expired.'}), 401
    except Exception:
        return jsonify({'error': 'unauthorized', 'error_description': 'Token is invalid or expired.'}), 401
