import asyncio
from playwright.async_api import async_playwright

LINKEDIN_EMAIL = "tekhnite@gmail.com"
LINKEDIN_PASSWORD = "vanshdilip1@"

async def auto_save_login_state():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        await page.goto("https://www.linkedin.com/login")

        # Fill in the username and password
        await page.fill('input#username', LINKEDIN_EMAIL)
        await page.fill('input#password', LINKEDIN_PASSWORD)

        # Make sure "Remember me" is checked
        remember_checkbox = await page.query_selector('input#rememberMeOptIn-checkbox')
        if remember_checkbox:
            is_checked = await remember_checkbox.is_checked()
            if not is_checked:
                await remember_checkbox.check()

        # Click the login button
        await page.click('button[type="submit"]')

        # Wait for navigation to ensure login is successful
        await page.wait_for_url("https://www.linkedin.com/feed/", timeout=15000)

        # Save the authenticated session
        await context.storage_state(path="state.json")
        print("✅ Login successful and state saved to state.json.")
        await browser.close()


async def save_login_state():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)  # Open visible browser so you can log in
        context = await browser.new_context()
        page = await context.new_page()
        await page.goto("https://www.linkedin.com/login")

        print("🔐 Please log in manually within the opened browser window...")
        print("⏳ Waiting 60 seconds for login. You can close the browser window after login is complete.")
        await page.wait_for_timeout(60000)  # Wait 60 seconds to allow login

        await context.storage_state(path="state_main.json")
        print("✅ Login saved to state.json.")
        await browser.close()


asyncio.run(auto_save_login_state())
