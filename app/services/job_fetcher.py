"""Fetch jobs from a configured source and store them."""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

from app.services.job_extractors import (
    extract_direct_url_jobs,
    extract_greenhouse_jobs,
    extract_lever_jobs,
)
from app.services.job_storage import save_jobs


SOURCE_TYPES = ("Auto-detect", "Greenhouse", "Lever", "Direct URL")

EXTRACTORS = {
    "Greenhouse": extract_greenhouse_jobs,
    "Lever": extract_lever_jobs,
    "Direct URL": extract_direct_url_jobs,
}


def fetch_and_store_jobs(company_name: str, source_url: str, source_type: str = "Auto-detect") -> int:
    """Extract jobs from a source and upsert them. Returns the number of jobs saved."""
    source_url = source_url.strip()
    if not looks_like_url(source_url):
        raise ValueError("Invalid URL. Use a public http or https URL.")
    if source_type not in SOURCE_TYPES:
        raise ValueError(f"Unknown source type {source_type!r}. Use one of: {', '.join(SOURCE_TYPES)}.")
    _reject_private_host(source_url)

    resolved_type = resolve_source_type(source_url, source_type)
    jobs = EXTRACTORS[resolved_type](company_name, source_url)
    return save_jobs(jobs)


def looks_like_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def resolve_source_type(source_url: str, source_type: str) -> str:
    if source_type != "Auto-detect":
        return source_type

    host = urlparse(source_url).netloc.lower()
    if "greenhouse.io" in host:
        return "Greenhouse"
    if "lever.co" in host:
        return "Lever"
    return "Direct URL"


def _reject_private_host(url: str) -> None:
    """Only public career pages are supported; refuse localhost and private network addresses."""
    host = urlparse(url).hostname or ""
    try:
        addresses = {info[4][0] for info in socket.getaddrinfo(host, None)}
    except socket.gaierror as error:
        raise ValueError(f"Could not resolve host {host!r}.") from error
    for address in addresses:
        ip = ipaddress.ip_address(address.split("%")[0])
        if not ip.is_global:
            raise ValueError("Only public career pages can be fetched.")
