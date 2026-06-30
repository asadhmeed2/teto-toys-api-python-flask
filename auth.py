from flask import Blueprint, jsonify, request, make_response, current_app
import os
import re
import uuid
import jwt
import bcrypt
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

@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json() or {}
    first_name = data.get('first_name', '').strip()
    last_name = data.get('last_name', '').strip()
    email = data.get('email', '').strip()
    password = data.get('password', '')
    confirm_password = data.get('confirm_password', '')
    is_adult = data.get('is_adult', False)
    terms_accepted = data.get('terms_accepted', False)
    marketing_opt_in = data.get('marketing_opt_in', False)

    # --- Required field checks ---
    if not first_name or not last_name or not email or not password or not confirm_password:
        return jsonify({'error': 'invalid_request', 'error_description': 'All fields are required.'}), 400

    # --- Email format validation ---
    email_regex = r'^[^\s@]+@[^\s@]+\.[^\s@]+$'
    if not re.match(email_regex, email):
        return jsonify({'error': 'invalid_request', 'error_description': 'Please enter a valid email address.'}), 400

    # --- Password strength ---
    if len(password) < 8:
        return jsonify({'error': 'invalid_request', 'error_description': 'Password must be at least 8 characters.'}), 400

    # --- Passwords match ---
    if password != confirm_password:
        return jsonify({'error': 'invalid_request', 'error_description': 'Passwords do not match.'}), 400

    # --- Compliance checks ---
    if not is_adult:
        return jsonify({'error': 'invalid_request', 'error_description': 'You must confirm that you are 18 years or older.'}), 400

    if not terms_accepted:
        return jsonify({'error': 'invalid_request', 'error_description': 'You must accept the Terms of Service and Privacy Policy.'}), 400

    # --- Hash password ---
    password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt(rounds=12)).decode('utf-8')

    # --- Stub response (no DB yet) ---
    user_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    return jsonify({
        'message': 'Account created successfully.',
        'user': {
            'user_id': user_id,
            'email': email,
            'first_name': first_name,
            'last_name': last_name,
            'is_adult': True,
            'terms_accepted_at': now,
            'terms_version': '1.0',
            'marketing_opt_in': bool(marketing_opt_in),
            'created_at': now,
        },
    }), 201

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
