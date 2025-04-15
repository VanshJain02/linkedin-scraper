import asyncio
import random
import pytz
from datetime import datetime, timedelta
from linkedin_scrapper import scrape_linkedin_jobs, convert_posted_time_to_datetime, format_posted_time_local  # Reuse your defined scraper logic
from companyinfo_scrapper import scrape_referral_profile 

import firebase_admin
from firebase_admin import credentials, firestore

def initialize_firebase():
    try:
        if not firebase_admin._apps:
            cred = credentials.Certificate('service-account.json')
            firebase_admin.initialize_app(cred)
        return firestore.client()
    except Exception as e:
        print(f"Firebase initialization error: {str(e)}")
        raise


# Initialize Firestore client
firestore_client = initialize_firebase()


import requests
import json

def send_jobs_to_webapp(jobs_data, webapp_url):
    """
    Send job data to a Google Apps Script web app.
    
    Args:
        jobs_data: List of job dictionaries
        webapp_url: URL of the deployed Google Apps Script web app
    
    Returns:
        Response from the web app
    """
    # Prepare the payload
    payload = {
        "jobs": jobs_data
    }
    
    # Convert to JSON
    json_payload = json.dumps(payload)
    
    # Set headers
    headers = {
        "Content-Type": "application/json"
    }
    
    # Send the POST request
    response = requests.post(webapp_url, data=json_payload, headers=headers)
    
    # Return the response
    return response.json()


# Define your target queries and role type filters
JOB_QUERIES = [[
    ("sde intern", "Internship"),
    ("software developer intern", "Internship"),
    ("machine learning intern", "Internship"),
    ("backend developer intern", "Internship"),
    ("full stack developer intern", "Internship"),
    ("frontend developer intern", "Internship"),
    ("data scientist intern", "Internship"),
    ('"software" "intern"', "Internship"),
    ('"software" "developer"', "Internship"),
    ("software engineer intern", "Internship"),
    ("software development engineer intern", "Internship")],[
    ("frontend developer", "Full-time"),
("software development engineer", "Full-time"),
    ("software developer", "Full-time"),
    ('"software"', "Full-time"),
    ("software engineer", "Full-time"),
    ("frontend developer", "Full-time"),
    ("backend developer", "Full-time")]
]

# Define your collection
COLLECTION_NAME = "linkedin_jobs"

# Function to check if job already exists based on URL
# async def job_exists(job_url):
#     docs = firestore_client.collection(COLLECTION_NAME).where("url", "==", job_url).stream()
#     return any(True for _ in docs)

# Save job to Firestore
async def save_job(job_data):
    firestore_client.collection(COLLECTION_NAME).add(job_data)
def save_job_to_firestore(job, firestore_client):
    job_type = job.get("type", "Unknown").replace(" ", "-")
    job_id = f"{job['title']}_{job['company']}_{job['location']}".replace(" ", "_").replace("/", "_")
    job_data = {
        **job,
        "timestamp": firestore.SERVER_TIMESTAMP
    }
    
    doc_ref = firestore_client.collection("jobs").document(job_id)
    if not doc_ref.get().exists:
        doc_ref.set(job_data)
        normalized_name = job_data['company'].strip().lower()
        company_ref = firestore_client.collection('companies').document(normalized_name)
        if not company_ref.get().exists:
            company_ref.set({
                'display_name': job_data['company'].title(),
                'first_seen': firestore.SERVER_TIMESTAMP,
                'last_updated': firestore.SERVER_TIMESTAMP
            })
            print(f"Added new company: {normalized_name}")
            try:
                print(f"Starting referral scrape for {normalized_name}")

                import threading
                t = threading.Thread(target=scrape_referral_profile, args=(normalized_name,))
                t.start
                # scrape_referral_profile(normalized_name)  # Make sure this function is imported/defined
            except Exception as e:
                print(f"Failed to scrape referrals: {str(e)}")

        print(f"[+] Saved new job to Firestore: {job['title']} | {job['company']}")
        # WEBAPP_URL = "https://script.google.com/macros/s/AKfycbwSOLJuSHVnEPzjFuxC4zcMfxJbxLoWKMkk96Yc64uImj4qeNCurvC-v6Lcc6MNy6WecA/exec"
        # try:
        #     send_jobs_to_webapp(job, WEBAPP_URL)
        # except Exception as e:
        #     return
    else:
        print(f"[=] Skipped duplicate job: {job['title']} ({job_type})")
# Run scraper for a single query-role pair
async def run_single_scrape(query, role_type):
    print(f"[SCRAPE] Running for: {query} | {role_type}")
    apply_filter_bool = random.choice([True,False])
    limit_option = random.choice([30,40])

    jobs = await scrape_linkedin_jobs(query=query, location="United States", role_type_filter=role_type,limit=limit_option,apply_job_type_filter=apply_filter_bool)

    for job in jobs:
        # if await job_exists(job["url"]):
        #     print(f"[SKIP] Duplicate job: {job['title']}")
        #     continue

        # Convert posting time to UTC and local time
        try:
            utc_time = convert_posted_time_to_datetime(job["posted"])
            job["posted"] = utc_time.isoformat()
            job["posted_local"] = format_posted_time_local(utc_time, timezone_str="America/New_York")
        except:
            job["posted_local"] = job["posted"]

        save_job_to_firestore(job, firestore_client)

        # print(f"[SAVED] {job['title']} | {job['company']}")

# Random cron runner
# async def run_cron_scraper():
#     while True:
#         queries = random.choice(JOB_QUERIES)
#         print(queries)
#         for query, role in queries:
#             await run_single_scrape(query, role)

#         next_sleep = random.choice([900, 1800,3600,1500,1000,])  # 5m, 10m, 15m, 20m, 30m
#         print(f"[WAIT] Sleeping for {next_sleep // 60} minutes...")
#         await asyncio.sleep(next_sleep)

# if __name__ == "__main__":
    # asyncio.run(run_cron_scraper())
    # Remove the async def run_cron_scraper() and modify main:
if __name__ == "__main__":
    # Single execution for cloud environments
    # queries = random.choice(JOB_QUERIES)
    for queries in JOB_QUERIES:
        for query, role in queries:
            asyncio.run(run_single_scrape(query, role))

