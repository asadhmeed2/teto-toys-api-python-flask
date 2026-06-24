from flask import Flask, jsonify
from flask_cors import CORS
import os
from dotenv import load_dotenv
from auth import auth_bp

load_dotenv()

app = Flask(__name__)
CORS(app)

# Register Blueprints
app.register_blueprint(auth_bp, url_prefix='/api/auth')

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({'status': 'OK'}), 200

@app.route('/', methods=['GET'])
def root():
    return jsonify({'flask status': 'OK'}), 200

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(debug=True, port=port)
