#!/usr/bin/env python3
"""
OSINT Monitoring Dashboard
Military-grade RSS feed aggregator and intelligence monitoring system.
"""

import os
import json
import sqlite3
import hashlib
import secrets
from datetime import datetime, timedelta
from functools import wraps
from threading import Thread
import time

from flask import Flask, render_template, jsonify, request, session, Response
from flask_socketio import SocketIO, emit
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import feedparser
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Flask app configuration
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', secrets.token_hex(32))

# Rate limiting
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)

# SocketIO for real-time updates
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Configuration
ADMIN_USERNAME = os.getenv('ADMIN_USERNAME', 'admin')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'osint123')
REFRESH_INTERVAL = int(os.getenv('REFRESH_INTERVAL', '300'))  # 5 minutes
MAX_ARTICLES = int(os.getenv('MAX_ARTICLES', '1000'))
ENABLE_WEBSOCKET = os.getenv('ENABLE_WEBSOCKET', 'true').lower() == 'true'

# Database path
DB_PATH = os.path.join(os.path.dirname(__file__), 'osint.db')

# Default RSS feeds by category
DEFAULT_FEEDS = {
    "cybersecurity": [
        {"name": "The Hacker News", "url": "https://feeds.feedburner.com/TheHackersNews"},
        {"name": "Bleeping Computer", "url": "https://www.bleepingcomputer.com/feed/"},
        {"name": "Krebs on Security", "url": "https://krebsonsecurity.com/feed/"},
    ],
    "technology": [
        {"name": "TechCrunch", "url": "https://techcrunch.com/feed/"},
        {"name": "The Verge", "url": "https://www.theverge.com/rss/index.xml"},
        {"name": "Ars Technica", "url": "https://feeds.arstechnica.com/arstechnica/index"},
    ],
    "world": [
        {"name": "Reuters World", "url": "https://www.reuters.com/world/rss/"},
        {"name": "BBC World", "url": "https://feeds.bbci.co.uk/news/world/rss.xml"},
        {"name": "Al Jazeera", "url": "https://www.aljazeera.com/xml/rss/all.xml"},
    ],
    "business": [
        {"name": "Financial Times", "url": "https://www.ft.com/?format=rss"},
        {"name": "Wall Street Journal", "url": "https://feeds.a.dj.com/rss/WSJcomUSBusiness.xml"},
    ]
}

# In-memory cache for articles
articles_cache = []
feeds_status = {}


def init_db():
    """Initialize SQLite database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Articles table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS articles (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            link TEXT NOT NULL,
            summary TEXT,
            content TEXT,
            source TEXT NOT NULL,
            category TEXT NOT NULL,
            published TEXT NOT NULL,
            fetched_at TEXT NOT NULL
        )
    ''')
    
    # Feeds table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS feeds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            url TEXT NOT NULL UNIQUE,
            category TEXT NOT NULL,
            active INTEGER DEFAULT 1,
            last_fetch TEXT,
            error_count INTEGER DEFAULT 0
        )
    ''')
    
    # Search index
    cursor.execute('''
        CREATE VIRTUAL TABLE IF NOT EXISTS articles_search USING fts5(
            title, summary, content,
            content='articles',
            content_rowid='rowid'
        )
    ''')
    
    conn.commit()
    conn.close()
    
    # Initialize default feeds if none exist
    init_default_feeds()


def init_default_feeds():
    """Initialize default feeds if database is empty."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) FROM feeds')
    count = cursor.fetchone()[0]
    
    if count == 0:
        for category, feeds in DEFAULT_FEEDS.items():
            for feed in feeds:
                try:
                    cursor.execute('''
                        INSERT INTO feeds (name, url, category, active)
                        VALUES (?, ?, ?, 1)
                    ''', (feed['name'], feed['url'], category))
                except sqlite3.IntegrityError:
                    pass
        
        conn.commit()
    
    conn.close()


