import json
import random
import time
import re
from playwright.sync_api import sync_playwright
from supabase import create_client, Client
from firebase_admin import credentials, initialize_app
from firebase_admin import firestore
import re
from urllib.parse import quote

import os

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")


supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


cred = credentials.Certificate('service-account.json')
initialize_app(cred)

# Initialize Firestore
db = firestore.client()


# Initialize Firestore
def human_like_interaction(page):
    """Simulate human-like behavior to avoid detection"""
    # Random mouse movement
    page.mouse.move(
        random.randint(0, 1000),
        random.randint(0, 600)
    )
    
    # Random scrolling
    scroll_amount = random.randint(300, 800)
    page.mouse.wheel(0, scroll_amount)
    
    # Random pauses between actions
    time.sleep(random.uniform(0.5, 2.5))


import json
from pathlib import Path

FAILED_COMPANIES_FILE = "failed_companies.json"
COMPANIES_CACHE_FILE = "companies_cache.json"
def load_failed_companies():
    """Load failed companies from JSON file"""
    try:
        if Path(FAILED_COMPANIES_FILE).exists():
            with open(FAILED_COMPANIES_FILE, 'r') as f:
                return json.load(f)
        return []
    except Exception as e:
        print(f"Error loading failed companies: {str(e)}")
        return []

def update_failed_companies(company_name, reason):
    """Update failed companies JSON file"""
    try:
        failed = load_failed_companies()
        
        # Check if already exists
        existing = next((c for c in failed if c['company'].lower() == company_name.lower()), None)
        if not existing:
            failed.append({
                "company": company_name,
                "reason": reason,
                "timestamp": int(time.time())
            })
            with open(FAILED_COMPANIES_FILE, 'w') as f:
                json.dump(failed, f, indent=2)
            print(f"Added {company_name} to failed companies list")
    except Exception as e:
        print(f"Error updating failed companies: {str(e)}")

def save_companies_to_json(companies):
    """Save companies list to JSON file"""
    try:
        with open(COMPANIES_CACHE_FILE, 'w') as f:
            json.dump(companies, f)
        print(f"Saved {len(companies)} companies to cache file")
    except Exception as e:
        print(f"Error saving companies cache: {str(e)}")

def load_companies_from_json():
    """Load companies from JSON cache file"""
    try:
        if Path(COMPANIES_CACHE_FILE).exists():
            with open(COMPANIES_CACHE_FILE, 'r') as f:
                return json.load(f)
        return None
    except Exception as e:
        print(f"Error loading companies cache: {str(e)}")
        return None
    

def load_linkedin_session():
    """Load LinkedIn session cookies from file"""
    try:
        with open("state_main.json", "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading session: {str(e)}")
        return None
    


