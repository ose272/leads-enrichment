"""Lightweight website enrichment for lead records."""

from __future__ import annotations

import re
from html.parser import HTMLParser
from urllib.parse import urljoin
from urllib.request import Request, urlopen


EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []
        self.text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            href = dict(attrs).get("href")
            if href:
                self.links.append(href)

    def handle_data(self, data: str) -> None:
        cleaned = " ".join(data.split())
        if cleaned:
            self.text.append(cleaned)


def fetch_page(url: str, timeout: int = 15) -> str:
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    request = Request(url, headers={"User-Agent": "SEGlobalLeadResearch/1.0"})
    with urlopen(request, timeout=timeout) as response:
        return response.read(2_000_000).decode("utf-8", errors="ignore")


def enrich_website(website: str) -> tuple[str, list[str]]:
    if not website:
        return "", []
    try:
        html = fetch_page(website)
        parser = PageParser()
        parser.feed(html)
        emails = set(EMAIL_RE.findall(html))
        base = website if website.startswith("http") else "https://" + website
        contact_links = [urljoin(base, link) for link in parser.links if "contact" in link.lower()]
        if not emails and contact_links:
            try:
                contact_html = fetch_page(contact_links[0])
                emails.update(EMAIL_RE.findall(contact_html))
                parser.feed(contact_html)
            except Exception:
                pass
        summary = " ".join(parser.text)[:1000]
        return summary, sorted(emails)
    except Exception:
        return "", []
