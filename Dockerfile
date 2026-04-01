FROM scrapinghub/scrapinghub-stack-scrapy:2.11

# Install scrapy-zyte-api for Zyte API integration
RUN pip install --no-cache-dir scrapy-zyte-api

# Copy and install the Scrapy project
COPY . /app
WORKDIR /app

# Set the Scrapy settings module
ENV SCRAPY_SETTINGS_MODULE=indeed_ontario.settings

# Install the project
RUN pip install --no-cache-dir -e .
