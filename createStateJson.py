import asyncio
from playwright.async_api import async_playwright

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

asyncio.run(save_login_state())
