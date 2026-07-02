from flask_sqlalchemy import SQLAlchemy

# Single SQLAlchemy instance — initialized in app.py via db.init_app(app)
db = SQLAlchemy()


class User(db.Model):
    """Maps to the `users` table created by the infrastructure SQL init script."""
    __tablename__ = 'users'

    user_id           = db.Column(db.String(36),  primary_key=True)
    email             = db.Column(db.String(255), unique=True, nullable=False)
    password_hash     = db.Column(db.String(255), nullable=False)
    first_name        = db.Column(db.String(100), nullable=False)
    last_name         = db.Column(db.String(100), nullable=False)
    is_adult          = db.Column(db.Boolean,     nullable=False, default=False)
    terms_accepted_at = db.Column(db.DateTime,    nullable=False)
    terms_version     = db.Column(db.String(50),  nullable=False)
    marketing_opt_in  = db.Column(db.Boolean,     default=False)
    created_at        = db.Column(db.DateTime,    default=db.func.current_timestamp())
    last_login        = db.Column(db.DateTime,    nullable=True)
    is_active         = db.Column(db.Boolean,     default=True)

    def to_dict(self):
        return {
            'user_id': self.user_id,
            'email': self.email,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'is_adult': self.is_adult,
            'terms_accepted_at': self.terms_accepted_at.isoformat() if self.terms_accepted_at else None,
            'terms_version': self.terms_version,
            'marketing_opt_in': self.marketing_opt_in,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
