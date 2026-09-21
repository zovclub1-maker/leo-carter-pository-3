"""
Leo Carter Poster Vault - PERMANENT DATABASE Backend
Fixed: Uses PostgreSQL for permanent storage (never deletes)
SQLite on Render free was deleting when server sleeps - this fixes it
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# PERMANENT DATABASE CONFIG - FIXED
# If DATABASE_URL exists (PostgreSQL), use it - PERMANENT
# If not, fallback to SQLite (temporary - will delete on sleep)
database_url = os.environ.get('DATABASE_URL')

if database_url:
    # Render PostgreSQL fix: postgres:// -> postgresql://
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    print(f"Using PERMANENT PostgreSQL database - posters will NEVER delete")
else:
    # Fallback SQLite - TEMPORARY (will delete when server sleeps)
    basedir = os.path.abspath(os.path.dirname(__file__))
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'leocarter.db')
    print(f"WARNING: Using SQLite - posters WILL DELETE when server sleeps! Add DATABASE_URL for permanent")

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class Poster(db.Model):
    id = db.Column(db.String(100), primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    short_title = db.Column(db.String(100))
    description = db.Column(db.Text)
    category = db.Column(db.String(100), nullable=False)
    type = db.Column(db.String(20), default='free')
    price = db.Column(db.Float, default=0)
    image_url = db.Column(db.Text, nullable=False)
    tags = db.Column(db.Text)
    downloads = db.Column(db.Integer, default=0)
    featured = db.Column(db.Boolean, default=False)
    created_by = db.Column(db.String(100), default='user')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'short_title': self.short_title,
            'description': self.description,
            'category': self.category,
            'type': self.type,
            'price': self.price,
            'image_url': self.image_url,
            'image': self.image_url,
            'tags': self.tags.split(',') if self.tags else [],
            'downloads': self.downloads,
            'featured': self.featured,
            'created_by': self.created_by,
            'created_at': self.created_at.isoformat() if self.created_at else ''
        }

with app.app_context():
    db.create_all()
    # Check if burger exists, if not create
    if not Poster.query.get('burger-fresh-best'):
        burger = Poster(
            id='burger-fresh-best',
            title='Fresh & Best Burger - Gourmet Cheeseburger Poster',
            short_title='Fresh Best Burger',
            description='Fresh and best Burger! Crispy Garlic Butter Shrimp style poster. Juicy beef patty with cheese, perfect for cafe restaurant.',
            category='Food & Restaurant',
            type='free',
            image_url='',
            tags='burger,food,restaurant,cafe',
            downloads=127,
            featured=True,
            created_by='admin'
        )
        db.session.add(burger)
        db.session.commit()
        print("Default burger poster created - permanent")

@app.route('/')
def home():
    return jsonify({
        'message': 'Leo Carter Poster Vault API - PERMANENT Database Active',
        'database_type': 'PostgreSQL (Permanent)' if database_url else 'SQLite (Temporary - WILL DELETE)',
        'total_posters': Poster.query.count(),
        'endpoints': {
            'GET /api/posters': 'Get all posters - permanent',
            'POST /api/posters': 'Add new poster - saves forever until admin deletes',
            'DELETE /api/posters/<id>': 'Delete poster - admin only',
        }
    })

@app.route('/api/posters', methods=['GET'])
def get_posters():
    category = request.args.get('category')
    search = request.args.get('search')
    query = Poster.query
    if category and category != 'All':
        query = query.filter_by(category=category)
    if search:
        query = query.filter(Poster.title.contains(search))
    posters = query.order_by(Poster.created_at.desc()).all()
    return jsonify([p.to_dict() for p in posters])

@app.route('/api/posters', methods=['POST'])
def add_poster():
    data = request.json
    if not data.get('title') or not data.get('image_url'):
        return jsonify({'error': 'Title and image_url required'}), 400
    
    import re
    poster_id = re.sub(r'[^a-z0-9]+', '-', data['title'].lower()).strip('-') + '-' + datetime.now().strftime('%Y%m%d%H%M%S')
    
    # Check if poster already exists with same title (avoid duplicates)
    existing = Poster.query.filter_by(title=data['title']).first()
    if existing:
        # Update existing instead of creating duplicate
        existing.description = data.get('description', existing.description)
        existing.category = data.get('category', existing.category)
        existing.type = data.get('type', existing.type)
        existing.price = data.get('price', existing.price)
        if data.get('image_url'):
            existing.image_url = data['image_url']
        existing.tags = ','.join(data.get('tags', [])) if isinstance(data.get('tags'), list) else data.get('tags', '')
        db.session.commit()
        return jsonify(existing.to_dict()), 200
    
    new_poster = Poster(
        id=poster_id,
        title=data['title'],
        short_title=data.get('short_title', data['title'][:30]),
        description=data.get('description', ''),
        category=data.get('category', 'General'),
        type=data.get('type', 'free'),
        price=data.get('price', 0),
        image_url=data['image_url'],
        tags=','.join(data.get('tags', [])) if isinstance(data.get('tags'), list) else data.get('tags', ''),
        created_by=data.get('created_by', 'user'),
        featured=data.get('featured', False)
    )
    db.session.add(new_poster)
    db.session.commit()
    return jsonify(new_poster.to_dict()), 201

@app.route('/api/posters/<poster_id>', methods=['DELETE'])
def delete_poster(poster_id):
    admin_key = request.headers.get('X-Admin-Key') or request.args.get('admin_key')
    expected_key = os.environ.get('ADMIN_KEY', 'LeoCarter_Ahmed_zov_1')
    if admin_key != expected_key:
        return jsonify({'error': 'Unauthorized - Wrong admin key'}), 403
    poster = Poster.query.get(poster_id)
    if not poster:
        return jsonify({'error': 'Poster not found'}), 404
    db.session.delete(poster)
    db.session.commit()
    return jsonify({'message': 'Poster deleted forever', 'id': poster_id})

@app.route('/api/posters/<poster_id>/download', methods=['POST'])
def increment_download(poster_id):
    poster = Poster.query.get(poster_id)
    if not poster:
        return jsonify({'error': 'Poster not found'}), 404
    poster.downloads += 1
    db.session.commit()
    return jsonify({'downloads': poster.downloads})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
