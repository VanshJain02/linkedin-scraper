

from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import json
import os


def categorize_job_type(title: str, description: str = ""):
    # combined = (title + " " + description).lower()
    combined = title.lower()
    if "intern" in combined or "internship" in combined or "summer trainee" in combined:
        return "Internship"
    if "co-op" in combined or "coop" in combined:
        return "Co-op"
    if "full-time" in combined or "full time" in combined:
        return "Full-time"
    if "part-time" in combined or "part time" in combined:
        return "Part-time"
    if "contract" in combined or "temporary" in combined:
        return "Contract"
    return "Full-time"

role_filter_map = {
    "Internship": "I",
    "Full-time": "F",
    "Part-time": "P",
    "Contract": "C",
    "Co-op": "4"
}

from datetime import datetime, timedelta
import re

def convert_posted_time_to_datetime(posted_str: str, reference_time: datetime = None) -> datetime:
    """
    Converts relative time like '5 minutes ago', '2 hours ago', '1 day ago' to a UTC datetime object.
    """
    if not reference_time:
        reference_time = datetime.utcnow()

    posted_str = posted_str.lower().strip()
    
    time_map = {
        "minute": "minutes",
        "minutes": "minutes",
        "hour": "hours",
        "hours": "hours",
        "day": "days",
        "days": "days",
        "week": "weeks",
        "weeks": "weeks",
    }

    match = re.search(r"(\d+)\s+(minute|minutes|hour|hours|day|days|week|weeks)", posted_str)
    if match:
        num = int(match.group(1))
        unit = time_map.get(match.group(2), "minutes")
        delta = timedelta(**{unit: num})
        return reference_time - delta

    if "just now" in posted_str or "moments ago" in posted_str:
        return reference_time

    return reference_time  # default fallback

import pytz

def format_posted_time_local(dt_utc: datetime, timezone_str: str = "America/New_York") -> str:
    """
    Converts a UTC datetime to the specified timezone and formats it.
    Example: "Mar 29, 2025 at 07:45 AM"
    """
    try:
        local_tz = pytz.timezone(timezone_str)
    except pytz.UnknownTimeZoneError:
        local_tz = pytz.utc

    dt_local = dt_utc.replace(tzinfo=pytz.utc).astimezone(local_tz)
    return dt_local.strftime("%b %d, %Y at %I:%M %p")


async def scrape_linkedin_jobs(query="software engineer", location="India", target_titles=None, role_type_filter=None, limit=50,apply_job_type_filter=True):
    # base_url = "https://www.linkedin.com/jobs/search/?keywords={query}&location={location}&f_TPR=r86400&sortBy=DD&start={start}"
    jt_filter = role_filter_map.get(role_type_filter)
    jt_query_param = f"&f_JT={jt_filter}" if jt_filter and apply_job_type_filter else ""

    base_url = f"https://www.linkedin.com/jobs/search/?keywords={{query}}&location={{location}}&f_TPR=r86400&sortBy=DD{jt_query_param}&start={{start}}"


    jobs = []
    if target_titles is None:
        target_titles = [query.lower()]
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(storage_state="state.json")
        page = await context.new_page()

        collected = 0
        start = 0

        while collected < limit:
            url = base_url.format(query=query.replace(" ", "%20"), location=location.replace(" ", "%20"), start=start)
            print(url)
            await page.goto(url)
            # 
            await page.wait_for_timeout(500)

            for _ in range(5):
                await page.mouse.wheel(0, 3000)
                await page.wait_for_timeout(400)

            try:
                await page.wait_for_selector("li.ember-view[data-occludable-job-id]", timeout=10000)
            except:
                print("[WARN] No job cards found on page", start // 25 + 1)
                break

            job_cards = await page.query_selector_all(
                "li.ember-view[data-occludable-job-id], li.ember-view div[data-job-id]"
            )

            print(f"[INFO] Page {(start // 25) + 1}: Found {len(job_cards)} job cards.")

            for i, card in enumerate(job_cards):
                if collected >= limit:
                    break
                try:
                    await card.scroll_into_view_if_needed()
                    await page.wait_for_timeout(100)

                    title_el = await card.query_selector("a.job-card-container__link span[aria-hidden='true']")
                    company_el = await card.query_selector("div.artdeco-entity-lockup__subtitle span")
                    location_el = await card.query_selector("ul.job-card-container__metadata-wrapper li")
                    link_el = await card.query_selector("a.job-card-container__link")
                

                    title = await title_el.inner_text() if title_el else "[NOT FOUND]"
                    company = await company_el.inner_text() if company_el else "[NOT FOUND]"
                    job_location = await location_el.inner_text() if location_el else "[NOT FOUND]"
                    job_url = await link_el.get_attribute("href") if link_el else ""

                    print(f"[{collected + 1}] {title} | {company} | {location} | {job_url}")

                    if True:
                        job_page = await context.new_page()
                        await job_page.goto(f"https://www.linkedin.com{job_url}" if job_url.startswith("/") else job_url)
                        await job_page.wait_for_timeout(1000)

                        try:
                            repost_flag = await job_page.query_selector("div.job-details-jobs-unified-top-card__primary-description-container strong")
                            if repost_flag:
                                repost_text_detail = await repost_flag.inner_text()
                                if "Reposted" in repost_text_detail:
                                    await job_page.close()
                                    continue
                        except:
                            pass

                        posted_time = None
                        try:
                            posted_span = await job_page.query_selector("div.job-details-jobs-unified-top-card__primary-description-container strong span")
                            if posted_span:
                                posted_time = await posted_span.inner_text()
                        except:
                            pass

                        description = ""
                        try:
                            await job_page.wait_for_selector('article.jobs-description__container p[dir="ltr"]', timeout=2000)
                            desc_blocks = await job_page.query_selector_all('article.jobs-description__container p[dir="ltr"]')
                            description = "\n".join([await el.inner_text() for el in desc_blocks])

                        except:
                            print("[WARN] Primary HTML description fetch failed.")
                       
                        await job_page.close()

                        job_type = categorize_job_type(title, description)
                        # print("Type:", job_type)
                        # if role_type_filter and job_type.lower() != role_type_filter.lower():
                        #     continue

                        jobs.append({
                            "title": title.strip(),
                            "title_lower": title.strip().lower(),
                            "company": company.strip(),
                            "company_lower": company.strip().lower(),
                            "location": job_location.strip(),
                            "url": f"https://www.linkedin.com{job_url}" if job_url.startswith("/") else job_url,
                            "posted": posted_time,
                            "type": job_type,
                            "description": description.strip()
                        })
                        
                        collected += 1

                except Exception as e:
                    print(f"[ERROR] Could not extract job #{collected + 1}: {e}")
                    continue

            start += 25

        await browser.close()
    return jobs


import asyncio

if __name__ == "__main__":
    async def main():
        jobs = await scrape_linkedin_jobs(
            query="software engineer",
            location="United States",
            limit=40,  # For testing purposes
            role_type_filter="Full-time"  # Optional
        )
        print(json.dumps(jobs, indent=2))

    asyncio.run(main())