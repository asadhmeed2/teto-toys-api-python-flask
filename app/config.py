# ponytail: app-factory config — only what exists in .env today
import os


class Config:
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret')

    DB_HOST = os.getenv('DB_HOST', 'localhost')
    DB_PORT = os.getenv('DB_PORT', '3306')
    DB_USER = os.getenv('MYSQL_USER', 'TetoToys')
    DB_PASS = os.getenv('MYSQL_PASSWORD', 'YourSqlPassword')
    DB_NAME = os.getenv('MYSQL_DATABASE', 'TetoToys')
    SQLALCHEMY_DATABASE_URI = (
        f"mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    )

    REDIS_HOST = os.getenv('REDIS_HOST', '127.0.0.1')
    REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
    REDIS_PASSWORD = os.getenv('REDIS_PASSWORD') or None

    CORS_ORIGIN = os.getenv('CORS_ORIGIN', 'http://localhost:4200')
    FRONTEND_BASE_URL = os.getenv('FRONTEND_BASE_URL', 'http://localhost:4200')

    RESEND_API_KEY = os.getenv('RESEND_API_KEY', '')
    RESEND_FROM_EMAIL = os.getenv('RESEND_FROM_EMAIL', 'asadhmeed1@gmail.com')


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


configs = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig,
}
