from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
from datetime import datetime
from services.scraper.base import BaseCarrierScraper, ScrapedShipment, ScrapedEvent
from services.config import settings
import json
import re


class GenericPlaywrightScraper(BaseCarrierScraper):
    slug = "generic"
    name = "Generic (Playwright)"

    def __init__(self, slug: str, name: str, tracking_url_template: str,
                 selectors: dict):
        self.slug = slug
        self.name = name
        self.tracking_url_template = tracking_url_template
        self.selectors = selectors

    async def track(self, tracking_number: str) -> ScrapedShipment:
        events = []
        status = "pending"

        url = self.tracking_url_template.replace("{tracking_number}", tracking_number)

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=settings.scrape_headless)
                page = await browser.new_page()
                await page.set_default_timeout(30000)

                await page.goto(url, wait_until="domcontentloaded")
                await page.wait_for_timeout(2000)

                content = await page.content()
                await browser.close()

            soup = BeautifulSoup(content, "lxml")

            event_container = soup.select(self.selectors.get("events_container", "table tr"))
            status_elem = soup.select_one(self.selectors.get("status", "h1"))

            if status_elem:
                status = self.normalize_status(status_elem.get_text(strip=True))

            for row in event_container:
                cells = row.select("td, th, [data-event]")
                if not cells or len(cells) < 2:
                    continue

                event_status = self._safe_text(cells, self.selectors.get("col_status", 0))
                event_location = self._safe_text(cells, self.selectors.get("col_location", 2))
                event_date = self._safe_text(cells, self.selectors.get("col_date", 0))
                event_time_val = self._safe_text(cells, self.selectors.get("col_time", 1))
                event_desc = self._safe_text(cells, self.selectors.get("col_desc", 1))

                events.append(ScrapedEvent(
                    status=self.normalize_status(event_status) if event_status else "unknown",
                    location_name=event_location or None,
                    description=event_desc or event_status,
                    event_time=self._parse_datetime(event_date, event_time_val),
                ))

        except Exception as e:
            return ScrapedShipment(
                tracking_number=tracking_number,
                carrier_slug=self.slug,
                status="error",
                events=[ScrapedEvent(status="error", description=str(e))],
            )

        return ScrapedShipment(
            tracking_number=tracking_number,
            carrier_slug=self.slug,
            status=status,
            events=events,
        )

    def _safe_text(self, cells, idx) -> str:
        try:
            return cells[int(idx)].get_text(strip=True)
        except (IndexError, ValueError, TypeError):
            return ""

    def _parse_datetime(self, date_str: str, time_str: str = "") -> datetime | None:
        combined = f"{date_str} {time_str}".strip()
        for fmt in [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%d/%m/%Y %H:%M",
            "%m/%d/%Y %H:%M",
            "%d %B %Y %H:%M",
            "%B %d, %Y %I:%M %p",
            "%Y-%m-%dT%H:%M:%S",
            "%d.%m.%Y %H:%M",
        ]:
            try:
                return datetime.strptime(combined, fmt)
            except ValueError:
                continue
        return None


