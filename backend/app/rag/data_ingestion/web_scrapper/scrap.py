from __future__ import annotations

import json
import re
import sys
import time
from collections import OrderedDict
from pathlib import Path
from urllib.parse import urljoin, urldefrag, urlparse

import requests
from bs4 import BeautifulSoup


PAGE_URL = "https://www.merasamvidhaan.in/index.html"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36"
)

def fetch_block_section_links(url: str) -> list[str]:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-IN,en;q=0.9",
    }

    resp = requests.get(url, headers=headers, timeout=20)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    links = []
    seen = set()

    # <a href="..."> elements inside any <section class="block">
    for a in soup.select("section.block a[href]"):
        href = a.get("href", "").strip() # type: ignore
        if not href:
            continue
        
        # Resolve relative URLs against the page URL
        absolute = urljoin(url, href)
        
        if href.startswith("#") or absolute.split("#")[0] == url.split("#")[0]:
            continue
        
        if "privacy-policy.html" in absolute or "privacy-policy.html" in href:
            continue

        if absolute not in seen:
            seen.add(absolute)
            links.append(absolute)

    return links



def fetch(session: requests.Session, url: str,
          retries: int = 3, timeout: int = 30, backoff: float = 2.0) -> str:
    last: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            r = session.get(url, timeout=timeout)
            r.raise_for_status()
            return r.text
        except requests.RequestException as e:
            last = e
            if attempt < retries:
                time.sleep(backoff * attempt)
    raise RuntimeError(f"failed to fetch {url}: {last}")


def parse_index(html: str, base_url: str):
    """Walk sections -> chips -> anchors. Returns (groups, unique_pages)"""
    soup = BeautifulSoup(html, "html.parser")

    groups: list[dict] = []
    pages: "OrderedDict[str, dict]" = OrderedDict()

    for sec in soup.select("section.group"):
        head = sec.select_one(".group-head")
        chapter = title = rng = None
        if head:
            el = head.select_one(".group-id")
            if el:  chapter = el.get_text(strip=True)
            el = head.select_one("h2")
            if el:  title   = el.get_text(strip=True)
            el = head.select_one(".group-range")
            if el:  rng     = el.get_text(strip=True)

        chips: list[dict] = []
        for a in sec.select("div.chips a.chip"):
            href = a.get("href")
            if not href:
                continue

            full_url, fragment = urldefrag(urljoin(base_url, href)) # type: ignore
            num = a.get("data-open") or a.get_text(strip=True)

            chips.append({
                "section":  num,
                "href": href,          
                "url": full_url,      
                "anchor": fragment,
                "title": a.get("title"),
            })

            rec = pages.setdefault(full_url, {
                "url": full_url,
                "chapters": [],
                "sections": [],
            })
            if chapter and chapter not in rec["chapters"]:
                rec["chapters"].append(chapter)
            rec["sections"].append(num)

        groups.append({
            "id":      sec.get("id"),
            "chapter": chapter,
            "title":   title,
            "range":   rng,
            "chips":   chips,
        })

    return groups, pages


def safe_filename(url: str) -> str:
    name = url.rsplit("/", 1)[-1] or "index.html"
    return re.sub(r"[^A-Za-z0-9._-]", "_", name)


