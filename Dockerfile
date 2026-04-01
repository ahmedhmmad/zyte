FROM scrapinghub/scrapinghub-stack-scrapy:2.11

# Install scrapy-zyte-api for Zyte API integration
RUN pip install --no-cache-dir scrapy-zyte-api

# Copy and install the Scrapy project
COPY . /app
WORKDIR /app
RUN pip install --no-cache-dir -e .
