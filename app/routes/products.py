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
    category = request.args.get('category', 'All', type=str)
    lang = request.args.get('lang', 'en', type=str) or 'en'

    if page < 1:
        page = 1
    if page_size < 1 or page_size > 100:
        page_size = 10

    offset = (page - 1) * page_size

    try:
        # Double LEFT JOIN product_translations resolves requested-language text
        # with an 'en' fallback; the count query needs the same joins since the
        # search filter matches translated text.
        count_sql = (
            "SELECT COUNT(1) AS count FROM products p "
            "LEFT JOIN product_translations req ON req.product_id = p.product_id AND req.language_code = :language "
            "LEFT JOIN product_translations fb ON fb.product_id = p.product_id AND fb.language_code = 'en' "
            "WHERE p.is_deleted = 0 AND p.is_displayed = 1"
        )
        items_sql = (
            "SELECT p.product_id, "
            "COALESCE(req.title, fb.title) AS title, "
            "COALESCE(req.subtitle, fb.subtitle) AS subtitle, "
            "COALESCE(req.description, fb.description) AS description, "
            "p.category, p.subcategory, p.price, p.image_urls "
            "FROM products p "
            "LEFT JOIN product_translations req ON req.product_id = p.product_id AND req.language_code = :language "
            "LEFT JOIN product_translations fb ON fb.product_id = p.product_id AND fb.language_code = 'en' "
            "WHERE p.is_deleted = 0 AND p.is_displayed = 1"
        )
        params = {'language': lang}

        filter_by_category = False
        category_id = None
        if category and category.lower() != 'all':
            try:
                category_id = int(category)
                filter_by_category = True
            except ValueError:
                pass

        if filter_by_category:
            count_sql += " AND p.category = :category_id"
            items_sql += " AND p.category = :category_id"
            params['category_id'] = category_id

        if search:
            search_clause = " AND (COALESCE(req.title, fb.title) LIKE :search OR COALESCE(req.description, fb.description) LIKE :search)"
            count_sql += search_clause
            items_sql += search_clause
            params['search'] = f"%{search}%"

        items_sql += " ORDER BY p.created_at DESC LIMIT :limit OFFSET :offset"
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
    lang = request.args.get('lang', 'en', type=str) or 'en'

    if page < 1:
        page = 1
    if page_size < 1 or page_size > 100:
        page_size = 10

    offset = (page - 1) * page_size

    try:
        count_sql = (
            "SELECT COUNT(1) AS count FROM parts pa "
            "LEFT JOIN part_translations req ON req.part_id = pa.part_id AND req.language_code = :language "
            "LEFT JOIN part_translations fb ON fb.part_id = pa.part_id AND fb.language_code = 'en'"
        )
        items_sql = (
            "SELECT pa.part_id, "
            "COALESCE(req.title, fb.title) AS title, "
            "COALESCE(req.description, fb.description) AS description, "
            "pa.price, pa.image_urls "
            "FROM parts pa "
            "LEFT JOIN part_translations req ON req.part_id = pa.part_id AND req.language_code = :language "
            "LEFT JOIN part_translations fb ON fb.part_id = pa.part_id AND fb.language_code = 'en'"
        )
        params = {'language': lang}

        if search:
            search_clause = " WHERE (COALESCE(req.title, fb.title) LIKE :search OR COALESCE(req.description, fb.description) LIKE :search)"
            count_sql += search_clause
            items_sql += search_clause
            params['search'] = f"%{search}%"

        items_sql += " ORDER BY pa.created_at DESC LIMIT :limit OFFSET :offset"
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
    lang = request.args.get('lang', 'en', type=str) or 'en'
    try:
        items_sql = (
            "SELECT c.id, COALESCE(req.name, fb.name) AS name, c.slug "
            "FROM categories c "
            "LEFT JOIN category_translations req ON req.category_id = c.id AND req.language_code = :language "
            "LEFT JOIN category_translations fb ON fb.category_id = c.id AND fb.language_code = 'en' "
            "WHERE c.number_of_active_products > 0 "
            "ORDER BY name ASC"
        )
        rows = db.session.execute(db.text(items_sql), {'language': lang}).fetchall()

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
