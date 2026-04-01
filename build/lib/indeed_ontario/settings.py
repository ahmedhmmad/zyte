# Scrapy settings for Indeed Ontario spider with Zyte API integration
# Designed for deployment to Zyte Scrapy Cloud

import os

BOT_NAME = "indeed_ontario"

SPIDER_MODULES = ["indeed_ontario.spiders"]
NEWSPIDER_MODULE = "indeed_ontario.spiders"

# Crawl responsibly — identify yourself (optional but recommended)
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# Obey robots.txt rules
ROBOTSTXT_OBEY = False  # Zyte API handles robots.txt compliance

# Configure maximum concurrent requests performed by Scrapy (default: 16)
CONCURRENT_REQUESTS = 16

# Configure a delay for requests for the same website (default: 0)
# Zyte API manages its own throttling and rate limiting, so we set this to 0
# to avoid unnecessary delays. Zyte's infrastructure handles request pacing.
DOWNLOAD_DELAY = 0

# Disable cookies (enabled by default)
COOKIES_ENABLED = True

# Disable Telnet Console (enabled by default)
TELNETCONSOLE_ENABLED = False

# Override the default request headers:
DEFAULT_REQUEST_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-CA,en-US;q=0.7,en;q=0.3",
}

# Enable or disable spider middlewares
SPIDER_MIDDLEWARES = {
    "scrapy.spidermiddlewares.offsite.OffsiteMiddleware": 500,
}

# Enable or disable downloader middlewares
DOWNLOADER_MIDDLEWARES = {
    "scrapy.downloadermiddlewares.useragent.UserAgentMiddleware": None,
    "scrapy.downloadermiddlewares.retry.RetryMiddleware": None,
    # Zyte API middleware for JavaScript rendering and anti-bot bypass
    "scrapy_zyte_api.ZyteApiRequestMiddleware": 543,
}

# Zyte API Configuration
# API key is automatically provided by Scrapy Cloud environment
ZYTE_API_KEY = os.environ.get("ZYTE_API_KEY")

# Enable browser HTML rendering for JavaScript-heavy pages
ZYTE_API_BROWSER_HTML = True

# Enable or disable extensions
EXTENSIONS = {
    "scrapy.extensions.telnet.TelnetConsole": None,
}

# Configure item pipelines
ITEM_PIPELINES = {
    "scrapy.pipelines.files.FilesPipeline": 1,
}

# Enable and configure the AutoThrottle extension (disabled by default)
AUTOTHROTTLE_ENABLED = False  # Zyte API handles throttling

# Maximum number of concurrent requests per domain
CONCURRENT_REQUESTS_PER_DOMAIN = 16

# Maximum number of concurrent requests per IP
CONCURRENT_REQUESTS_PER_IP = 16

# Zyte API Configuration
# API key is automatically provided by Scrapy Cloud environment
# ZYTE_API_KEY = os.environ.get("ZYTE_API_KEY")

# Zyte Scrapy Cloud automatically enables Zyte API
# No additional configuration needed for browser HTML rendering
ZYTE_API_BROWSER_HTML = True

# Zyte API request options (optional fine-tuning)
ZYTE_API_DEFAULT_OPTIONS = {
    "browserHtml": True,
    "javascript": True,
}

# Logging configuration
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s [%(name)s] %(levelname)s: %(message)s"

# Feed export configuration
# Scrapy Cloud uses default feed storage; this configures local development
FEEDS = {
    "items.jl": {
        "format": "jsonlines",
        "encoding": "utf-8",
        "indent": 0,  # Compact JSON for smaller file size
    },
}

# Retry configuration
RETRY_ENABLED = True
RETRY_TIMES = 3
RETRY_HTTP_CODES = [500, 502, 503, 504, 408, 429]

# Timeout for requests (seconds)
DOWNLOAD_TIMEOUT = 60