def scrape_company_profiles(company_name, min_profiles=50, max_profiles=70):
    company_slug = company_name.lower().replace(" ", "-")
    base_url = f"https://www.linkedin.com/company/{company_slug}/people/"
    
    with sync_playwright() as p:
        # Launch browser with anti-detection features
        browser = p.chromium.launch(
            headless=True,  # Set to True for production
            args=[
                '--disable-blink-features=AutomationControlled',
                '--start-maximized'
            ]
        )
        
        # Load session state with cookies
        session_state = load_linkedin_session()
        context = browser.new_context(
            storage_state=session_state,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            viewport={'width': 1920, 'height': 1080}
        )
        
        page = context.new_page()
        profiles = []
        
        try:
            # Navigate to people page
            print(f"Navigating to {base_url}")
            page.goto(base_url, timeout=60000)
            
            # Wait for page to load
            # page.wait_for_load_state('networkidle', timeout=30000)
            
            # Give the page extra time to fully render
            time.sleep(5)
            
            # Check if we need to log in or if there's an error message
            if page.query_selector('.artdeco-empty-state__message'):
                print("No access to company people page or empty results")
                reason = "Page not found or access denied"

                update_failed_companies(company_name, reason)

                return profiles
            
            # Look for "People you may know" section - using exact class from screenshot
            print("Searching for profile elements...")
            
            # Using the exact DOM structure from the screenshot
            # people_section = page.query_selector("div[data-artdeco-is-focused='true']")
                    #  Try several selector patterns to find the section
            people_section_selectors = [
                "h2:text('People you may know')",
                "div:has(h2:text('People you may know'))",
                "div.artdeco-card.org-people-profile-card__card-spacing"
            ]
            
            people_section = None
            for selector in people_section_selectors:
                people_section = page.query_selector(selector)
                if people_section:
                    print(f"Found people section using selector: {selector}")
                    break
            
            if not people_section:
                people_section = page.query_selector("div:has(h2:text('People you may know'))")
            
            if not people_section:
                print("Could not find people section")
                reason = "Could not find people section"
                update_failed_companies(company_name, reason)
                return profiles
                
            print("Found people section. Starting to collect profiles...")
            
            collected_profiles = []
            click_attempts = 0
            max_click_attempts = 6  # Maximum number of "Show more" clicks to try
            
            # Loop until we have enough profiles or reach maximum attempts
            if len(collected_profiles) < min_profiles and click_attempts < max_click_attempts:
                # Scroll to load content
                human_like_interaction(page)
                profile_cards = page.query_selector_all("li.org-people-profile-card__profile-card-spacing")
                    
                print(f"Found {len(profile_cards)} profile cards in this batch")

                while len(profile_cards)<min_profiles and click_attempts<=max_click_attempts:
                        # Look for "Show more results" button using exact classes from screenshot
                    
                    show_more_button = page.query_selector("button.artdeco-button.artdeco-button--muted.artdeco-button--1.artdeco-button--full.artdeco-button--secondary.ember-view.scaffold-finite-scroll__load-button")

                    
                    if not show_more_button:
                        # Try with text content
                        show_more_button = page.query_selector("button:has-text('Show more results')")
                    
                    if show_more_button and show_more_button.is_visible():
                        print("Found 'Show more results' button")
                        
                        # Scroll to make button visible
                        show_more_button.scroll_into_view_if_needed()
                        time.sleep(random.uniform(1, 2))
                        
                        print("Clicking 'Show more results' button")
                        show_more_button.click()
                        
                        # Wait for new content to load
                        time.sleep(random.uniform(2, 4))
                        click_attempts += 1
                        print(f"Clicked 'Show more results' button ({click_attempts}/{max_click_attempts})")
                    else:
                        print("No 'Show more results' button found or it's not visible")
                        # html = page.content()
                        # print(html)  
                        # Scroll to the bottom of the page to try to trigger loading more content
                        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                        time.sleep(3)
                        
                        # If after scrolling we still don't find the button, break the loop
                        show_more_button = page.query_selector("button:has-text('Show more results')")
                        if not show_more_button:
                            print("No more results available")
                            break
                    profile_cards = page.query_selector_all("li.org-people-profile-card__profile-card-spacing")
                    print(f"Found {len(profile_cards)} profile cards in this batch")

                # Process current batch of profile cards
                for card in profile_cards:
                    try:
                        # Find profile link inside the card
                        profile_link = card.query_selector("a[href*='/in/']")
                        
                        if not profile_link:
                            continue
                            
                        href = profile_link.get_attribute('href')
                        
                        # Extract the clean profile URL using regex
                        match = re.search(r'(https://www\.linkedin\.com/in/[^?]+)', href)
                        if not match:
                            # Alternative extraction if full URL isn't in href
                            match = re.search(r'/in/([^?]+)', href)
                            if match:
                                profile_url = f"https://www.linkedin.com/in/{match.group(1)}"
                            else:
                                continue
                        else:
                            profile_url = match.group(1)
                        
                        # Skip if we already have this profile
                        if profile_url in [p.get('url') for p in collected_profiles]:
                            continue
                            
                        # Try to extract the name
                        name_element = card.query_selector(".artdeco-entity-lockup__title") or \
                                      card.query_selector(".org-people-profile-card__profile-title") or \
                                      card.query_selector("span[aria-hidden='true']")
                        
                        name = "Unknown LinkedIn User"
                        if name_element:
                            name = name_element.inner_text().strip()
                        
                        collected_profiles.append({
                            'name': name,
                            'url': profile_url,
                            'company': company_name,
                            'timestamp': int(time.time())
                        })
                        
                        print(f"Found: {name} - {profile_url}")
                        
                        # Stop if we've reached the maximum number of profiles
                        if len(collected_profiles) >= max_profiles:
                            break
                            
                    except Exception as e:
                        print(f"Error processing profile card: {str(e)}")
                        continue
                
                print(f"Collected {len(collected_profiles)} unique profiles so far")
                
                # If we have enough profiles, break the loop
              
            
            # Final results
            profiles = collected_profiles[:max_profiles]  # Limit to max_profiles
            
            # Save to Firebase
            if profiles:
                            # Upsert the company into "companies" table
                print("SAVING DATA TO SUPABASE")
                company_data = {
                    "name": company_name.lower(),
                    "timestamp": int(time.time())
                }
                company_result = None
                try:
                    company_result = supabase.table("companies").upsert(company_data, on_conflict=["name"]).execute()
                except Exception as e:
                    print("Error upserting company data:",e)
                # Get company ID
                if company_result and len(company_result.data) > 0:
                    company_id = company_result.data[0]['id']
                     # Optional: Delete old people data for the company
                    try:
                        supabase.table("people").delete().eq("company_id", company_id).execute()
                        
                    except Exception as e:
                        print("Exceeption: ",e)
                    try:
                        for profile in profiles:
                            profile["company_id"] = company_id
                    except Exception as e:
                        print("Exceeption profile: ",e)
                else:
                    print(f"Failed to upsert/find company ID for {company_name}")
                    return profiles
                # Insert new people
                try:
                    supabase.table("people").insert(profiles).execute()
                except Exception as e:
                    print(e)

                print(f"Saved {len(profiles)} profiles to Supabase for company {company_name}")
                if len(profiles) < 5:
                    reason = f"Insufficient profiles ({len(profiles)})"
                    update_failed_companies(company_name, reason)
            else:
                print(f"No profiles found for {company_name}")
                
        except Exception as e:
            print("Critical error during scraping: ",e)
        finally:
            # Clean up
            context.close()
            browser.close()
            
        return profiles
    


