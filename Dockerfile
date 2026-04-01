FROM scrapinghub/scrapinghub-stack-scrapy:2.11

# Install scrapy-zyte-api for Zyte API integration
RUN pip install --no-cache-dir --system scrapy-zyte-api
