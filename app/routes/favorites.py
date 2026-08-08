import jwt
import os
from flask import Blueprint, jsonify, request, current_app
from app.extensions import db

favorites_bp = Blueprint('favorites', __name__)

ISSUER = 'tatotoys-api'
AUDIENCE = 'tatotoys-frontend'


def _secret():
    return current_app.config.get('JWT_SECRET', os.getenv('JWT_SECRET'))


def _extract_user_id():
    """Validate Bearer token and return user_id, or None on failure."""
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return None
    token = auth_header[7:]
    try:
        decoded = jwt.decode(
            token, _secret(), algorithms=['HS256'],
            issuer=ISSUER, audience=AUDIENCE,
        )
        return decoded.get('sub')
    except Exception:
        return None


# GET /favorites — list authenticated user's favourite products
@favorites_bp.route('/favorites', methods=['GET'])
def get_favorites():
    user_id = _extract_user_id()
    if not user_id:
        return jsonify({'error': 'unauthorized', 'error_description': 'Missing or invalid Authorization header.'}), 401

    try:
        sql = """
            SELECT p.product_id, p.title, p.subtitle, p.description,
                   p.category, p.subcategory, p.price, p.image_urls
            FROM favorites_products f
            JOIN products p ON p.product_id = f.product_id
            WHERE f.user_id = :user_id
              AND p.is_deleted = 0
              AND p.is_displayed = 1
            ORDER BY f.created_at DESC
        """
        rows = db.session.execute(db.text(sql), {'user_id': user_id}).fetchall()

        import json
        items = []
        for row in rows:
            urls_raw = row[7]
            try:
                urls = json.loads(urls_raw) if urls_raw else []
            except Exception:
                urls = []
            items.append({
                'product_id': row[0],
                'title': row[1],
                'subtitle': row[2],
                'description': row[3],
                'category': row[4],
                'subcategory': row[5],
                'price': float(row[6]),
                'image_urls': urls,
            })

        return jsonify({'items': items}), 200
    except Exception as e:
        return jsonify({'error': 'server_error', 'error_description': str(e)}), 500


# GET /favorites/ids — return only favourite product IDs
@favorites_bp.route('/favorites/ids', methods=['GET'])
def get_favorite_ids():
    user_id = _extract_user_id()
    if not user_id:
        return jsonify({'error': 'unauthorized', 'error_description': 'Missing or invalid Authorization header.'}), 401

    try:
        rows = db.session.execute(
            db.text('SELECT product_id FROM favorites_products WHERE user_id = :user_id'),
            {'user_id': user_id}
        ).fetchall()
        ids = [str(row[0]) for row in rows]
        return jsonify({'ids': ids}), 200
    except Exception as e:
        return jsonify({'error': 'server_error', 'error_description': str(e)}), 500


# POST /favorites/<product_id> — add product to favorites
@favorites_bp.route('/favorites/<product_id>', methods=['POST'])
def add_favorite(product_id):
    user_id = _extract_user_id()
    if not user_id:
        return jsonify({'error': 'unauthorized', 'error_description': 'Missing or invalid Authorization header.'}), 401

    try:
        count = db.session.execute(
            db.text('SELECT COUNT(1) FROM products WHERE product_id = :pid AND is_deleted = 0 AND is_displayed = 1'),
            {'pid': product_id}
        ).scalar()
        if not count:
            return jsonify({'error': 'not_found', 'error_description': 'Product not found.'}), 404

        db.session.execute(
            db.text('INSERT IGNORE INTO favorites_products (user_id, product_id) VALUES (:user_id, :pid)'),
            {'user_id': user_id, 'pid': product_id}
        )
        db.session.commit()
        return jsonify({'product_id': product_id, 'is_favorite': True}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'server_error', 'error_description': str(e)}), 500


# DELETE /favorites/<product_id> — remove product from favorites
@favorites_bp.route('/favorites/<product_id>', methods=['DELETE'])
def remove_favorite(product_id):
    user_id = _extract_user_id()
    if not user_id:
        return jsonify({'error': 'unauthorized', 'error_description': 'Missing or invalid Authorization header.'}), 401

    try:
        db.session.execute(
            db.text('DELETE FROM favorites_products WHERE user_id = :user_id AND product_id = :pid'),
            {'user_id': user_id, 'pid': product_id}
        )
        db.session.commit()
        return jsonify({'product_id': product_id, 'is_favorite': False}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'server_error', 'error_description': str(e)}), 500
