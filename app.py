from flask import Flask, jsonify, request
from flask_cors import CORS
import os
import hmac
import hashlib
import base64
import json
import time
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)

# JWT Utilities using standard libraries
def base64url_encode(data):
    if isinstance(data, str):
        data = data.encode('utf-8')
    encoded = base64.urlsafe_b64encode(data)
    return encoded.decode('utf-8').rstrip('=')

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

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({'status': 'OK'}), 200

@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({'error': 'invalid_request', 'error_description': 'Email and password are required.'}), 400

    if len(password) < 8:
        return jsonify({'error': 'invalid_request', 'error_description': 'Password must be at least 8 characters.'}), 400

    if email == 'admin@tetotoys.com' and password == 'password123':
        payload = {
            'sub': email,
            'email': email,
            'exp': int(time.time()) + 3600
        }
        secret = os.getenv('JWT_SECRET', 'SuperSecretKeyForTetoToysTokenAuth2026')
        token = generate_jwt(payload, secret)
        return jsonify({
            'access_token': token,
            'token_type': 'Bearer',
            'expires_in': 3600
        }), 200

    return jsonify({'error': 'invalid_grant', 'error_description': 'Invalid email or password.'}), 401

@app.route('/api/auth/logout', methods=['POST'])
def logout():
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.lower().startswith('bearer '):
        return jsonify({'error': 'unauthorized', 'error_description': 'Missing or invalid authorization header.'}), 401
    
    return jsonify({'message': 'Logged out successfully'}), 200

@app.route('/', methods=['GET'])
def root():
    return jsonify({'flask status': 'OK'}), 200

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(debug=True, port=port)
