# Indeed Ontario Jobs Spider

Production-ready Scrapy spider for scraping software developer job listings from Indeed Canada (Ontario region), designed for deployment to Zyte Scrapy Cloud.

## Features

- **Zyte API Integration**: Uses Zyte Scrapy Cloud's built-in Zyte API for JavaScript rendering
- **Pagination**: Automatically paginates through all result pages until no "next" button exists
- **Deduplication**: Deduplicates job listings by `job_id` (Indeed's `data-jk` attribute)
- **Clean Output**: Yields flat dict items compatible with Scrapy Cloud feed export
- **Error Handling**: Graceful handling of request failures and missing data

## Project Structure

```
.
├── requirements.txt          # Python dependencies
├── scrapy.cfg                # Scrapy project configuration
├── setup.py                  # Package setup for Scrapy Cloud deployment
├── scrapinghub.yml           # Zyte Scrapy Cloud project config
├── README.md                 # This file
└── indeed_ontario/           # Main package
    ├── __init__.py           # Package marker
    ├── settings.py           # Scrapy settings with Zyte API config
    └── spiders/
        ├── __init__.py       # Spider package marker
        └── indeed_ontario.py # Main spider
```

## Prerequisites

- Python 3.9+
- Zyte Scrapy Cloud account
- Zyte API key (from [Zyte Dashboard](https://app.zyte.com/))

## Local Development

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Set Environment Variable

```bash
# Windows (PowerShell)
$env:ZYTE_API_KEY="your-api-key-here"

# Windows (CMD)
set ZYTE_API_KEY=your-api-key-here

# macOS/Linux
export ZYTE_API_KEY="your-api-key-here"
```

### 3. Run the Spider

```bash
scrapy crawl indeed_ontario -o items.jl
```

Output will be saved to `items.jl` in JSONL format.

## Deployment to Zyte Scrapy Cloud

### Step 1: Install shub

```bash
pip install shub
```

### Step 2: Login to Scrapy Cloud

```bash
shub login
```

Enter your Zyte API key when prompted.

### Step 3: Configure Environment Variable in Scrapy Cloud UI

1. Navigate to your project in [Scrapy Cloud](https://app.zyte.com/)
2. Go to **Settings** → **Environment**
3. Add a new environment variable:
   - **Name**: `ZYTE_API_KEY`
   - **Value**: Your Zyte API key
4. Click **Save**

> ⚠️ **Security Note**: Never commit your API key to version control. Always use Scrapy Cloud's environment variable feature.

### Step 4: Deploy the Spider

```bash
shub deploy
```

This uploads your spider code to Scrapy Cloud.

### Step 5: Schedule a Run

#### Option A: Via Web UI

1. Go to your project dashboard
2. Click **Spiders** → **indeed_ontario**
3. Click **Schedule** to run immediately or set a cron schedule

#### Option B: Via API

```bash
shub schedule indeed_ontario
```

Or use the [Scrapy Cloud API](https://docs.zyte.com/scrapy-cloud/api.html):

```bash
curl -X POST "https://dash.zyte.com/api/scrapyd/schedule.json" \
  -u YOUR_API_KEY: \
  -d project=YOUR_PROJECT_ID \
  -d spider=indeed_ontario
```

### Step 7: View Results

- **Items**: Navigate to **Jobs** → select your job → **Items** tab
- **Logs**: Navigate to **Jobs** → select your job → **Logs** tab
- **Download**: Click **Download** to export items as JSONL, CSV, or XML

## Output Schema

Each job listing yields the following fields:

| Field | Type | Description |
|-------|------|-------------|
| `job_id` | string | Indeed's unique job identifier (from `data-jk` attribute) |
| `job_title` | string | Position title |
| `company` | string | Company name |
| `location` | string | Job location (city, province) |
| `date_posted` | string | Relative posting time (e.g., "Just posted", "2 days ago") |
| `salary` | string\|null | Salary information if available, otherwise `null` |
| `job_url` | string | Absolute URL to the job posting |

### Example Output

```json
{"job_id": "a1b2c3d4e5f6g7h8", "job_title": "Software Developer", "company": "Tech Corp", "location": "Toronto, ON", "date_posted": "Just posted", "salary": "$80,000 - $100,000 a year", "job_url": "https://ca.indeed.com/viewjob?jk=a1b2c3d4e5f6g7h8"}
```

## Configuration Options

### Zyte API Settings

The spider uses the following Zyte API features:

- **AutoMap Mode** (`ZYTE_API_AUTOMAP = True`): Automatically handles request/response conversion
- **Browser HTML** (`ZYTE_API_BROWSER_HTML = True`): Renders JavaScript for dynamic content
- **JavaScript Enabled**: Ensures client-side rendered content is captured

### Throttling

`DOWNLOAD_DELAY` is set to `0` because Zyte API manages its own rate limiting and throttling. Additional delays would be redundant and slow down crawling unnecessarily.

### Concurrency

Default concurrency settings are optimized for Zyte's infrastructure:
- `CONCURRENT_REQUESTS = 16`
- `CONCURRENT_REQUESTS_PER_DOMAIN = 16`
- `CONCURRENT_REQUESTS_PER_IP = 16`

## Troubleshooting

### No Items Extracted

- Verify `ZYTE_API_KEY` is set correctly in Scrapy Cloud environment
- Check logs for selector mismatches (Indeed may have updated their DOM)
- Ensure the spider has permission to access the target URL

### Pagination Stops Early

- Check for CAPTCHA or blocking (Zyte API should handle this)
- Verify the next page selector matches Indeed's current pagination structure

### Duplicate Items

- Deduplication is per-crawl-session only
- To deduplicate across runs, implement a custom pipeline with persistent storage

## License

MIT License
