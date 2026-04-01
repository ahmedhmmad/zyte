"""
Indeed Ontario Job Listings Spider

Scrapes software developer job listings from Indeed Canada (Ontario region).
Designed for deployment to Zyte Scrapy Cloud with Zyte API integration.

Selector Strategy (Indeed DOM structure as of mid-2024):
- Job cards: div[data-jk] or li[data-jk] containing job details
- Job ID: data-jk attribute on the job card element
- Job title: .jobTitle span (contains the actual title text)
- Company: .companyName
- Location: .companyLocation
- Date posted: .date (relative time like "Just posted", "2 days ago")
- Salary: .salary-snippet-container or .salary-snippet (may be absent)
- Next page: a[data-testid="pagination-page-next"] or .pagination next link
"""

import hashlib
from typing import Any, Dict, Iterator, Optional, Set, Union

import scrapy
from scrapy.http import Response


class IndeedOntarioSpider(scrapy.Spider):
    """
    Spider for scraping Indeed Canada job listings for software developers in Ontario.

    Features:
    - Paginates through all available result pages
    - Deduplicates listings by job_id (Indeed's data-jk attribute)
    - Handles missing salary information gracefully
    - Yields clean dict items compatible with Scrapy Cloud feed export
    """

    name = "indeed_ontario"
    allowed_domains = ["ca.indeed.com"]

    # Base search URL for software developer jobs in Ontario, sorted by date
    start_url = (
        "https://ca.indeed.com/jobs?q=software+developer&l=Ontario&sort=date"
    )

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        # Track seen job_ids for deduplication within a single crawl session
        self._seen_job_ids: Set[str] = set()

    def start_requests(self) -> Iterator[scrapy.Request]:
        """
        Generate initial request with Zyte API browser automation.
        Uses zyte_api meta to enable Zyte's browser rendering.
        """
        yield scrapy.Request(
            url=self.start_url,
            callback=self.parse,
            errback=self.handle_error,
            meta={
                "zyte_api": {
                    "browserHtml": True,
                }
            },
        )

    def parse(self, response: Response) -> Iterator[Union[scrapy.Request, Dict[str, Any]]]:
        """
        Parse job listings from the search results page.

        Yields:
            - Job item dicts for each listing
            - Follow-up requests for pagination
        """
        # Select all job cards using data-jk attribute
        # Indeed uses this attribute to uniquely identify each job
        job_cards = response.css("div[data-jk], li[data-jk]")

        self.logger.info(f"Found {len(job_cards)} job cards on page")

        for job_card in job_cards:
            item = self._extract_job_item(job_card, response)
            if item is not None:
                yield item

        # Handle pagination — find and follow the "next" page link
        next_page_url = self._extract_next_page_url(response)
        if next_page_url:
            self.logger.info(f"Following pagination to: {next_page_url}")
            yield scrapy.Request(
                url=next_page_url,
                callback=self.parse,
                errback=self.handle_error,
                meta={
                    "zyte_api": {
                        "browserHtml": True,
                    }
                },
            )
        else:
            self.logger.info("No more pages to paginate — crawl complete")

    def _extract_job_item(
        self, job_card: scrapy.Selector, response: Response
    ) -> Optional[Dict[str, Any]]:
        """
        Extract job details from a single job card element.

        Args:
            job_card: Selector for the job card element
            response: Parent response for URL construction

        Returns:
            Dict with job details, or None if job_id is duplicate/missing
        """
        # Extract job_id from data-jk attribute (primary key for deduplication)
        job_id = job_card.attrib.get("data-jk")
        if not job_id:
            self.logger.warning("Job card missing data-jk attribute, skipping")
            return None

        # Deduplicate by job_id within this crawl session
        if job_id in self._seen_job_ids:
            self.logger.debug(f"Duplicate job_id {job_id}, skipping")
            return None
        self._seen_job_ids.add(job_id)

        # Extract job title — Indeed nests the title in a span within .jobTitle
        job_title_selector = job_card.css(".jobTitle span::text")
        job_title = job_title_selector.get(default="").strip()
        # Fallback: if no span, try direct text from .jobTitle
        if not job_title:
            job_title = job_card.css(".jobTitle::text").get(default="").strip()

        # Extract company name
        company = job_card.css(".companyName::text").get(default="").strip()

        # Extract location
        location = job_card.css(".companyLocation::text").get(default="").strip()

        # Extract date posted (relative time like "Just posted", "2 days ago")
        date_posted = job_card.css(".date::text").get(default="").strip()

        # Extract salary — may be absent for many listings
        # Indeed uses .salary-snippet-container or .salary-snippet
        salary_selector = (
            job_card.css(".salary-snippet-container .salary-snippet::text")
            or job_card.css(".salary-snippet::text")
        )
        salary_raw = salary_selector.get(default="")
        salary = salary_raw.strip() if salary_raw.strip() else None

        # Extract job URL — construct from job_id or extract from anchor
        job_url = self._extract_job_url(job_card, job_id, response)

        # Build clean item dict (no nested objects for Scrapy Cloud compatibility)
        item = {
            "job_id": job_id,
            "job_title": job_title,
            "company": company,
            "location": location,
            "date_posted": date_posted,
            "salary": salary,
            "job_url": job_url,
        }

        self.logger.debug(f"Extracted job: {job_title} at {company}")
        return item

    def _extract_job_url(
        self, job_card: scrapy.Selector, job_id: str, response: Response
    ) -> str:
        """
        Extract or construct the job URL.

        Indeed job URLs follow the pattern:
        https://ca.indeed.com/viewjob?jk=<job_id>

        Args:
            job_card: Selector for the job card
            job_id: The job's unique identifier
            response: Parent response for relative URL resolution

        Returns:
            Absolute URL to the job posting
        """
        # Try to extract from anchor href first
        href = job_card.css("a[href*='/viewjob']::attr(href)").get()
        if href:
            return response.urljoin(href)

        # Fallback: construct URL from job_id
        return f"https://ca.indeed.com/viewjob?jk={job_id}"

    def _extract_next_page_url(self, response: Response) -> Optional[str]:
        """
        Extract the URL for the next page of results.

        Indeed pagination uses:
        - data-testid="pagination-page-next" attribute on the next button
        - Fallback: .pagination a with specific text or aria-label

        Args:
            response: Current page response

        Returns:
            Next page URL or None if no more pages
        """
        # Primary selector: data-testid attribute (Indeed's modern pagination)
        next_link = response.css('a[data-testid="pagination-page-next"]::attr(href)').get()

        if next_link:
            return response.urljoin(next_link)

        # Fallback selector: pagination container with "Next" text
        next_link_fallback = response.css(
            'div.pagination a[aria-label="Next Page"]::attr(href)'
        ).get()

        if next_link_fallback:
            return response.urljoin(next_link_fallback)

        # Additional fallback: look for anchor with "Next" or "»" text
        next_link_text = response.css(
            'div.pagination a:contains("Next"), div.pagination a:contains("»")::attr(href)'
        ).get()

        if next_link_text:
            return response.urljoin(next_link_text)

        return None

    def handle_error(self, failure: scrapy.http.Request) -> None:
        """
        Handle request failures gracefully.

        Args:
            failure: The Twisted Failure object from Scrapy
        """
        self.logger.error(f"Request failed: {failure.value}")
        self.logger.error(f"Failed URL: {failure.request.url}")