# Add these functions to manage company list
def create_companies_collection():
    """One-time function to create companies collection from existing jobs"""
    companies_ref = db.collection('companies')
    seen_companies = set()
    
    try:
        # Get all jobs
        jobs = db.collection('jobs').stream()
        
        for job in jobs:
            data = job.to_dict()
            raw_company = data.get('company') or data.get('companyName', '')
            
            if not raw_company:
                continue
                
            # Sanitize company name for Firestore document ID
            sanitized_company = sanitize_firestore_id(raw_company)
            
            if sanitized_company and sanitized_company not in seen_companies:
                # Create document with sanitized ID
                companies_ref.document(sanitized_company).set({
                    'display_name': raw_company.strip().title(),
                    'original_name': raw_company.strip(),
                    'last_updated': firestore.SERVER_TIMESTAMP
                })
                seen_companies.add(sanitized_company)
                
        print(f"Created {len(seen_companies)} companies in collection")
    
    except Exception as e:
        print(f"Error creating companies collection: {str(e)}")

def sanitize_firestore_id(text):
    """Sanitize text to be Firestore document ID safe"""
    # Remove forbidden characters
    sanitized = re.sub(r'[\/\.\$#\[\]]', '-', text.strip().lower())
    # Trim to 1500 characters (Firestore limit)
    return sanitized[:1500]

def get_unique_companies():
    """Retrieve unique companies from optimized collection"""
    try:
        companies_ref = db.collection('companies')
        docs = companies_ref.select(['display_name']).stream()
        return [doc.get('display_name') for doc in docs]
    
    except Exception as e:
        print(f"Error getting companies: {str(e)}")
        return []

