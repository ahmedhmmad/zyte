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
from scrapy.spidermiddlewares.httperror import HttpError


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

        container = self._get_description_container(response)
        description_text = self._container_to_text(container) if container else ""
        duties = self._extract_section_html(
            container,
            r"job\s+duties|responsibilities|what\s+you[''\u2019]ll\s+do|your\s+role",
        )
        requirements = self._extract_section_html(
            container,
            r"job\s+requirements?|qualifications?|what\s+you\s+(need|bring)|requirements?|must\s+have",
        )

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

    # Selectors tried in order to locate the job description container.
    # Indeed has used several different IDs/classes over time.
    _DESCRIPTION_SELECTORS = (
        "#jobDescriptionText",
        ".jobsearch-jobDescriptionText",
        ".jobDescriptionText",
        '[data-testid="jobDescriptionText"]',
        "#job-description-container",
        ".jobsearch-JobComponent-description",
        # Broad fallback: any div whose id contains "description"
        'div[id*="description"]',
    )

    def _get_description_container(self, response: Response):
        """Return the first matching description container, or None."""
        for sel in self._DESCRIPTION_SELECTORS:
            container = response.css(sel)
            if container:
                # Verify it actually has text before accepting
                if any(t.strip() for t in container.css("::text").getall()):
                    self.logger.debug(f"Description container matched by: {sel}")
                    return container
        self.logger.warning(f"No description container found on: {response.url}")
        return None

    def _container_to_text(self, container) -> str:
        """Flatten all text nodes in a container into a single string."""
        parts = container.css("*::text").getall()
        return " ".join(p.strip() for p in parts if p.strip())

    def _extract_section_html(self, container, heading_pattern: str) -> str:
        """
        Extract a named section from the description container by scanning
        the HTML structure.

        Strategy:
        - Walk every block-level and inline-heading element in document order.
        - When an element whose text matches heading_pattern is found, switch
          into collection mode.
        - Collect text from <p> and <li> elements that follow.
        - Stop when the next heading-like element is encountered.

        This works on the rendered HTML tree and is far more reliable than
        trying to split a flat text string.
        """
        if container is None:
            return ""

        in_section = False
        result_parts = []

        # Walk headings, bold/strong (used as pseudo-headings), paragraphs, list items
        for element in container.css("h1, h2, h3, h4, h5, h6, strong, b, p, li, div"):
            raw_texts = element.css("::text").getall()
            text = " ".join(t.strip() for t in raw_texts if t.strip())
            if not text:
                continue

            tag = element.root.tag

            # Decide whether this element is a heading / section boundary
            is_heading = (
                tag in ("h1", "h2", "h3", "h4", "h5", "h6")
                or (tag in ("strong", "b") and len(text) < 120)
                or (tag == "div" and len(text) < 120 and re.search(r":\s*$", text))
            )

            if is_heading and re.search(heading_pattern, text, re.IGNORECASE):
                in_section = True
                # Capture anything after a colon on the same heading line
                after = re.split(r":\s*", text, maxsplit=1)
                if len(after) > 1 and after[1].strip():
                    result_parts.append(after[1].strip())
                continue

            if in_section:
                if is_heading:
                    # Reached the next section — stop
                    break
                if tag in ("p", "li"):
                    result_parts.append(text)

        return " ".join(result_parts).strip()

    def handle_error(self, failure) -> Iterator[Dict[str, Any]]:
        if failure.check(HttpError):
            response = failure.value.response
            if response.status == 404:
                # Likely a fake/ad placeholder job ID — yield partial item with empty detail fields
                partial = failure.request.meta.get("partial")
                if partial:
                    self.logger.warning(f"Job not found (404), keeping listing data: {failure.request.url}")
                    yield {**partial, "full_description": "", "job_duties": "", "job_requirements": ""}
                return
            self.logger.error(f"HTTP {response.status} for: {failure.request.url}")
        else:
            self.logger.error(f"Request failed: {failure.value}")
            self.logger.error(f"Failed URL: {failure.request.url}")
