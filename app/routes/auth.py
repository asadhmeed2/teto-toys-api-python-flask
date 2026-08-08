from flask import Blueprint, jsonify, request, make_response, current_app
import os
import re
import uuid
import jwt
import bcrypt
from datetime import datetime, timedelta, timezone
from app.extensions import db
from app.models.user import User
from app.services.email_service import send_password_reset_email

auth_bp = Blueprint('auth', __name__)

ISSUER = 'tatotoys-api'
AUDIENCE = 'tatotoys-frontend'
REFRESH_TOKEN_TTL = 7 * 24 * 60 * 60  # 7 days in seconds


def _secret():
    return current_app.config.get('JWT_SECRET', os.getenv('JWT_SECRET'))


def _redis():
    return current_app.extensions['redis']


def _generate_token(user_id, expire_delta, token_type='access', first_name=None, last_name=None, tz=None):
    payload = {
        'sub': user_id, 'role': 'User',
        'exp': datetime.now(timezone.utc) + expire_delta,
        'iss': ISSUER, 'aud': AUDIENCE,
    }
    if token_type == 'refresh':
        payload['token_type'] = 'refresh'
    if first_name:
        payload['firstName'] = first_name
    if last_name:
        payload['lastName'] = last_name
    if token_type == 'refresh' and tz:
        payload['timezone'] = tz
    return jwt.encode(payload, _secret(), algorithm='HS256')


def _set_refresh_cookie(resp, token):
    resp.set_cookie(
        'refresh_token', token, httponly=True, samesite='Strict',
        secure=current_app.config.get('ENV') == 'production',
        max_age=REFRESH_TOKEN_TTL, path='/',
    )


@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    email, password = data.get('email'), data.get('password')
    tz = data.get('timezone') or None

    if not email or not password:
        return jsonify({'error': 'invalid_request', 'error_description': 'Email and password are required.'}), 400
    if len(password) < 8:
        return jsonify({'error': 'invalid_request', 'error_description': 'Password must be at least 8 characters.'}), 400

    try:
        user = User.query.filter_by(email=email).first()
        if not user:
            return jsonify({'error': 'invalid_grant', 'error_description': 'Invalid email or password.'}), 401
        if not user.is_active:
            return jsonify({'error': 'invalid_grant', 'error_description': 'Account is deactivated.'}), 401
        if not bcrypt.checkpw(password.encode(), user.password_hash.encode()):
            return jsonify({'error': 'invalid_grant', 'error_description': 'Invalid email or password.'}), 401

        user.last_login = datetime.now(timezone.utc)
        db.session.commit()

        access_token = _generate_token(user.user_id, timedelta(minutes=15))
        refresh_token = _generate_token(user.user_id, timedelta(days=7), 'refresh', user.first_name, user.last_name, tz)
        _redis().setex(f'refresh:{refresh_token}', REFRESH_TOKEN_TTL, '1')

        resp = make_response(jsonify({'access_token': access_token, 'token_type': 'Bearer', 'expires_in': 900}), 200)
        _set_refresh_cookie(resp, refresh_token)
        return resp
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Login error: {e}')
        return jsonify({'error': 'server_error', 'error_description': 'An internal error occurred.'}), 500


@auth_bp.route('/refresh', methods=['POST'])
def refresh():
    refresh_token = request.cookies.get('refresh_token')
    if not refresh_token or not _redis().exists(f'refresh:{refresh_token}'):
        return jsonify({'error': 'invalid_token', 'error_description': 'Missing or invalid refresh token.'}), 401

    try:
        decoded = jwt.decode(refresh_token, _secret(), algorithms=['HS256'], audience=AUDIENCE, options={'verify_exp': False})
        user_id = decoded['sub']
    except Exception:
        return jsonify({'error': 'invalid_token', 'error_description': 'Malformed refresh token.'}), 401

    new_access = _generate_token(user_id, timedelta(minutes=15))

    return jsonify({'access_token': new_access, 'token_type': 'Bearer', 'expires_in': 900}), 200


@auth_bp.route('/logout', methods=['POST'])
def logout():
    refresh_token = request.cookies.get('refresh_token')
    if refresh_token:
        _redis().delete(f'refresh:{refresh_token}')
    resp = make_response(jsonify({'message': 'Logged out successfully'}), 200)
    resp.delete_cookie('refresh_token', path='/')
    return resp


