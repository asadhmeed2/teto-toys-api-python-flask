import json
from flask import Blueprint, jsonify, request
from app.extensions import db

products_bp = Blueprint('products', __name__)

# ponytail: GET /products (public storefront endpoint)
@products_bp.route('/products', methods=['GET'])
def get_products():
    page = request.args.get('page', 1, type=int)
    page_size = request.args.get('pageSize', 10, type=int)
    search = request.args.get('search', '', type=str)

    if page < 1:
        page = 1
    if page_size < 1 or page_size > 100:
        page_size = 10

    offset = (page - 1) * page_size

    try:
        count_sql = "SELECT COUNT(1) AS count FROM products"
        items_sql = "SELECT product_id, title, subtitle, description, category, subcategory, price, image_urls FROM products"
        params = {}

        if search:
            count_sql += " WHERE title LIKE :search OR description LIKE :search"
            items_sql += " WHERE title LIKE :search OR description LIKE :search"
            params['search'] = f"%{search}%"

        items_sql += " ORDER BY created_at DESC LIMIT :limit OFFSET :offset"
        params['limit'] = page_size
        params['offset'] = offset

        total_count = db.session.execute(db.text(count_sql), params).scalar()

        rows = db.session.execute(db.text(items_sql), params).fetchall()

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
                'image_urls': urls
            })

        total_pages = (total_count + page_size - 1) // page_size if total_count > 0 else 0

        return jsonify({
            'items': items,
            'total_count': total_count,
            'page': page,
            'page_size': page_size,
            'total_pages': total_pages
        }), 200
    except Exception as e:
        return jsonify({'error': 'server_error', 'error_description': str(e)}), 500


# ponytail: GET /parts (public storefront endpoint)
@products_bp.route('/parts', methods=['GET'])
def get_parts():
    page = request.args.get('page', 1, type=int)
    page_size = request.args.get('pageSize', 10, type=int)
    search = request.args.get('search', '', type=str)

    if page < 1:
        page = 1
    if page_size < 1 or page_size > 100:
        page_size = 10

    offset = (page - 1) * page_size

    try:
        count_sql = "SELECT COUNT(1) AS count FROM parts"
        items_sql = "SELECT part_id, title, description, price, image_urls FROM parts"
        params = {}

        if search:
            count_sql += " WHERE title LIKE :search OR description LIKE :search"
            items_sql += " WHERE title LIKE :search OR description LIKE :search"
            params['search'] = f"%{search}%"

        items_sql += " ORDER BY created_at DESC LIMIT :limit OFFSET :offset"
        params['limit'] = page_size
        params['offset'] = offset

        total_count = db.session.execute(db.text(count_sql), params).scalar()

        rows = db.session.execute(db.text(items_sql), params).fetchall()

        items = []
        for row in rows:
            urls_raw = row[4]
            try:
                urls = json.loads(urls_raw) if urls_raw else []
            except Exception:
                urls = []

            items.append({
                'part_id': row[0],
                'title': row[1],
                'description': row[2],
                'price': float(row[3]),
                'image_urls': urls
            })

        total_pages = (total_count + page_size - 1) // page_size if total_count > 0 else 0

        return jsonify({
            'items': items,
            'total_count': total_count,
            'page': page,
            'page_size': page_size,
            'total_pages': total_pages
        }), 200
    except Exception as e:
        return jsonify({'error': 'server_error', 'error_description': str(e)}), 500


# ponytail: GET /categories (public storefront endpoint)
@products_bp.route('/categories', methods=['GET'])
def get_categories():
    try:
        items_sql = "SELECT id, name, slug FROM categories ORDER BY name ASC"
        rows = db.session.execute(db.text(items_sql)).fetchall()
        
        items = []
        for row in rows:
            items.append({
                'id': row[0],
                'name': row[1],
                'slug': row[2]
            })
            
        return jsonify(items), 200
    except Exception as e:
        return jsonify({'error': 'server_error', 'error_description': str(e)}), 500
