import html

from flask import Blueprint, jsonify, request, current_app
from app.extensions import db

contact_bp = Blueprint('contact', __name__)


# POST /contact — save a contact form submission (public, no auth required)
@contact_bp.route('/contact', methods=['POST'])
def submit_contact():
    body = request.get_json(silent=True) or {}

    name    = (body.get('name') or '').strip()
    email   = (body.get('email') or '').strip()
    subject = (body.get('subject') or '').strip() or None
    message = (body.get('message') or '').strip()

    if not name or not email or not message:
        return jsonify({
            'error': 'validation_error',
            'error_description': 'name, email, and message are required.',
        }), 400

    # ponytail: HTML-encode free-text fields so a submitted <script> tag is stored
    # as inert text, protecting any future consumer (admin UI, email digest, etc.)
    # that renders these values, regardless of whether that consumer remembers to encode.
    name = html.escape(name)
    email = html.escape(email)
    subject = html.escape(subject) if subject else None
    message = html.escape(message)

    try:
        db.session.execute(
            db.text(
                'INSERT INTO contact_messages (name, email, subject, message) '
                'VALUES (:name, :email, :subject, :message)'
            ),
            {'name': name, 'email': email, 'subject': subject, 'message': message},
        )
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Thank you for reaching out! We will get back to you within 1–2 business days.',
        }), 201
    except Exception as e:
        db.session.rollback()
        # Log the detail, return a generic body: exception text leaks table
        # names, SQL fragments and stack context to the caller.
        current_app.logger.exception('Unhandled error: %s', e)
        return jsonify({'error': 'server_error', 'error_description': 'An internal error occurred.'}), 500
