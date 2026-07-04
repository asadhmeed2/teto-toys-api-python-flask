import redis
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
redis_client: redis.Redis = None  # assigned in create_app()
