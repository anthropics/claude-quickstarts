# OSINT Monitoring Dashboard

A military-grade open-source intelligence (OSINT) monitoring dashboard for real-time RSS feed aggregation, news tracking, and intelligence analysis. Built with Flask and designed for deployment on Vercel.

![License](https://img.shields.io/badge/license-MIT-green.svg)
![Python](https://img.shields.io/badge/python-3.8+-blue.svg)
![Flask](https://img.shields.io/badge/flask-2.0+-lightgrey.svg)

## Features

- **RSS Feed Aggregation**: Monitor multiple news sources in real-time
- **Military-Grade UI**: Dark theme interface designed for intelligence operations
- **Real-Time Monitoring**: Live updates with WebSocket support
- **Keyword Filtering**: Track specific topics, entities, or events
- **Source Management**: Add, remove, and categorize intelligence sources
- **Export Capabilities**: Save reports in multiple formats
- **Mobile Responsive**: Access intelligence on any device
- **Free Vercel Deployment**: Zero-cost hosting with serverless functions

## Quick Start

### Local Development

1. **Install Dependencies**
```bash
cd osint-dashboard
pip install -r requirements.txt
```

2. **Configure Environment**
```bash
cp .env.example .env
# Edit .env with your configuration
```

3. **Run the Application**
```bash
python app.py
```

4. **Open Dashboard**
Navigate to `http://localhost:5000`

### Default Login
- Username: `admin`
- Password: `osint123`

*(Change these in production!)*

## Deployment on Vercel

### One-Click Deploy

[![Deploy with Vercel](https://vercel.com/button)](https://vercel.com/new/clone?repository-url=https://github.com/anthropics/claude-quickstarts/tree/main/osint-dashboard)

### Manual Deployment

1. **Install Vercel CLI**
```bash
npm i -g vercel
```

2. **Deploy**
```bash
vercel --prod
```

The included `vercel.json` handles all configuration automatically.

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SECRET_KEY` | Flask secret key | Random generated |
| `ADMIN_USERNAME` | Dashboard admin username | `admin` |
| `ADMIN_PASSWORD` | Dashboard admin password | `osint123` |
| `REFRESH_INTERVAL` | Feed refresh interval (seconds) | `300` |
| `MAX_ARTICLES` | Maximum articles to store | `1000` |
| `ENABLE_WEBSOCKET` | Enable real-time updates | `true` |

### Adding RSS Feeds

Edit the `FEEDS` configuration in `app.py`:

```python
FEEDS = {
    "cybersecurity": [
        "https://feeds.feedburner.com/TheHackersNews",
        "https://www.bleepingcomputer.com/feed/"
    ],
    "geopolitics": [
        "https://www.reuters.com/rss/news",
        "https://feeds.bbci.co.uk/news/world/rss.xml"
    ],
    "technology": [
        "https://techcrunch.com/feed/",
        "https://www.theverge.com/rss/index.xml"
    ]
}
```

## Dashboard Interface

### Main Views

1. **Live Feed**: Real-time streaming of all sources
2. **By Category**: Filtered views by topic/domain
3. **Search**: Full-text search across all articles
4. **Analytics**: Charts and statistics
5. **Settings**: Manage sources and preferences

### Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `R` | Refresh feeds |
| `F` | Focus search |
| `C` | Clear filters |
| `1-5` | Switch categories |
| `ESC` | Close modals |

## API Endpoints

### REST API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/feeds` | GET | List all feeds |
| `/api/articles` | GET | Get articles (paginated) |
| `/api/articles/<id>` | GET | Get specific article |
| `/api/search` | POST | Search articles |
| `/api/stats` | GET | Dashboard statistics |
| `/api/export` | POST | Export data |

### WebSocket Events

| Event | Direction | Description |
|-------|-----------|-------------|
| `connect` | Incoming | Client connects |
| `new_article` | Outgoing | New article published |
| `refresh_feeds` | Incoming | Request feed refresh |

## Example Usage

### Fetch Latest Articles

```bash
curl http://localhost:5000/api/articles?limit=10
```

### Search Articles

```bash
curl -X POST http://localhost:5000/api/search \
  -H "Content-Type: application/json" \
  -d '{"query": "cybersecurity", "category": "tech"}'
```

### Export Report

```bash
curl -X POST http://localhost:5000/api/export \
  -H "Content-Type: application/json" \
  -d '{"format": "json", "since": "24h"}' \
  --output report.json
```

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   Client    │────▶│ Flask Server │────▶│  RSS Feeds  │
│  (Browser)  │◄────│   (Python)   │◄────│  (Sources)  │
└─────────────┘     └──────────────┘     └─────────────┘
                           │
                    ┌──────┴──────┐
                    ▼             ▼
              ┌─────────┐   ┌──────────┐
              │ SQLite  │   │ WebSocket│
              │ (Cache) │   │ (Realtime)│
              └─────────┘   └──────────┘
```

### Components

- **Flask Backend**: REST API and WebSocket server
- **Feed Parser**: RSS/Atom feed aggregation
- **Article Store**: SQLite database for caching
- **Real-time Engine**: Socket.IO for live updates
- **Military UI**: Custom CSS with dark theme

## Customization

### Theming

Modify CSS variables in `static/css/style.css`:

```css
:root {
  --bg-primary: #0a0a0a;
  --bg-secondary: #1a1a1a;
  --accent-color: #00ff88;
  --alert-color: #ff4444;
  --text-primary: #ffffff;
}
```

### Adding Widgets

1. Create widget HTML in `templates/widgets/`
2. Add JavaScript handler in `static/js/dashboard.js`
3. Register in Flask routes

## Security Considerations

- Change default credentials immediately
- Use HTTPS in production
- Implement rate limiting for API endpoints
- Consider authentication for sensitive feeds
- Regular security updates for dependencies

## Monitoring Use Cases

### Cybersecurity
- Track vulnerability disclosures
- Monitor threat actor activity
- Follow security advisories

### Geopolitical Intelligence
- News aggregation by region
- Conflict monitoring
- Policy change tracking

### Brand Monitoring
- Company mentions
- Competitor analysis
- Sentiment tracking

### Research
- Academic paper alerts
- Patent filings
- Industry reports

## Troubleshooting

### Feeds Not Updating
- Check feed URLs are valid
- Verify network connectivity
- Check `REFRESH_INTERVAL` setting

### WebSocket Connection Failed
- Ensure `ENABLE_WEBSOCKET=true`
- Check firewall settings
- Verify WebSocket support on hosting platform

### Memory Issues
- Reduce `MAX_ARTICLES` limit
- Enable article pruning
- Check SQLite database size

## Contributing

Contributions welcome! Areas for improvement:
- Additional feed parsers (Twitter, Reddit APIs)
- Machine learning for article categorization
- Advanced analytics and visualization
- Multi-user support with roles

## License

MIT License - See LICENSE file for details

## Resources

- [Flask Documentation](https://flask.palletsprojects.com/)
- [Vercel Python Runtime](https://vercel.com/docs/runtimes/python)
- [RSS Specification](https://www.rssboard.org/rss-specification)
- [OpenClaw Documentation](https://docs.openclaw.io)

---

**⚠️ Disclaimer**: This tool is for legitimate intelligence gathering and research purposes. Always comply with applicable laws and terms of service.
