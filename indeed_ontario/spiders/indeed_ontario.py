"""
Indeed Ontario Job Listings Spider

Scrapes software developer job listings from Indeed Canada (Ontario region).
Designed for deployment to Zyte Scrapy Cloud with Zyte API integration.

Selector Strategy (Indeed DOM structure as of 2025):
- Job cards: .job_seen_beacon (stable class wrapping each result)
- Job ID: data-jk attribute on the inner anchor
- Job title: .jobTitle a span[title] or .jobTitle a span::text
- Company: [data-testid="company-name"]
- Location: [data-testid="text-location"]
- Date posted: .date::text
- Salary: [data-testid="attribute_snippet_testid"] or .salary-snippet
- Next page: a[data-testid="pagination-page-next"]
- Full description: #jobDescriptionText on the detail page
"""

import re
from typing import Any, Dict, Iterator, Optional, Set, Union

import scrapy
from scrapy.http import Response


class IndeedOntarioSpider(scrapy.Spider):
    """
    Spider for scraping Indeed Canada job listings for software developers in Ontario.

    Flow:
    1. Paginate the search results page, extracting summary fields from each card.
    2. Follow each job URL to the detail page and extract the full description,
       job duties, and job requirements.
    """

    name = "indeed_ontario"
    allowed_domains = ["ca.indeed.com"]

    start_url = (
        "https://ca.indeed.com/jobs?q=software+developer&l=Ontario&sort=date"
    )

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._seen_job_ids: Set[str] = set()

    def start_requests(self) -> Iterator[scrapy.Request]:
        yield scrapy.Request(
            url=self.start_url,
            callback=self.parse,
            errback=self.handle_error,
            meta={"zyte_api": {"browserHtml": True}},
        )

    def parse(self, response: Response) -> Iterator[Union[scrapy.Request, Dict[str, Any]]]:
        """Parse the search results page and follow each job to its detail page."""
        job_cards = response.css(".job_seen_beacon")
        if not job_cards:
            job_cards = response.css("div[data-jk], li[data-jk]")

        self.logger.info(f"Found {len(job_cards)} job cards on page")

        for job_card in job_cards:
            partial = self._extract_listing_fields(job_card, response)
            if partial is None:
                continue
            # Follow the job URL to scrape the full description
            yield scrapy.Request(
                url=partial["job_url"],
                callback=self.parse_job_detail,
                errback=self.handle_error,
                meta={
                    "zyte_api": {"browserHtml": True},
                    "partial": partial,
                },
            )

        next_page_url = self._extract_next_page_url(response)
        if next_page_url:
            self.logger.info(f"Following pagination to: {next_page_url}")
            yield scrapy.Request(
                url=next_page_url,
                callback=self.parse,
                errback=self.handle_error,
                meta={"zyte_api": {"browserHtml": True}},
            )
        else:
            self.logger.info("No more pages to paginate — crawl complete")

    def parse_job_detail(self, response: Response) -> Iterator[Dict[str, Any]]:
        """
        Parse the job detail page and merge with listing fields.
        Extracts full description, job duties, and job requirements.
        """
        partial: Dict[str, Any] = response.meta["partial"]

        description_text = self._extract_description_text(response)
        duties = self._extract_section(description_text, r"job\s+duties|responsibilities|what\s+you['']ll\s+do")
        requirements = self._extract_section(description_text, r"job\s+requirements?|qualifications?|what\s+you\s+(need|bring)|requirements?")

        yield {
            **partial,
            "full_description": description_text,
            "job_duties": duties,
            "job_requirements": requirements,
        }

    # ------------------------------------------------------------------ #
    # Listing-page helpers
    # ------------------------------------------------------------------ #

    def _extract_listing_fields(
        self, job_card: scrapy.Selector, response: Response
    ) -> Optional[Dict[str, Any]]:
        """Extract summary fields from a search-result job card."""
        # Job ID — on the anchor in the current layout, or on the card element itself
        job_id = (
            job_card.css("a[data-jk]::attr(data-jk)").get()
            or job_card.attrib.get("data-jk")
        )
        if not job_id:
            self.logger.warning("Job card missing data-jk, skipping")
            return None

        if job_id in self._seen_job_ids:
            self.logger.debug(f"Duplicate job_id {job_id}, skipping")
            return None
        self._seen_job_ids.add(job_id)

        # Job title — prefer the title attribute (avoids "new" badge text)
        job_title = (
            job_card.css(".jobTitle a span[title]::attr(title)").get(default="").strip()
            or job_card.css(".jobTitle a span::text").get(default="").strip()
            or job_card.css(".jobTitle span::text").get(default="").strip()
        )

        # Company — Indeed now uses data-testid="company-name"
        company = (
            job_card.css('[data-testid="company-name"]::text').get(default="").strip()
            or job_card.css(".companyName::text").get(default="").strip()
        )

        # Location — data-testid="text-location"
        location = (
            job_card.css('[data-testid="text-location"]::text').get(default="").strip()
            or job_card.css(".companyLocation::text").get(default="").strip()
        )

        # Date posted
        date_posted = job_card.css(".date::text").get(default="").strip()

        # Salary — multiple possible containers
        salary_raw = (
            job_card.css('[data-testid="attribute_snippet_testid"]::text').get(default="").strip()
            or job_card.css(".salary-snippet-container .salary-snippet::text").get(default="").strip()
            or job_card.css(".salary-snippet::text").get(default="").strip()
        )
        salary = salary_raw or None

        job_url = self._extract_job_url(job_card, job_id, response)

        self.logger.debug(f"Extracted listing: {job_title} at {company}")
        return {
            "job_id": job_id,
            "job_title": job_title,
            "company": company,
            "location": location,
            "date_posted": date_posted,
            "salary": salary,
            "job_url": job_url,
        }

    def _extract_job_url(
        self, job_card: scrapy.Selector, job_id: str, response: Response
    ) -> str:
        href = (
            job_card.css("a[data-jk]::attr(href)").get()
            or job_card.css("a[href*='/viewjob']::attr(href)").get()
        )
        if href:
            return response.urljoin(href)
        return f"https://ca.indeed.com/viewjob?jk={job_id}"

    def _extract_next_page_url(self, response: Response) -> Optional[str]:
        next_link = response.css('a[data-testid="pagination-page-next"]::attr(href)').get()
        if next_link:
            return response.urljoin(next_link)
        fallback = response.css('div.pagination a[aria-label="Next Page"]::attr(href)').get()
        if fallback:
            return response.urljoin(fallback)
        return None

    # ------------------------------------------------------------------ #
    # Detail-page helpers
    # ------------------------------------------------------------------ #

    def _extract_description_text(self, response: Response) -> str:
        """Return the full job description as plain text."""
        container = response.css("#jobDescriptionText, .jobsearch-jobDescriptionText")
        if not container:
            return ""
        # Join all text nodes; collapse whitespace
        parts = container.css("*::text").getall()
        text = " ".join(p.strip() for p in parts if p.strip())
        return text

    def _extract_section(self, text: str, heading_pattern: str) -> str:
        """
        Extract the content that follows a section heading matching heading_pattern.

        Looks for a heading line, then collects text until the next heading-like
        line or end of text. Returns an empty string if the section is not found.
        """
        if not text:
            return ""

        # Split on sentence-ending punctuation or newline-like boundaries
        # (the plain text has no real newlines after joining; we use capital
        #  letter sequences as heuristic section boundaries)
        lines = re.split(r'(?<=[.!?])\s+(?=[A-Z])', text)

        result_parts = []
        in_section = False

        for line in lines:
            if re.search(heading_pattern, line, re.IGNORECASE):
                in_section = True
                # Include text after the colon on the same line, if any
                after_colon = re.split(r'[:]\s*', line, maxsplit=1)
                if len(after_colon) > 1 and after_colon[1].strip():
                    result_parts.append(after_colon[1].strip())
                continue

            if in_section:
                # Stop at the next section heading (a short line ending with ":")
                if re.search(r'\w{4,}.*:\s*$', line):
                    break
                result_parts.append(line.strip())

        return " ".join(result_parts).strip()

    def handle_error(self, failure) -> None:
        self.logger.error(f"Request failed: {failure.value}")
        self.logger.error(f"Failed URL: {failure.request.url}")