def main(output_dir) -> int:
    
    retries = 3
    delay = 0.6
    force = True
    
    link_lists = fetch_block_section_links(PAGE_URL)
    link_lists.append("https://www.merasamvidhaan.in/income-tax-2025.html")
    link_lists.append("https://www.merasamvidhaan.in/income-tax-1961.html")
    
    for link in link_lists:

        path = urlparse(link).path 
        out_dir_name = path.strip("/").replace(".html", "") + "_sections"
                
        outdir = Path(output_dir) / out_dir_name 
        outdir.mkdir(parents=True, exist_ok=True)

        session = requests.Session()
        session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept-Language": "en-IN,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml",
        })

        base_url = link
        print(f"index: fetching {base_url}", file=sys.stderr)
        html = fetch(session, base_url, retries=retries)

        groups, pages = parse_index(html, base_url)

        total_chips = sum(len(g["chips"]) for g in groups)
        print(f"found {len(groups)} sections, {total_chips} chips, "
            f"{len(pages)} unique pages to fetch", file=sys.stderr)

        # download each unique target page
        manifest = {
            "index":   base_url,
            "groups":  groups,
            "pages":   [],
        }

        for i, (url, rec) in enumerate(pages.items(), 1):
            fname = safe_filename(url)
            dest  = outdir / fname
            entry = dict(rec)
            entry["file"] = fname

            if dest.exists() and not force:
                entry["skipped"] = True
                print(f"[{i:>2}/{len(pages)}] skip  {fname}", file=sys.stderr)
            else:
                text = fetch(session, url, retries=retries)
                dest.write_text(text, encoding="utf-8")
                entry["bytes"] = len(text.encode("utf-8"))
                print(f"[{i:>2}/{len(pages)}] saved {fname}  ({entry['bytes']:,} B)",
                    file=sys.stderr)
                time.sleep(delay)

            manifest["pages"].append(entry)

        mpath = outdir / "_manifest.json"
        mpath.write_text(json.dumps(manifest, indent=2, ensure_ascii=False),
                        encoding="utf-8")
        print(f"\nwrote {mpath}", file=sys.stderr)
        
    return 0


if __name__ == "__main__":
    
    output_dir = Path(__file__).parent / "scrapped"
    
    raise SystemExit(main(output_dir))


    
    
    
    # link_lists = [
        # "https://www.merasamvidhaan.in/contract.html",
        # "https://www.merasamvidhaan.in/limitation.html",
        # "https://www.merasamvidhaan.in/technology.html",
        # "https://www.merasamvidhaan.in/rti.html",
        # "https://www.merasamvidhaan.in/consumer.html",
        # "https://www.merasamvidhaan.in/companies.html",
        # "https://www.merasamvidhaan.in/insolvency.html",
        # "https://www.merasamvidhaan.in/arbitration.html",
        # "https://www.merasamvidhaan.in/negotiable-instruments.html",
        # "https://www.merasamvidhaan.in/transfer-of-property.html",
        # "https://www.merasamvidhaan.in/registration.html",
        # "https://www.merasamvidhaan.in/easements.html",
        # "https://www.merasamvidhaan.in/hindu-marriage.html",
        # "https://www.merasamvidhaan.in/hindu-succession.html",
        # "https://www.merasamvidhaan.in/special-marriage.html",
        # "https://www.merasamvidhaan.in/succession.html",
        # "https://www.merasamvidhaan.in/specific-relief.html",
        # "https://www.merasamvidhaan.in/sale-of-goods.html",
        # "https://www.merasamvidhaan.in/partnership.html",
        # "https://www.merasamvidhaan.in/llp.html",
        # "https://www.merasamvidhaan.in/pocso.html",
        # "https://www.merasamvidhaan.in/domestic-violence.html",
        # "https://www.merasamvidhaan.in/dowry.html",
        # "https://www.merasamvidhaan.in/scst.html",
        # "https://www.merasamvidhaan.in/rpwd.html",
        # "https://www.merasamvidhaan.in/senior-citizens.html",
        # "https://www.merasamvidhaan.in/family-courts.html",
        # "https://www.merasamvidhaan.in/legal-services.html",
        # "https://www.merasamvidhaan.in/human-rights.html",
        # "https://www.merasamvidhaan.in/prevention-of-corruption.html",
        # "https://www.merasamvidhaan.in/dpdp.html",
        # "https://www.merasamvidhaan.in/juvenile-justice.html",
        # "https://www.merasamvidhaan.in/right-to-education.html",
        # "https://www.merasamvidhaan.in/gst.html",
        # "https://www.merasamvidhaan.in/income-tax-2025.html",
        # "https://www.merasamvidhaan.in/income-tax-1961.html",
    # ]