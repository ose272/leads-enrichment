"""Email scraper for finding contact emails on websites."""

from __future__ import annotations

import logging
import re
import time
from functools import wraps
from typing import Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

LOGGER = logging.getLogger("scraper")

EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)

CONTACT_PATHS = [
    "/contact", "/contact-us", "/about", "/about-us", 
    "/team", "/get-in-touch", "/about/team", "/team/leadership"
]

REQUEST_DELAY = 2.0


def rate_limited(func):
    """Decorator to add rate limiting between requests."""
    last_call = [0.0]

    @wraps(func)
    def wrapper(*args, **kwargs):
        elapsed = time.time() - last_call[0]
        if elapsed < REQUEST_DELAY:
            time.sleep(REQUEST_DELAY - elapsed)
        last_call[0] = time.time()
        return func(*args, **kwargs)
    return wrapper


def retry(max_attempts: int = 3, backoff: float = 2.0):
    """Decorator for retry with exponential backoff."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        wait_time = backoff ** attempt
                        LOGGER.warning(
                            "Attempt %d/%d failed for %s: %s. Retrying in %.1fs...",
                            attempt + 1, max_attempts, args[0] if args else "unknown", e, wait_time
                        )
                        time.sleep(wait_time)
            raise last_exception
        return wrapper
    return decorator


@rate_limited
@retry(max_attempts=3, backoff=2.0)
def _fetch_page(url: str, timeout: int = 10) -> str:
    """Fetch a single page with proper headers and timeout."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }
    response = requests.get(url, headers=headers, timeout=timeout)
    response.raise_for_status()
    return response.text


def _extract_emails_from_html(html: str) -> set[str]:
    """Extract all email addresses from HTML content."""
    emails = set(EMAIL_RE.findall(html))
    
    soup = BeautifulSoup(html, "html.parser")
    for link in soup.find_all("a", href=True):
        href = link["href"]
        if href.startswith("mailto:"):
            email = href[7:].split("?")[0].strip()
            if EMAIL_RE.match(email):
                emails.add(email.lower())
    
    return emails


def _get_visible_text(soup: BeautifulSoup) -> str:
    """Get visible text from HTML, excluding scripts and styles."""
    for script in soup(["script", "style", "noscript", "meta", "link"]):
        script.decompose()
    text = soup.get_text(separator=" ", strip=True)
    return " ".join(text.split())


def scrape_email(url: str) -> Optional[str]:
    """Scrape a website for contact email addresses.

    Checks homepage and common contact/about pages.
    Returns the first email found, or None if no email found.

    Args:
        url: The website URL to scrape
        
    Returns:
        Email address string or None
    """
    # Normalize URL
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    
    # Ensure no trailing slash for consistent joining
    base_url = url.rstrip("/")
    
    # Pages to check: homepage first, then contact pages
    pages_to_check = [base_url] + [urljoin(base_url + "/", path) for path in CONTACT_PATHS]

    for page_url in pages_to_check:
        try:
            LOGGER.info("Scraping %s", page_url)
            html = _fetch_page(page_url)
            
            # Extract emails
            emails = _extract_emails_from_html(html)
            
            if emails:
                # Filter out common false positives
                filtered = [
                    e for e in emails 
                    if not any(skip in e.lower() for skip in [
                        "example.com", "test.com", "localhost", 
                        "sentry.io", "google-analytics", "googletagmanager"
                    ])
                ]
                if filtered:
                    email = filtered[0]
                    LOGGER.info("Found email %s on %s", email, page_url)
                    return email
                    
        except requests.exceptions.Timeout:
            LOGGER.warning("Timeout scraping %s", page_url)
        except requests.exceptions.ConnectionError:
            LOGGER.warning("Connection error for %s", page_url)
        except requests.exceptions.HTTPError as e:
            LOGGER.warning("HTTP error %s for %s", e.response.status_code, page_url)
        except Exception as e:
            LOGGER.warning("Unexpected error scraping %s: %s", page_url, e)
    
    LOGGER.info("No email found for %s", url)
    return None


def scrape_website_content(url: str) -> tuple[str, list[str]]:
    """Scrape website content for business context and emails.

    Returns:
        Tuple of (visible_text_summary, list_of_emails)
    """
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    
    base_url = url.rstrip("/")
    pages_to_check = [base_url] + [urljoin(base_url + "/", path) for path in CONTACT_PATHS[:2]]
    
    all_text = []
    all_emails = set()
    
    for page_url in pages_to_check:
        try:
            html = _fetch_page(page_url)
            soup = BeautifulSoup(html, "html.parser")
            
            # Get visible text
            text = _get_visible_text(soup)
            if text:
                all_text.append(text[:2000])
            
            # Get emails
            emails = _extract_emails_from_html(html)
            all_emails.update(emails)
            
        except Exception as e:
            LOGGER.warning("Error scraping %s: %s", page_url, e)
    
    summary = " ".join(all_text)[:3000]
    return summary, sorted(all_emails)


class ScrapeError(Exception):
    """Custom exception for scraping failures."""
    pass

