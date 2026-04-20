import json
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import requests

KEYWORDS = ["AI Engineer", "Machine Learning Engineer", "Data Scientist", "Software Engineer"]
ML_AI_TERMS = [
    "machine learning", " ml ", "ai ", "artificial intelligence",
    "deep learning", "nlp", "llm", "generative",
]
SENIOR_EXCLUDE = [
    "senior", "staff", "principal", "lead", "director",
    "manager", "head of", "vp", "vice president", " iii", " iv", " v ",
]
US_INDICATORS = [
    ", us", ", usa", "united states", " - us", "remote - us",
    "san francisco", "new york", "mountain view", "seattle",
    "boston", "los angeles", "chicago", "austin", "palo alto",
    "washington, dc", "denver", "atlanta", "san jose",
]
SEEN_JOBS_FILE = "scraper/jobs_seen.json"


def is_us_location(loc_str):
    if not loc_str:
        return False
    loc_lower = loc_str.lower()
    return any(x in loc_lower for x in US_INDICATORS)


def load_seen_jobs():
    if os.path.exists(SEEN_JOBS_FILE):
        with open(SEEN_JOBS_FILE, "r") as f:
            return json.load(f)
    return {}


def save_seen_jobs(seen):
    with open(SEEN_JOBS_FILE, "w") as f:
        json.dump(seen, f, indent=2)


def is_relevant_title(title):
    title_lower = title.lower()
    if any(bad in title_lower for bad in SENIOR_EXCLUDE):
        return False
    for kw in KEYWORDS:
        if kw.lower() in title_lower:
            if kw.lower() == "software engineer":
                if any(term in title_lower for term in ML_AI_TERMS):
                    return True
            else:
                return True
    return False


def scrape_greenhouse(company_slug, company_display):
    jobs = []
    url = f"https://boards-api.greenhouse.io/v1/boards/{company_slug}/jobs"
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        for job in data.get("jobs", []):
            title = job.get("title", "")
            job_id = str(job.get("id", ""))
            location = job.get("location", {}).get("name", "")
            if is_relevant_title(title) and is_us_location(location):
                jobs.append({
                    "id": f"{company_slug}_{job_id}",
                    "company": company_display,
                    "title": title,
                    "location": location,
                    "url": job.get("absolute_url", ""),
                    "posted": job.get("updated_at", ""),
                })
    except Exception as e:
        print(f"[{company_display}] Error: {e}")

    return jobs


def scrape_ashby(company_slug, company_display):
    jobs = []
    url = f"https://api.ashbyhq.com/posting-api/job-board/{company_slug}"
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        for job in data.get("jobs", []):
            title = job.get("title", "")
            job_id = str(job.get("id", ""))
            if not job.get("isListed", True):
                continue
            country = (
                job.get("address", {})
                .get("postalAddress", {})
                .get("addressCountry", "")
            )
            location = job.get("location", "")
            is_us = country == "United States" or is_us_location(location)
            if is_relevant_title(title) and is_us:
                jobs.append({
                    "id": f"{company_slug}_{job_id}",
                    "company": company_display,
                    "title": title,
                    "location": location,
                    "url": job.get("jobUrl", ""),
                    "posted": job.get("publishedAt", ""),
                })
    except Exception as e:
        print(f"[{company_display}] Error: {e}")

    return jobs


def send_email(new_jobs):
    sender = os.environ["EMAIL_SENDER"]
    password = os.environ["EMAIL_PASSWORD"]
    recipient = os.environ["EMAIL_RECIPIENT"]

    subject = f"[Job Alert] {len(new_jobs)} New AI/ML Job(s) — {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}"

    lines = [f"Found {len(new_jobs)} new job posting(s) matching your criteria:\n"]
    for job in new_jobs:
        lines.append(f"Company:  {job['company']}")
        lines.append(f"Title:    {job['title']}")
        lines.append(f"Location: {job['location']}")
        lines.append(f"Posted:   {job['posted']}")
        lines.append(f"Apply:    {job['url']}")
        lines.append("-" * 50)

    msg = MIMEMultipart()
    msg["From"] = sender
    msg["To"] = recipient
    msg["Subject"] = subject
    msg.attach(MIMEText("\n".join(lines), "plain"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender, password)
        server.sendmail(sender, recipient, msg.as_string())

    print(f"Email sent: {len(new_jobs)} new jobs.")


def main():
    seen = load_seen_jobs()
    all_jobs = (
        scrape_greenhouse("deepmind", "Google DeepMind")
        + scrape_ashby("cohere", "Cohere")
    )
    new_jobs = [j for j in all_jobs if j["id"] not in seen]

    print(f"Total relevant jobs found: {len(all_jobs)} | New: {len(new_jobs)}")

    if new_jobs:
        send_email(new_jobs)
        for job in new_jobs:
            seen[job["id"]] = {
                "title": job["title"],
                "company": job["company"],
                "first_seen": datetime.now().isoformat(),
            }
        save_seen_jobs(seen)
    else:
        print("No new jobs. Nothing to send.")


if __name__ == "__main__":
    main()
