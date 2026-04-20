import json
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import requests

KEYWORDS = ["AI Engineer", "Machine Learning Engineer", "Data Scientist", "Software Engineer"]
ML_AI_TERMS = ["machine learning", " ml ", "ai ", "artificial intelligence", "deep learning", "nlp", "llm", "generative"]
ENTRY_LEVEL_TERMS = ["entry", "junior", "new grad", "0-2", "1-2", "early career", "university grad", "associate"]
SEEN_JOBS_FILE = "scraper/jobs_seen.json"


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
    for kw in KEYWORDS:
        if kw.lower() in title_lower:
            # "Software Engineer" alone isn't enough — must have ML/AI context in title
            if kw.lower() == "software engineer":
                if any(term in title_lower for term in ML_AI_TERMS):
                    return True
            else:
                return True
    return False


def scrape_google():
    jobs = []
    seen_ids = set()
    search_terms = ["machine learning engineer", "data scientist", "AI engineer", "software engineer AI"]

    for term in search_terms:
        url = "https://careers.google.com/api/v3/search/"
        params = {
            "q": term,
            "jex": "ENTRY_LEVEL",
            "page_size": 100,
        }
        try:
            resp = requests.get(url, params=params, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
            resp.raise_for_status()
            data = resp.json()
            for job in data.get("jobs", []):
                job_id = str(job.get("id", ""))
                if job_id in seen_ids:
                    continue
                seen_ids.add(job_id)
                title = job.get("title", "")
                if is_relevant_title(title):
                    locations = [loc.get("display", "") for loc in job.get("locations", [])]
                    jobs.append({
                        "id": f"google_{job_id}",
                        "company": "Google",
                        "title": title,
                        "location": ", ".join(locations),
                        "url": f"https://careers.google.com/jobs/results/{job_id}",
                        "posted": job.get("publish_date", ""),
                    })
        except Exception as e:
            print(f"[Google] Error scraping '{term}': {e}")

    return jobs


def scrape_cohere():
    jobs = []
    url = "https://boards-api.greenhouse.io/v1/boards/cohere/jobs"
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        for job in data.get("jobs", []):
            title = job.get("title", "")
            job_id = str(job.get("id", ""))
            if is_relevant_title(title):
                jobs.append({
                    "id": f"cohere_{job_id}",
                    "company": "Cohere",
                    "title": title,
                    "location": job.get("location", {}).get("name", ""),
                    "url": job.get("absolute_url", ""),
                    "posted": job.get("updated_at", ""),
                })
    except Exception as e:
        print(f"[Cohere] Error: {e}")

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
    all_jobs = scrape_google() + scrape_cohere()
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
