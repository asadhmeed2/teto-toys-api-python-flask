from flask import Flask, jsonify
from flask_cors import CORS
import os
import redis
from dotenv import load_dotenv
from services.db import db
from auth import auth_bp

load_dotenv()

app = Flask(__name__)

CORS(app, supports_credentials=True, origins=[
    os.getenv('CORS_ORIGIN', 'http://localhost:4200')
])

# --- MySQL via SQLAlchemy ---
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = os.getenv('DB_PORT', '3306')
DB_USER = os.getenv('MYSQL_USER', 'TetoToys')
DB_PASS = os.getenv('MYSQL_PASSWORD', 'YourSqlPassword123!')
DB_NAME = os.getenv('MYSQL_DATABASE', 'TetoToys')

app.config['SQLALCHEMY_DATABASE_URI'] = f"mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

# Test the MySQL connection at startup
with app.app_context():
    try:
        with db.engine.connect() as conn:
            conn.execute(db.text('SELECT 1'))
        print('✅ Successfully connected to MySQL from Flask!')
    except Exception as e:
        print(f'❌ MySQL connection failed: {e}')

# --- Redis ---
redis_pool = redis.ConnectionPool(
    host=os.getenv('REDIS_HOST', '127.0.0.1'),
    port=int(os.getenv('REDIS_PORT', 6379)),
    password=os.getenv('REDIS_PASSWORD') or None,
    socket_connect_timeout=5,
    socket_timeout=3,
    decode_responses=True,
)
redis_client = redis.Redis(connection_pool=redis_pool)

# Make redis_client available to blueprints via app context
app.extensions['redis'] = redis_client

# Register Blueprints
app.register_blueprint(auth_bp, url_prefix='/api/auth')

@app.route('/', methods=['GET'])
def root():
    return jsonify({'flask status': 'OK'}), 200

if __name__ == '__main__':
    port = int(os.getenv('PORT', 8000))
    app.run(host='0.0.0.0', debug=True, port=port)
