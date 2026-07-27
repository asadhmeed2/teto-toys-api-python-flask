import os
import redis as redis_lib
from flask import Flask, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from app.config import configs
from app.extensions import db
import app.extensions as ext


def create_app(env: str = None) -> Flask:
    load_dotenv()
    env = env or os.getenv('FLASK_ENV', 'development')
    app = Flask(__name__)
    app.config.from_object(configs.get(env, configs['default']))

    CORS(app, supports_credentials=True, origins=[app.config['CORS_ORIGIN']])

    # SQLAlchemy
    db.init_app(app)
    with app.app_context():
        try:
            with db.engine.connect() as conn:
                conn.execute(db.text('SELECT 1'))
            print('✅ MySQL connected')
        except Exception as e:
            print(f'❌ MySQL connection failed: {e}')

    # Redis
    pool = redis_lib.ConnectionPool(
        host=app.config['REDIS_HOST'],
        port=app.config['REDIS_PORT'],
        password=app.config['REDIS_PASSWORD'],
        socket_connect_timeout=5,
        socket_timeout=3,
        decode_responses=True,
    )
    ext.redis_client = redis_lib.Redis(connection_pool=pool)
    app.extensions['redis'] = ext.redis_client

    # Blueprints
    from app.routes.auth import auth_bp
    app.register_blueprint(auth_bp, url_prefix='/api/auth')

    from app.routes.products import products_bp
    app.register_blueprint(products_bp, url_prefix='/api')

    from app.routes.favorites import favorites_bp
    app.register_blueprint(favorites_bp, url_prefix='/api')

    from app.routes.contact import contact_bp
    app.register_blueprint(contact_bp, url_prefix='/api')

    from app.routes.store_hours import store_hours_bp
    app.register_blueprint(store_hours_bp, url_prefix='/api')

    @app.route('/', methods=['GET'])
    def root():
        return jsonify({'flask status': 'OK'}), 200

    return app