def login_required(f):
    """Decorator to require authentication."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'authenticated' not in session:
            return jsonify({'error': 'Authentication required'}), 401
        return f(*args, **kwargs)
    return decorated_function


def fetch_feed(feed_info):
    """Fetch and parse a single RSS feed."""
    try:
        parsed = feedparser.parse(feed_info['url'])
        
        if parsed.bozo:
            print(f"Warning parsing {feed_info['name']}: {parsed.bozo_exception}")
        
        articles = []
        for entry in parsed.entries[:20]:  # Limit to 20 most recent
            # Generate unique ID
            article_id = hashlib.md5(
                f"{entry.get('link', '')}{entry.get('title', '')}".encode()
            ).hexdigest()
            
            # Parse published date
            published = entry.get('published_parsed') or entry.get('updated_parsed')
            if published:
                published_str = datetime(*published[:6]).isoformat()
            else:
                published_str = datetime.now().isoformat()
            
            # Get summary/content
            summary = entry.get('summary', '')
            content = entry.get('content', [{}])[0].get('value', summary)
            
            # Clean HTML from summary
            if summary:
                soup = BeautifulSoup(summary, 'html.parser')
                summary = soup.get_text(separator=' ', strip=True)[:500]
            
            article = {
                'id': article_id,
                'title': entry.get('title', 'No Title'),
                'link': entry.get('link', ''),
                'summary': summary,
                'content': content,
                'source': feed_info['name'],
                'category': feed_info['category'],
                'published': published_str,
                'fetched_at': datetime.now().isoformat()
            }
            
            articles.append(article)
        
        # Update feed status
        feeds_status[feed_info['url']] = {
            'last_fetch': datetime.now().isoformat(),
            'article_count': len(articles),
            'status': 'ok'
        }
        
        return articles
        
    except Exception as e:
        print(f"Error fetching {feed_info['name']}: {e}")
        feeds_status[feed_info['url']] = {
            'last_fetch': datetime.now().isoformat(),
            'error': str(e),
            'status': 'error'
        }
        return []


def store_articles(articles):
    """Store articles in database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    new_count = 0
    for article in articles:
        try:
            cursor.execute('''
                INSERT INTO articles (id, title, link, summary, content, source, category, published, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                article['id'], article['title'], article['link'],
                article['summary'], article['content'], article['source'],
                article['category'], article['published'], article['fetched_at']
            ))
            new_count += 1
        except sqlite3.IntegrityError:
            # Article already exists
            pass
    
    conn.commit()
    conn.close()
    
    return new_count


def cleanup_old_articles():
    """Remove old articles to keep database size manageable."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Keep only MAX_ARTICLES most recent
    cursor.execute('''
        DELETE FROM articles WHERE id NOT IN (
            SELECT id FROM articles ORDER BY published DESC LIMIT ?
        )
    ''', (MAX_ARTICLES,))
    
    deleted = cursor.rowcount
    conn.commit()
    conn.close()
    
    return deleted


def fetch_all_feeds():
    """Fetch all active feeds."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('SELECT name, url, category FROM feeds WHERE active = 1')
    feeds = cursor.fetchall()
    conn.close()
    
    all_articles = []
    for name, url, category in feeds:
        feed_info = {'name': name, 'url': url, 'category': category}
        articles = fetch_feed(feed_info)
        all_articles.extend(articles)
    
    # Store new articles
    new_count = store_articles(all_articles)
    
    # Cleanup old articles
    cleanup_old_articles()
    
    print(f"Feed fetch complete: {new_count} new articles from {len(feeds)} feeds")
    
    # Emit update to connected clients
    if ENABLE_WEBSOCKET:
        socketio.emit('feed_update', {
            'new_count': new_count,
            'total_feeds': len(feeds),
            'timestamp': datetime.now().isoformat()
        })
    
    return new_count


def background_feed_fetcher():
    """Background thread to periodically fetch feeds."""
    while True:
        try:
            fetch_all_feeds()
        except Exception as e:
            print(f"Error in background fetcher: {e}")
        
        time.sleep(REFRESH_INTERVAL)


# Routes

@app.route('/')
def index():
    """Main dashboard page."""
    return render_template('index.html')


@app.route('/login', methods=['POST'])
@limiter.limit("5 per minute")
def login():
    """Authenticate user."""
    data = request.get_json() or {}
    username = data.get('username')
    password = data.get('password')
    
    if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
        session['authenticated'] = True
        return jsonify({'success': True, 'message': 'Authenticated'})
    
    return jsonify({'success': False, 'error': 'Invalid credentials'}), 401


@app.route('/logout', methods=['POST'])
def logout():
    """Logout user."""
    session.pop('authenticated', None)
    return jsonify({'success': True})


@app.route('/api/feeds')
@login_required
def get_feeds():
    """Get all configured feeds."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('SELECT name, url, category, active, last_fetch, error_count FROM feeds')
    feeds = cursor.fetchall()
    conn.close()
    
    return jsonify([{
        'name': f[0],
        'url': f[1],
        'category': f[2],
        'active': bool(f[3]),
        'last_fetch': f[4],
        'error_count': f[5]
    } for f in feeds])


@app.route('/api/articles')
@login_required
def get_articles():
    """Get articles with pagination and filtering."""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    category = request.args.get('category')
    source = request.args.get('source')
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Build query
    query = 'SELECT * FROM articles WHERE 1=1'
    params = []
    
    if category:
        query += ' AND category = ?'
        params.append(category)
    
    if source:
        query += ' AND source = ?'
        params.append(source)
    
    # Get total count
    count_query = query.replace('SELECT *', 'SELECT COUNT(*)')
    cursor.execute(count_query, params)
    total = cursor.fetchone()[0]
    
    # Get paginated results
    query += ' ORDER BY published DESC LIMIT ? OFFSET ?'
    params.extend([per_page, (page - 1) * per_page])
    
    cursor.execute(query, params)
    articles = cursor.fetchall()
    conn.close()
    
    return jsonify({
        'articles': [{
            'id': a[0],
            'title': a[1],
            'link': a[2],
            'summary': a[3],
            'source': a[5],
            'category': a[6],
            'published': a[7],
            'fetched_at': a[8]
        } for a in articles],
        'total': total,
        'page': page,
        'per_page': per_page,
        'pages': (total + per_page - 1) // per_page
    })


@app.route('/api/search', methods=['POST'])
@login_required
def search_articles():
    """Search articles."""
    data = request.get_json() or {}
    query = data.get('query', '')
    category = data.get('category')
    limit = data.get('limit', 20)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Simple search for now (could use FTS5 for better performance)
    sql = '''
        SELECT * FROM articles 
        WHERE (title LIKE ? OR summary LIKE ?)
    '''
    params = [f'%{query}%', f'%{query}%']
    
    if category:
        sql += ' AND category = ?'
        params.append(category)
    
    sql += ' ORDER BY published DESC LIMIT ?'
    params.append(limit)
    
    cursor.execute(sql, params)
    articles = cursor.fetchall()
    conn.close()
    
    return jsonify([{
        'id': a[0],
        'title': a[1],
        'link': a[2],
        'summary': a[3],
        'source': a[5],
        'category': a[6],
        'published': a[7]
    } for a in articles])


@app.route('/api/stats')
@login_required
def get_stats():
    """Get dashboard statistics."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Total articles
    cursor.execute('SELECT COUNT(*) FROM articles')
    total_articles = cursor.fetchone()[0]
    
    # Articles by category
    cursor.execute('SELECT category, COUNT(*) FROM articles GROUP BY category')
    by_category = dict(cursor.fetchall())
    
    # Recent articles (last 24 hours)
    yesterday = (datetime.now() - timedelta(days=1)).isoformat()
    cursor.execute('SELECT COUNT(*) FROM articles WHERE fetched_at > ?', (yesterday,))
    recent = cursor.fetchone()[0]
    
    # Active feeds
    cursor.execute('SELECT COUNT(*) FROM feeds WHERE active = 1')
    active_feeds = cursor.fetchone()[0]
    
    conn.close()
    
    return jsonify({
        'total_articles': total_articles,
        'by_category': by_category,
        'recent_24h': recent,
        'active_feeds': active_feeds,
        'feeds_status': feeds_status
    })


@app.route('/api/refresh', methods=['POST'])
@login_required
def refresh_feeds():
    """Manually trigger feed refresh."""
    new_count = fetch_all_feeds()
    return jsonify({
        'success': True,
        'new_articles': new_count,
        'timestamp': datetime.now().isoformat()
    })


@app.route('/api/export', methods=['POST'])
@login_required
def export_data():
    """Export articles to various formats."""
    data = request.get_json() or {}
    format_type = data.get('format', 'json')
    since = data.get('since', '24h')
    category = data.get('category')
    
    # Parse since parameter
    if since == '24h':
        cutoff = (datetime.now() - timedelta(days=1)).isoformat()
    elif since == '7d':
        cutoff = (datetime.now() - timedelta(days=7)).isoformat()
    elif since == '30d':
        cutoff = (datetime.now() - timedelta(days=30)).isoformat()
    else:
        cutoff = '1970-01-01'
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    query = 'SELECT * FROM articles WHERE fetched_at > ?'
    params = [cutoff]
    
    if category:
        query += ' AND category = ?'
        params.append(category)
    
    query += ' ORDER BY published DESC'
    
    cursor.execute(query, params)
    articles = cursor.fetchall()
    conn.close()
    
    article_data = [{
        'id': a[0],
        'title': a[1],
        'link': a[2],
        'summary': a[3],
        'source': a[5],
        'category': a[6],
        'published': a[7],
        'fetched_at': a[8]
    } for a in articles]
    
    if format_type == 'json':
        return jsonify(article_data)
    
    elif format_type == 'csv':
        import csv
        import io
        
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Title', 'Source', 'Category', 'Published', 'Link', 'Summary'])
        
        for article in article_data:
            writer.writerow([
                article['title'],
                article['source'],
                article['category'],
                article['published'],
                article['link'],
                article['summary']
            ])
        
        output.seek(0)
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': 'attachment; filename=osint_export.csv'}
        )
    
    return jsonify({'error': 'Unsupported format'}), 400


# WebSocket events

@socketio.on('connect')
def handle_connect():
    """Handle client connection."""
    print('Client connected')
    emit('connected', {'data': 'Connected to OSINT Dashboard'})


@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection."""
    print('Client disconnected')


@socketio.on('refresh_feeds')
def handle_refresh_feeds():
    """Handle manual feed refresh request."""
    new_count = fetch_all_feeds()
    emit('feed_update', {
        'new_count': new_count,
        'timestamp': datetime.now().isoformat()
    })


# Error handlers

@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Not found'}), 404


@app.errorhandler(500)
def server_error(e):
    return jsonify({'error': 'Internal server error'}), 500


# Initialize
init_db()

# Start background feed fetcher if not on Vercel (serverless)
if os.getenv('VERCEL') != '1':
    fetcher_thread = Thread(target=background_feed_fetcher, daemon=True)
    fetcher_thread.start()


# For Vercel serverless handler
if os.getenv('VERCEL') == '1':
    # Fetch feeds on cold start
    try:
        fetch_all_feeds()
    except:
        pass


if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)
