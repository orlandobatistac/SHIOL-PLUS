# Nginx SSI Configuration for SHIOL+

## Overview

SHIOL+ uses **Server-Side Includes (SSI)** to implement reusable header and footer components across all HTML pages. This eliminates code duplication and ensures consistent UI across the platform.

## Architecture

### Component Files
```
frontend/includes/
├── header.html  (107 lines - Navigation + Auth section)
└── footer.html  (32 lines - Legal links + Copyright)
```

### Pages Using SSI
- `index.html` (main app)
- `about.html` 
- `privacy.html`
- `terms.html`
- `status.html`

Each page replaces ~150 lines of duplicated HTML with:
```html
<!--#include virtual="/includes/header.html" -->
<!--#include virtual="/includes/footer.html" -->
```

## Production Configuration

### 1. Enable SSI in Nginx

Edit your Nginx site configuration (usually `/etc/nginx/sites-available/shiolplus`):

```nginx
server {
    listen 80;
    server_name your-domain.com;
    
    root /path/to/SHIOL-PLUS/frontend;
    index index.html;

    # Enable SSI
    ssi on;
    ssi_silent_errors off;  # Show errors during development
    ssi_types text/html;

    location / {
        try_files $uri $uri/ =404;
    }

    # API proxy (if needed)
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### 2. Test Configuration

```bash
# Test Nginx config syntax
sudo nginx -t

# Reload Nginx
sudo systemctl reload nginx
```

### 3. Verify SSI is Working

```bash
# Check if includes are being processed
curl -I http://your-domain.com/ | grep "X-SSI"

# View source in browser - you should see the expanded HTML
# NOT the <!--#include--> directives
```

## Development Environment

### Local Testing (without Nginx)

SSI directives **won't work** when opening HTML files directly (`file:///`). You need a local server:

#### Option 1: Python HTTP Server
```bash
cd frontend
python3 -m http.server 8080
# Visit http://localhost:8080
```
⚠️ **Note**: Python's simple server doesn't support SSI. You'll see raw `<!--#include-->` comments.

#### Option 2: Local Nginx (Recommended)
```bash
# Install Nginx locally
sudo apt-get install nginx  # Ubuntu/Debian
brew install nginx          # macOS

# Create local config
sudo nano /etc/nginx/sites-available/shiolplus-dev

# Add configuration (see above)
# Point root to your local /workspaces/SHIOL-PLUS/frontend

# Enable site
sudo ln -s /etc/nginx/sites-available/shiolplus-dev /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

## Troubleshooting

### Issue: Includes not appearing

**Symptoms**: Page shows blank where header/footer should be

**Solutions**:
1. Check `ssi on;` is in server block
2. Verify file paths start with `/` (absolute from root)
3. Check file permissions: `chmod 644 frontend/includes/*.html`
4. Look for errors: `sudo tail -f /var/log/nginx/error.log`

### Issue: "File not found" errors

**Symptoms**: Nginx logs show "no such file or directory"

**Solutions**:
```bash
# Verify include files exist
ls -la /path/to/SHIOL-PLUS/frontend/includes/

# Check Nginx user has read permissions
sudo chown -R www-data:www-data /path/to/SHIOL-PLUS/frontend/includes/
```

### Issue: SSI not processing (showing raw HTML comments)

**Symptoms**: View source shows `<!--#include virtual="..."-->`

**Solutions**:
1. Ensure `ssi on;` is in correct block (server or location)
2. Check `ssi_types` includes `text/html`
3. File extension must be `.html` (not `.htm`)
4. Reload Nginx: `sudo systemctl reload nginx`

## GitHub Actions Auto-Deploy

No changes needed! GitHub Actions workflow will:
1. Pull latest code (including new `frontend/includes/` directory)
2. Restart services
3. Nginx will automatically use new SSI includes

## Benefits

### Before SSI
- **Total lines**: ~750 (150 lines × 5 pages)
- **Maintenance**: Update 5 files for menu/footer changes
- **Risk**: Inconsistent UI across pages

### After SSI
- **Total lines**: ~220 (140 include files + 5 lines × 5 pages)
- **Maintenance**: Update 1 file for changes
- **Risk**: Zero - single source of truth

**Reduction**: 71% less code to maintain

## Performance Impact

- **Negligible**: SSI processing happens once per request on server-side
- **No client-side overhead**: Browser receives fully-rendered HTML
- **Cacheable**: Nginx can cache processed pages with `proxy_cache`

## Future Improvements

If SSI becomes limiting, consider:
1. **Template engine**: Jinja2 (Python), Handlebars (Node.js)
2. **Build tools**: Webpack HTML plugins, Gulp
3. **Static site generator**: 11ty, Hugo
4. **Frontend framework**: React, Vue (if interactivity needed)

For now, SSI is the optimal choice for SHIOL+'s static content needs.

---

**Last Updated**: 2025-11-05  
**Author**: Orlando B.  
**Related**: See `.github/copilot-instructions.md` for full architecture
