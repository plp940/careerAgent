import requests
import re

# ── Adzuna country code map ───────────────────────────────────────────────────
# Location keywords → Adzuna country codes (supports multiple per region)
LOCATION_TO_ADZUNA = {
    # USA
    "usa": ["us"],
    "united states": ["us"],
    "america": ["us"],
    "new york": ["us"],
    "san francisco": ["us"],
    "seattle": ["us"],
    "austin": ["us"],
    "chicago": ["us"],
    "boston": ["us"],
    # Dubai / UAE / Gulf
    "dubai": ["ae"],
    "uae": ["ae"],
    "abu dhabi": ["ae"],
    "gulf": ["ae"],
    "middle east": ["ae"],
    # India
    "india": ["in"],
    "bangalore": ["in"],
    "bengaluru": ["in"],
    "mumbai": ["in"],
    "hyderabad": ["in"],
    "chennai": ["in"],
    "delhi": ["in"],
    "pune": ["in"],
    # Europe
    "europe": ["gb", "de", "nl", "fr"],
    "uk": ["gb"],
    "london": ["gb"],
    "united kingdom": ["gb"],
    "germany": ["de"],
    "berlin": ["de"],
    "munich": ["de"],
    "netherlands": ["nl"],
    "amsterdam": ["nl"],
    "france": ["fr"],
    "paris": ["fr"],
    # Canada
    "canada": ["ca"],
    "toronto": ["ca"],
    "vancouver": ["ca"],
    # Australia
    "australia": ["au"],
    "sydney": ["au"],
    "melbourne": ["au"],
    # Remote — no Adzuna country; handled separately
    "remote": [],
}


def _resolve_adzuna_countries(location: str) -> list[str]:
    """Map a freeform location string to Adzuna country codes."""
    loc = location.strip().lower()
    # exact match first
    if loc in LOCATION_TO_ADZUNA:
        return LOCATION_TO_ADZUNA[loc]
    # partial match
    for key, codes in LOCATION_TO_ADZUNA.items():
        if key in loc or loc in key:
            return codes
    # fallback: try treating it as a country code directly
    return ["us"]  # safe default


def fetch_adzuna(
    keyword: str,
    location: str = "",
    limit: int = 5,
    app_id: str = "",
    app_key: str = "",
) -> list:
    """
    Fetch jobs from Adzuna across one or more country codes derived from location.
    Returns list in the same MatchedObjectDescriptor format as USAJobs/Remotive.
    """
    if not app_id or not app_key:
        print("[Adzuna] No API credentials — skipping.")
        return []

    is_remote = location.strip().lower() == "remote"
    country_codes = _resolve_adzuna_countries(location) if location.strip() else ["us"]

    results = []
    seen_ids = set()

    for country in country_codes:
        try:
            params = {
                "app_id": app_id,
                "app_key": app_key,
                "what": keyword,
                "results_per_page": limit,
                "content-type": "application/json",
            }
            # For remote searches pass "telecommute" flag where supported
            if is_remote:
                params["title_only"] = keyword  # stricter match for remote
            elif location.strip():
                params["where"] = location.strip()

            url = f"https://api.adzuna.com/v1/api/jobs/{country}/search/1"
            r = requests.get(url, params=params, timeout=12)
            r.raise_for_status()
            jobs = r.json().get("results", [])
            print(f"[Adzuna/{country.upper()}] '{keyword}' → {len(jobs)} results")

            for j in jobs:
                job_id = j.get("id", "")
                if job_id in seen_ids:
                    continue
                seen_ids.add(job_id)

                loc_parts = j.get("location", {}).get("area", [])
                loc_display = (
                    ", ".join(loc_parts[-2:]) if loc_parts else country.upper()
                )

                results.append(
                    {
                        "MatchedObjectDescriptor": {
                            "PositionTitle": j.get("title", "Unknown Title"),
                            "OrganizationName": j.get("company", {}).get(
                                "display_name", "Unknown Company"
                            ),
                            "PositionLocationDisplay": (
                                "Remote" if is_remote else loc_display
                            ),
                            "PositionURI": j.get("redirect_url", ""),
                            "_source": f"🔍 Adzuna/{country.upper()}",
                            "UserArea": {
                                "Details": {
                                    "JobSummary": _strip_html(j.get("description", ""))[
                                        :2000
                                    ]
                                }
                            },
                        }
                    }
                )
        except Exception as e:
            print(f"[Adzuna/{country}] Error: {e}")
            continue

    return results


def fetch_remotive(keyword: str, limit: int = 5) -> list:
    """Free API, no key needed. Remote tech jobs worldwide."""
    try:
        r = requests.get(
            "https://remotive.com/api/remote-jobs",
            params={"search": keyword, "limit": limit},
            timeout=10,
        )
        r.raise_for_status()
        jobs = r.json().get("jobs", [])
        print(f"[Remotive] '{keyword}' → {len(jobs)} results")
        return [
            {
                "MatchedObjectDescriptor": {
                    "PositionTitle": j.get("title", "Unknown Title"),
                    "OrganizationName": j.get("company_name", "Unknown Company"),
                    "PositionLocationDisplay": "Remote",
                    "PositionURI": j.get("url", ""),
                    "_source": "🌐 Remotive",
                    "UserArea": {
                        "Details": {
                            "JobSummary": _strip_html(j.get("description", ""))[:2000]
                        }
                    },
                }
            }
            for j in jobs
        ]
    except Exception as e:
        print(f"[Remotive] Error: {e}")
        return []


def _strip_html(text: str) -> str:
    clean = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", clean).strip()
