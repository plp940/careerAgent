import requests
from utils.config import USAJOBS_API_KEY, USAJOBS_USER_AGENT


def fetch_usajobs(keyword, location="", results_per_page=5):
    if location.strip().lower() == "remote":
        print("[USAJobs] Skipping — remote searches use Remotive/Adzuna only.")
        return []
    
    headers = {
        "Host": "data.usajobs.gov",
        "User-Agent": USAJOBS_USER_AGENT,  # pull from config, not hardcoded
        "Authorization-Key": USAJOBS_API_KEY,
    }

    params = {"Keyword": keyword, "ResultsPerPage": results_per_page}

    # Only add location if user actually provides one
    if location and location.strip() and location.lower() != "remote":
        params["LocationName"] = location

    try:
        response = requests.get(
            "https://data.usajobs.gov/api/search",
            headers=headers,
            params=params,
            timeout=15,
        )
        if response.status_code == 200:
            items = response.json().get("SearchResult", {}).get("SearchResultItems", [])
            print(f"[USAJobs] '{keyword}' → {len(items)} results")
            return items
        else:
            print(f"[USAJobs] Error {response.status_code}: {response.text[:200]}")
            return []
    except requests.exceptions.Timeout:
        print("[USAJobs] Request timed out")
        return []
    except Exception as e:
        print(f"[USAJobs] Unexpected error: {e}")
        return []


if __name__ == "__main__":
    # Test with multiple keywords to verify the fix
    for kw in ["business analyst", "software engineer", "data scientist", "nurse"]:
        jobs = fetch_usajobs(kw, results_per_page=3)
        print(f"\n{kw}: {len(jobs)} jobs found")
        for job in jobs:
            d = job["MatchedObjectDescriptor"]
            print(f"  → {d['PositionTitle']} at {d['OrganizationName']}")