SCRAPER_CONFIGS = {
    "royal-mail": {
        "name": "Royal Mail",
        "url": "https://www.royalmail.com/track-your-item#/tracking-results/{tracking_number}",
        "selectors": {"events_container": "[data-testid='event-row']", "status": "[data-testid='status']"},
    },
    "canada-post": {
        "name": "Canada Post",
        "url": "https://www.canadapost-postescanada.ca/track-reperage/en#/tracking/{tracking_number}",
        "selectors": {"events_container": ".tracking-event", "status": ".shipment-status"},
    },
    "australia-post": {
        "name": "Australia Post",
        "url": "https://auspost.com.au/mypost/track/#/details/{tracking_number}",
        "selectors": {"events_container": ".tracking-event-list li", "status": ".tracking-status"},
    },
    "deutsche-post": {
        "name": "Deutsche Post",
        "url": "https://www.deutschepost.de/en/p/track.html?piececode={tracking_number}",
        "selectors": {"events_container": ".timeline-event", "status": ".status-text"},
    },
    "dhl-parcel-de": {
        "name": "DHL Parcel DE",
        "url": "https://www.dhl.de/en/privatkunden/pakete-empfangen/verfolgung.html?piececode={tracking_number}",
        "selectors": {"events_container": ".shipment-timeline li", "status": ".shipment-status"},
    },
    "gls": {
        "name": "GLS",
        "url": "https://gls-group.eu/en/track/{tracking_number}",
        "selectors": {"events_container": ".timeline-event", "status": ".status-text"},
    },
    "hermes": {
        "name": "Hermes",
        "url": "https://www.myhermes.de/tracking?tracking={tracking_number}",
        "selectors": {"events_container": ".shipment-timeline li", "status": ".shipment-status"},
    },
    "yanwen": {
        "name": "Yanwen",
        "url": "https://track.yw56.com.cn/en/detail?number={tracking_number}",
        "selectors": {"events_container": ".track-list li", "status": ".track-status"},
    },
    "china-post": {
        "name": "China Post",
        "url": "http://tracking.chinapost.com/track/{tracking_number}",
        "selectors": {"events_container": ".tracking-result tbody tr", "status": ".status"},
    },
    "japan-post": {
        "name": "Japan Post",
        "url": "https://trackings.post.japanpost.jp/en/delivery/{tracking_number}",
        "selectors": {"events_container": ".tableType01 tbody tr", "status": ".td1"},
    },
    "india-post": {
        "name": "India Post",
        "url": "https://www.indiapost.gov.in/vas/Pages/track/{tracking_number}",
        "selectors": {"events_container": ".tracking-table tbody tr", "status": ".status-text"},
    },
    "correos": {
        "name": "Correos (Spain)",
        "url": "https://www.correos.es/en/track/{tracking_number}",
        "selectors": {"events_container": ".tracking-events li", "status": ".tracking-status"},
    },
    "poste-italiane": {
        "name": "Poste Italiane",
        "url": "https://www.poste.it/track/{tracking_number}",
        "selectors": {"events_container": ".timeline-event", "status": ".status-text"},
    },
    "la-poste": {
        "name": "La Poste (France)",
        "url": "https://www.laposte.fr/outils/suivre-vos-envois?code={tracking_number}",
        "selectors": {"events_container": ".timeline-item", "status": ".shipment-status"},
    },
    "postnord": {
        "name": "PostNord",
        "url": "https://www.postnord.com/en/track-and-trace/?shipmentId={tracking_number}",
        "selectors": {"events_container": ".timeline-event", "status": ".status-text"},
    },
    "swiss-post": {
        "name": "Swiss Post",
        "url": "https://www.post.ch/en/track/{tracking_number}",
        "selectors": {"events_container": ".tracking-event", "status": ".status-text"},
    },
    "an-post": {
        "name": "An Post (Ireland)",
        "url": "https://track.anpost.ie/Tracking/{tracking_number}",
        "selectors": {"events_container": ".event-row", "status": ".status"},
    },
    "nz-post": {
        "name": "New Zealand Post",
        "url": "https://www.nzpost.co.nz/tools/track?trackid={tracking_number}",
        "selectors": {"events_container": ".tracking-event", "status": ".status-text"},
    },
    "singapore-post": {
        "name": "Singapore Post",
        "url": "https://www.singpost.com/track/{tracking_number}",
        "selectors": {"events_container": ".tracking-row", "status": ".tracking-status"},
    },
    "pos-malaysia": {
        "name": "Pos Malaysia",
        "url": "https://www.poslaju.com.my/track/{tracking_number}",
        "selectors": {"events_container": ".tracking-event", "status": ".status"},
    },
    "thai-post": {
        "name": "Thai Post",
        "url": "https://track.thailandpost.co.th/{tracking_number}",
        "selectors": {"events_container": ".tracking-detail tr", "status": ".status-text"},
    },
}


def get_playwright_scraper(slug: str) -> GenericPlaywrightScraper | None:
    config = SCRAPER_CONFIGS.get(slug)
    if not config:
        return None
    return GenericPlaywrightScraper(
        slug=slug,
        name=config["name"],
        tracking_url_template=config["url"],
        selectors=config["selectors"],
    )
