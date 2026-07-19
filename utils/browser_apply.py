"""
utils/browser_apply.py
Auto-Apply agent using Playwright to fill job application forms.
"""

import os
import json
import logging
from dotenv import load_dotenv
import litellm

load_dotenv()
logger = logging.getLogger(__name__)

# Fallback profile block when no Bio is provided
DEFAULT_PROFILE = {
    "first_name": "Venkat",
    "last_name": "Applicant",
    "email": "venkat.applicant@example.com",
    "phone": "555-0199",
    "linkedin": "https://linkedin.com/in/venkat-applicant",
    "github": "https://github.com/venkat-applicant",
    "portfolio": "https://venkat-applicant.dev",
    "address": "San Francisco, CA",
    "expected_salary": "120000",
    "authorized_to_work": "Yes",
    "requires_sponsorship": "No"
}

def analyze_form_with_llm(html_snippet: str) -> dict:
    """
    Use LLM to inspect clean selector inputs and suggest value mappings to target profile keys.
    """
    prompt = f"""You are analyzing a job application form HTML snippet to yield field mappings.
Given the HTML snippet below, return a JSON map matching tag selectors (like 'input[name="first_name"]' or '#email') to the appropriate profile data field names:
Available profile field names:
- first_name
- last_name
- email
- phone
- linkedin
- github
- portfolio
- address
- expected_salary
- authorized_to_work
- requires_sponsorship

HTML Snippet:
{html_snippet}

Output should be a strict JSON object mapping browser CSS selectors to candidate profile keys, for example:
{{
  "input[name='first_name']": "first_name",
  "input[type='email']": "email"
}}
Return ONLY the raw JSON object, no markdown code blocks, no intro or explanation.
"""
    try:
        model = os.getenv("LLM_MODEL", "groq/llama-3.3-70b-versatile")
        # swap to fallback instructor if not groq
        if "groq" not in model and not os.getenv("GROQ_API_KEY"):
            model = "openrouter/google/gemma-4-26b-a4b-it:free"
            
        r = litellm.completion(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=600
        )
        text = r.choices[0].message.content.strip()
        # Clean potential markdown wrapping
        if text.startswith("```json"):
            text = text[7:]
        if text.endswith("```"):
            text = text[:-3]
        return json.loads(text.strip())
    except Exception as e:
        logger.error(f"[LLM Form Analyzer] Analysis failed: {e}")
        return {}