@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json() or {}
    first_name = data.get('first_name', '').strip()
    last_name  = data.get('last_name', '').strip()
    email      = data.get('email', '').strip()
    password   = data.get('password', '')
    confirm    = data.get('confirm_password', '')
    is_adult   = data.get('is_adult', False)
    terms      = data.get('terms_accepted', False)
    marketing  = data.get('marketing_opt_in', False)

    if not all([first_name, last_name, email, password, confirm]):
        return jsonify({'error': 'invalid_request', 'error_description': 'All fields are required.'}), 400
    if not re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', email):
        return jsonify({'error': 'invalid_request', 'error_description': 'Please enter a valid email address.'}), 400
    if len(password) < 8:
        return jsonify({'error': 'invalid_request', 'error_description': 'Password must be at least 8 characters.'}), 400
    if password != confirm:
        return jsonify({'error': 'invalid_request', 'error_description': 'Passwords do not match.'}), 400
    if not is_adult:
        return jsonify({'error': 'invalid_request', 'error_description': 'You must confirm that you are 18 years or older.'}), 400
    if not terms:
        return jsonify({'error': 'invalid_request', 'error_description': 'You must accept the Terms of Service and Privacy Policy.'}), 400

    now = datetime.now(timezone.utc)
    user = User(
        user_id=str(uuid.uuid4()), email=email,
        password_hash=bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode(),
        first_name=first_name, last_name=last_name,
        is_adult=True, terms_accepted_at=now, terms_version='1.0',
        marketing_opt_in=bool(marketing), created_at=now,
    )
    try:
        db.session.add(user)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        if 'Duplicate entry' in str(e):
            return jsonify({'error': 'conflict', 'error_description': 'An account with this email already exists.'}), 409
        current_app.logger.error(f'Register error: {e}')
        return jsonify({'error': 'server_error', 'error_description': 'An internal error occurred.'}), 500

    return jsonify({'message': 'Account created successfully.', 'user': user.to_dict()}), 201


@auth_bp.route('/me', methods=['GET'])
def me():
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.lower().startswith('bearer '):
        return jsonify({'error': 'unauthorized', 'error_description': 'Missing or invalid Authorization header.'}), 401
    try:
        decoded = jwt.decode(auth_header[7:], _secret(), algorithms=['HS256'], issuer=ISSUER, audience=AUDIENCE)
    except jwt.ExpiredSignatureError:
        return jsonify({'error': 'unauthorized', 'error_description': 'Token has expired.'}), 401
    except Exception:
        return jsonify({'error': 'unauthorized', 'error_description': 'Token is invalid or expired.'}), 401

    # The refresh token carries first/last name — pull it from there for the full profile
    refresh_token = request.cookies.get('refresh_token')
    if refresh_token and _redis().exists(f'refresh:{refresh_token}'):
        try:
            refresh_decoded = jwt.decode(refresh_token, _secret(), algorithms=['HS256'], issuer=ISSUER, audience=AUDIENCE)
            return jsonify({
                'userId': refresh_decoded['sub'],
                'role': refresh_decoded.get('role', 'User'),
                'firstName': refresh_decoded.get('firstName', ''),
                'lastName': refresh_decoded.get('lastName', ''),
            }), 200
        except Exception:
            pass  # fall through to access-token-only info

    return jsonify({'userId': decoded['sub'], 'role': decoded.get('role', 'User'), 'firstName': '', 'lastName': ''}), 200


@auth_bp.route('/forgot-password', methods=['POST'])
def forgot_password():
    email = (request.get_json() or {}).get('email', '').strip()
    if not email:
        return jsonify({'error': 'invalid_request', 'error_description': 'Email is required.'}), 400

    try:
        user = User.query.filter_by(email=email).first()
        if user and user.is_active:
            token = uuid.uuid4().hex + uuid.uuid4().hex
            _redis().setex(f'reset:{token}', 15 * 60, user.user_id)
            reset_link = f"{current_app.config['FRONTEND_BASE_URL']}/reset-password?token={token}"
            send_password_reset_email(
                user.email, reset_link,
                current_app.config['RESEND_API_KEY'],
                current_app.config['RESEND_FROM_EMAIL'],
            )
        return jsonify({'message': 'If an account with that email exists, a password reset link has been sent.'}), 200
    except Exception as e:
        current_app.logger.error(f'ForgotPassword error: {e}')
        return jsonify({'error': 'server_error', 'error_description': 'An internal error occurred.'}), 500


@auth_bp.route('/reset-password', methods=['POST'])
def reset_password():
    data = request.get_json() or {}
    token    = data.get('token', '').strip()
    new_pw   = data.get('new_password', '')
    confirm  = data.get('confirm_password', '')

    if not token:
        return jsonify({'error': 'invalid_request', 'error_description': 'Token is required.'}), 400
    if not new_pw or len(new_pw) < 8:
        return jsonify({'error': 'invalid_request', 'error_description': 'Password must be at least 8 characters.'}), 400
    if new_pw != confirm:
        return jsonify({'error': 'invalid_request', 'error_description': 'Passwords do not match.'}), 400

    try:
        user_id = _redis().get(f'reset:{token}')
        if not user_id:
            return jsonify({'error': 'invalid_token', 'error_description': 'Reset token is invalid or has expired.'}), 400

        _redis().delete(f'reset:{token}')
        if isinstance(user_id, bytes):
            user_id = user_id.decode()

        user = User.query.filter_by(user_id=user_id).first()
        if not user:
            return jsonify({'error': 'not_found', 'error_description': 'User not found.'}), 404

        user.password_hash = bcrypt.hashpw(new_pw.encode(), bcrypt.gensalt(rounds=12)).decode()
        db.session.commit()
        return jsonify({'message': 'Password has been reset successfully.'}), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'ResetPassword error: {e}')
        return jsonify({'error': 'server_error', 'error_description': 'An internal error occurred.'}), 500
