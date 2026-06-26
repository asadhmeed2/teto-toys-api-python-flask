from flask import Flask, jsonify
from flask_cors import CORS
import os
from dotenv import load_dotenv
from auth import auth_bp

load_dotenv()

app = Flask(__name__)

CORS(app, supports_credentials=True, origins=[
    os.getenv('CORS_ORIGIN', 'http://localhost:4200')
])

# Register Blueprints
app.register_blueprint(auth_bp, url_prefix='/api/auth')

@app.route('/', methods=['GET'])
def root():
    return jsonify({'flask status': 'OK'}), 200

if __name__ == '__main__':
    port = int(os.getenv('PORT', 8000))
    app.run(host='0.0.0.0',debug=True, port=port)