def auto_fill_form(job_url: str, resume_path: str, user_bio: str = "") -> dict:
    """
    Locates inputs on the application page and completes them using Playwright.
    Leaves the browser session open so the candidate can inspect and submit.
    """
    status = {"success": False, "message": "", "fields_filled": []}
    
    # Try importing playwright
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        status["message"] = "Playwright not installed. Run 'pip install playwright' to enable browser form filling."
        logger.warning(status["message"])
        return status

    # Parse profile from user bio or default
    profile = DEFAULT_PROFILE.copy()
    if user_bio:
        # Prompt LLM to structure user bio into profile fields
        try:
            model = os.getenv("LLM_MODEL", "groq/llama-3.3-70b-versatile")
            if "groq" not in model and not os.getenv("GROQ_API_KEY"):
                model = "openrouter/google/gemma-4-26b-a4b-it:free"
            prompt = f"""Convert this user bio into a structured JSON profile matching these fields.
Bio:
{user_bio}

Schema target fields:
first_name, last_name, email, phone, linkedin, github, portfolio, address, expected_salary, authorized_to_work, requires_sponsorship.
If direct values are missing, guess reasonably or keep default placeholder formats.
Return ONLY valid JSON.
"""
            r = litellm.completion(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=500
            )
            structured = json.loads(r.choices[0].message.content.strip())
            profile.update({k: v for k, v in structured.items() if k in profile})
        except Exception as ex:
            logger.error(f"Failed parsing bio to profile: {ex}")

    try:
        # Using Playwright Sync API
        playwright_instance = sync_playwright().start()
        # Launch browser in visible headed mode so user can see it! Beautiful hackathon demo look.
        browser = playwright_instance.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        
        logger.info(f"Navigating to {job_url}...")
        page.goto(job_url, timeout=30000)
        page.wait_for_load_state("networkidle")

        # Extract text inputs, dropboxes, area elements
        inputs = page.query_selector_all("input, textarea, select")
        input_details = []
        for i, element in enumerate(inputs):
            try:
                tag = element.evaluate("el => el.tagName.toLowerCase()")
                name = element.get_attribute("name") or ""
                inp_type = element.get_attribute("type") or ""
                placeholder = element.get_attribute("placeholder") or ""
                id_val = element.get_attribute("id") or ""
                
                # Make a simple selector
                selector = ""
                if id_val:
                    selector = f"#{id_val}"
                elif name:
                    selector = f"{tag}[name='{name}']"
                else:
                    selector = f"{tag}:nth-child({i+1})"
                    
                input_details.append({
                    "selector": selector,
                    "tag": tag,
                    "type": inp_type,
                    "name": name,
                    "placeholder": placeholder
                })
            except Exception:
                continue

        # Use LLM to resolve selectors to profile fields
        snippet = json.dumps(input_details[:30], indent=2)
        mappings = analyze_form_with_llm(snippet)
        
        logger.info(f"Resolved form mappings: {mappings}")
        
        # Fill mapped fields
        for selector, profile_key in mappings.items():
            if profile_key not in profile:
                continue
            val = profile[profile_key]
            try:
                element = page.query_selector(selector)
                if element:
                    tag = element.evaluate("el => el.tagName.toLowerCase()")
                    inp_type = element.get_attribute("type") or ""
                    
                    if inp_type == "file":
                        if resume_path and os.path.exists(resume_path):
                            element.set_input_files(resume_path)
                            status["fields_filled"].append(f"{profile_key} (File Upload -> {os.path.basename(resume_path)})")
                    elif tag == "select":
                        # Attempt selecting by value or label Match
                        element.select_option(value=val)
                        status["fields_filled"].append(f"{profile_key} (Dropdown -> {val})")
                    elif inp_type in ["checkbox", "radio"]:
                        # Simple checks
                        if val.lower() in ["yes", "true", "1"]:
                            element.check()
                            status["fields_filled"].append(f"{profile_key} (Checked)")
                    else:
                        element.fill(str(val))
                        status["fields_filled"].append(f"{profile_key} (Text -> {val})")
            except Exception as e:
                logger.error(f"Error filling {selector} with {val}: {e}")

        # Fallback heuristic: Try matching on common names/placeholder keywords directly
        for details in input_details:
            name_lower = details["name"].lower()
            place_lower = details["placeholder"].lower()
            tag = details["tag"]
            selector = details["selector"]
            
            # Skip if already filled
            if any(selector in f for f in status["fields_filled"]):
                continue
                
            try:
                element = page.query_selector(selector)
                if not element:
                    continue
                    
                if details["type"] == "file" or "resume" in name_lower or "cv" in name_lower:
                    if resume_path and os.path.exists(resume_path):
                        element.set_input_files(resume_path)
                        status["fields_filled"].append(f"resume (Heuristic Upload)")
                elif "first" in name_lower or "firstname" in name_lower:
                    element.fill(profile["first_name"])
                    status["fields_filled"].append("first_name (Heuristic)")
                elif "last" in name_lower or "lastname" in name_lower:
                    element.fill(profile["last_name"])
                    status["fields_filled"].append("last_name (Heuristic)")
                elif "email" in name_lower or "mail" in name_lower:
                    element.fill(profile["email"])
                    status["fields_filled"].append("email (Heuristic)")
                elif "phone" in name_lower or "mobile" in name_lower or "tel" in name_lower:
                    element.fill(profile["phone"])
                    status["fields_filled"].append("phone (Heuristic)")
                elif "linkedin" in name_lower or "linkedin" in place_lower:
                    element.fill(profile["linkedin"])
                    status["fields_filled"].append("linkedin (Heuristic)")
                elif "github" in name_lower or "github" in place_lower:
                    element.fill(profile["github"])
                    status["fields_filled"].append("github (Heuristic)")
                elif "portfolio" in name_lower or "web" in name_lower or "website" in name_lower:
                    element.fill(profile["portfolio"])
                    status["fields_filled"].append("portfolio (Heuristic)")
            except Exception:
                continue

        status["success"] = True
        status["message"] = "Form filled successfully! The browser session is kept open for you to verify details and press Submit."
        
    except Exception as e:
        status["message"] = f"Error during browser automation: {e}"
        logger.error(status["message"])
        
    return status