# Add this to your main scraping function when saving new jobs
def update_companies_collection(company_name):
    """Maintain companies collection when adding new jobs"""
    normalized_name = company_name.strip().lower()
    
    try:
        company_ref = db.collection('companies').document(normalized_name)
        
        if not company_ref.get().exists:
            company_ref.set({
                'display_name': company_name.title(),
                'first_seen': firestore.SERVER_TIMESTAMP,
                'last_updated': firestore.SERVER_TIMESTAMP
            })
            print(f"Added new company: {normalized_name}")
        else:
            company_ref.update({
                'last_updated': firestore.SERVER_TIMESTAMP
            })
            
    except Exception as e:
        print(f"Error updating companies collection: {str(e)}")


def format_linkedin_company_url(company_name):
    """
    Convert company names to LinkedIn's URL format:
    - Lowercase
    - Replace spaces with hyphens
    - Remove special characters
    - Preserve Inc/LLC suffixes
    """
    # Remove special characters
    clean_name = re.sub(r'[\.\',]', '', company_name.strip())
    
    # Replace special cases
    clean_name = clean_name.replace('&', 'and').replace('+', 'and')
    
    # Convert to lowercase and hyphenate
    formatted = clean_name.lower().replace(' ', '-')
    
    # Handle common suffixes
    formatted = re.sub(r'-+inc$', '-inc', formatted)
    formatted = re.sub(r'-+llc$', '-llc', formatted)
    formatted = re.sub(r'-+ltd$', '-ltd', formatted)
    
    # Remove double hyphens
    formatted = re.sub(r'-+', '-', formatted)
    
    # URL encode special characters
    return f"{quote(formatted)}"

# Modified scrape_referral_profile function
def scrape_referral_profile(normalized_name, original_name):
    """Scrape company referrals with proper resource isolation"""
    try:
        # Reinitialize Firebase for this process
        if not firebase_admin._apps:
            cred = credentials.Certificate('service-account.json')
            firebase_admin.initialize_app(cred)
        
        # Reinitialize Supabase
        supabase = create_client(os.environ['SUPABASE_URL'], 
                               os.environ['SUPABASE_SERVICE_KEY'])

        print(f"\nStarting deep scrape for {original_name}")
        profiles = scrape_company_profiles(original_name)  # Use original name
        
        if profiles:
            print(f"Discovered {len(profiles)} profiles for {original_name}")
            # Delete old entries
            existing = supabase.table("companies").select("id").eq("name", normalized_name).execute()
            if existing.data:
                supabase.table("people").delete().eq("company_id", existing.data[0]['id']).execute()
            
            # Insert new profiles
            supabase.table("people").insert(profiles).execute()
            print(f"Updated {len(profiles)} profiles for {original_name}")
        else:
            print(f"No profiles found for {original_name}")
            supabase.table("companies").delete().eq("name", normalized_name).execute()
            print(f"Cleaned up company record for {original_name}")

    except Exception as e:
        print(f"REFERRAL SCRAPE ERROR ({original_name}): {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # companies = get_unique_companies()
    # save_companies_to_json(companies=companies)
    companies = load_companies_from_json()
    formatted_company_names = [format_linkedin_company_url(c) for c in companies]

    for company in formatted_company_names:
        # Check if company exists in Supabase
        existing_check = supabase.table("companies") \
            .select("id") \
            .eq("name", company.lower()) \
            .execute()
        
        if len(existing_check.data) > 0:
            print(f"Company {company} already exists in database. Skipping...")
            continue
            
        print(f"\nStarting scrape for {company}")
        profiles = scrape_company_profiles(company)
        
        # Add delay between companies to avoid detection
        if len(profiles)>5:
            delay = random.randint(50, 180)  # 5-15 minutes
            print(f"Waiting {delay} seconds before next company...")
            time.sleep(delay)