"""
utils/cron_agent.py
Autonomous Scheduler / Cron Agent that checks job boards periodically,
matches with candidate profiles, and auto-tailors applications.
"""

import os
import time
import json
import logging
import datetime
import threading
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

from usajobs_api import fetch_usajobs
from utils.job_sources import fetch_adzuna, fetch_remotive
from utils.tracking import is_duplicate
from orchestrator import run_pipeline

ALERT_OUTPUT_DIR = "data/alert_applications"

def send_slack_alert(title: str, company: str, score: float, source: str):
    """Sends matched job alerts to an external Slack webhook if configured."""
    webhook_url = os.getenv("SLACK_WEBHOOK_URL")
    if not webhook_url:
        return
        
    payload = {
        "text": f"🎯 *New Job Alert Match!* \n\n*Title*: {title} \n*Company*: {company} \n*Compatibility Score*: `{score}%` \n*Source*: {source} \n\n_Auto-tailored resume folder and cover letter generated successfully! Ready to apply._"
    }
    try:
        import requests
        response = requests.post(webhook_url, json=payload, headers={"Content-Type": "application/json"}, timeout=10)
        if response.status_code == 200:
            logger.info(f"Slack webhook sent successfully for {title} at {company}.")
        else:
            logger.error(f"Slack webhook returned status code {response.status_code}: {response.text}")
    except Exception as e:
        logger.error(f"Failed to post alert payload to Slack: {e}")

# Global control for background scheduling loop
_scheduler_thread = None
_stop_scheduler = threading.Event()

def search_all_sources(keyword: str, location: str = "", limit: int = 3) -> list:
    """Consolidates job search across all integrated endpoints."""
    all_jobs = []
    
    # 1. Remotive (Keyless)
    remotive_jobs = fetch_remotive(keyword, limit=limit)
    all_jobs.extend(remotive_jobs)
    
    # 2. USAJobs
    usajobs = fetch_usajobs(keyword, location, results_per_page=limit)
    for j in usajobs:
        # Map to unified structure
        try:
            # Check source format, add source field
            j["MatchedObjectDescriptor"]["_source"] = "🏛️ USAJobs"
            all_jobs.append(j)
        except KeyError:
            continue
            
    # 3. Adzuna
    adzuna_id = os.getenv("ADZUNA_APP_ID")
    adzuna_key = os.getenv("ADZUNA_APP_KEY")
    if adzuna_id and adzuna_key:
        adzuna_jobs = fetch_adzuna(keyword, location, limit=limit, app_id=adzuna_id, app_key=adzuna_key)
        all_jobs.extend(adzuna_jobs)
        
    return all_jobs

def run_cron_cycle(keyword: str, location: str, resume_text: str, user_bio: str, min_score: int = 75) -> dict:
    """
    Executes one background sourcing scan.
    Returns details of highly matching jobs found and auto-processed.
    """
    os.makedirs(ALERT_OUTPUT_DIR, exist_ok=True)
    logger.info(f"[Cron Alarm] Checking jobs for keyword: '{keyword}' in '{location}'")
    
    jobs = search_all_sources(keyword, location, limit=5)
    matched_results = []
    
    for job in jobs:
        try:
            desc = job["MatchedObjectDescriptor"]
            title = desc.get("PositionTitle", "Unknown Title")
            company = desc.get("OrganizationName", "Unknown Company")
            source = desc.get("_source", "Unknown Source")
            
            # Skip if already applied/processed
            if is_duplicate(title, company):
                continue
                
            # Execute full pipeline orchestration to score, tailor, write cover letter and log
            pipeline_result = run_pipeline(
                job_data=desc,
                resume_text=resume_text,
                user_bio=user_bio
            )
            
            score_val = pipeline_result["score_data"].get("match_score", 0)
            if score_val >= min_score:
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                job_slug = f"{title}_{company}".replace(" ", "_").replace("/", "_")
                # Keep alphanumeric only
                job_slug = "".join(c for c in job_slug if c.isalnum() or c == "_")
                
                alert_file = os.path.join(ALERT_OUTPUT_DIR, f"cron_match_{job_slug}_{timestamp}.json")
                with open(alert_file, "w", encoding="utf-8") as f:
                    json.dump(pipeline_result, f, indent=2)
                    
                matched_results.append({
                    "title": title,
                    "company": company,
                    "score": score_val,
                    "source": source,
                    "saved_alert_file": alert_file
                })
                logger.info(f"[Cron Alarm] Alert Match Found & Tailored: {title} at {company} (Score: {score_val})")
                
                # Send slack webhook alert notification if configured
                send_slack_alert(title, company, score_val, source)
                
                # Sleep briefly between matching runs to respect rate limits
                time.sleep(10)
        except Exception as e:
            logger.error(f"[Cron Cycle] Error processing job: {e}")
            continue
            
    return {
        "timestamp": datetime.datetime.now().isoformat(),
        "keyword": keyword,
        "location": location,
        "matched_count": len(matched_results),
        "matches": matched_results
    }

def start_background_scheduler(keyword: str, location: str, resume_text: str, user_bio: str, interval_hours: float = 24.0, min_score: int = 75):
    """Launches the background daemon loop."""
    global _scheduler_thread, _stop_scheduler
    if _scheduler_thread and _scheduler_thread.is_alive():
        logger.warning("[Cron Scheduler] Already running.")
        return False
        
    _stop_scheduler.clear()
    
    def loop():
        while not _stop_scheduler.is_set():
            try:
                run_cron_cycle(keyword, location, resume_text, user_bio, min_score)
            except Exception as e:
                logger.error(f"[Scheduler Loop] Worker error: {e}")
            # wait with interval splitting to facilitate quick termination shutdown
            for _ in range(int(interval_hours * 3600)):
                if _stop_scheduler.is_set():
                    break
                time.sleep(1)
                
    _scheduler_thread = threading.Thread(target=loop, daemon=True)
    _scheduler_thread.start()
    logger.info(f"[Cron Scheduler] Started daemon running every {interval_hours} hours.")
    return True

def stop_background_scheduler():
    global _scheduler_thread, _stop_scheduler
    if _scheduler_thread and _scheduler_thread.is_alive():
        _stop_scheduler.set()
        _scheduler_thread.join()
        logger.info("[Cron Scheduler] Terminated background daemon.")
        return True
    return False
