import os
import b4
import requests
import asyncio
import random
from playwright.sync_api import sync_playwright
from browserbase import Browserbase
from dotenv import load_dotenv

# types
from typing import List, Union, Dict, Optional
from dataclasses import dataclass

from urllib.parse import urljoin
from aiohttp import ClientSession
from fastapi import HTTPException
from fastapi import status as http_status
from playwright.async_api import async_playwright, Browser, Page, BrowserContext

# CONFIGURE LOGGING
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# load dotenv
load_dotenv()

# HOLDS ALL INFORMATION SCRAPED FROM WEBSITE
@dataclass
class ScrapingResult:
    url: str
    screenshots: Dict[str, str]  # base64 images
    dom_structure: str
    extracted_css: Dict[str, any]
    typography: Dict[str, any]
    color_palette: List[str]
    layout_info: Dict[str, any]
    assets: Dict[str, str] # urls
    metadata: Dict[str, any]
    raw_html: str
    success: bool
    error_message: Optional[str] = None
    
class WebScrape:
    logger("scraping website")
    
    def create_session():
        bb = Browserbase(api_key=os.environ["BROWSERBASE_KEY"])
        session = bb.sessions.create(
            project_id=os.environ["BROWSERBASE_ID"],
        )
        return session

    
    def __init__(self, use_browserbase: bool = True, browserbase_api_key: str = ""):
        self.use_browserbase = use_browserbase
        self.browserbase_api_key = browserbase_api_key
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        
    async def scrape_website(self, url: str, max_retries: int = 3) -> ScrapingResult:
        for attempt in range(max_retries):
            try:
                logger.info(f"attempt {attempt} for {url} ")
                
                if not self._is_valid_url(url):
                    return self._create_error_result();
                
                await self._initialize_browser()

                result = await self._perform_scraping(url)
                
                if result.success:
                    return result
                
            except Exception as e:
                logger.error(f"Scraping attempt {attempt + 1} failed: {str(e)}")
                if attempt == max_retries - 1:
                    return self._create_error_result();
                
                
                # sleep
                jitter = random.uniform(0, 1)
                await asyncio.sleep((2 ** attempt) + jitter) 
            finally:
                await self._cleanup_browser()
        
        # fallback failure
        return ScrapingResult(
            url=url, screenshots={}, dom_structure="", 
            extracted_css={}, color_palette=[], typography={}, 
            layout_info={}, assets={}, metadata={}, raw_html={},
            success=False, error_message="Max retries exceeded"
        )
        
    async def _initialize_browser(self):
        try:
            playwright = await async_playwright().start()
            
            if self.use_browserbase and self.browserbase_api_key:
                # Connect to Browserbase
                self.browser = await playwright.chromium.connect_over_cdp(
                    f"wss://connect.browserbase.com?apiKey={self.browserbase_api_key}"
                )
            else:
                # Launch local browser
                self.browser = await playwright.chromium.launch(
                    headless=True,
                    args=[
                        '--no-sandbox',
                        '--disable-dev-shm-usage',
                        '--disable-gpu',
                        '--disable-web-security',
                        '--disable-features=VizDisplayCompositor'
                    ]
                )
            
            # Create context with mobile user agent for better compatibility
            self.context = await self.browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            
        except Exception as e:
            logger.error(f"Browser initialization failed: {str(e)}")
            raise
        
    async def _perform_scraping(self, url: str) -> ScrapingResult:
        try:
            session = self.createSession()
                
            if session.status_code != 200:
                raise Exception(f"Failed to create Browserbase session: {session.text}")
                
            print(f"View session replay at https://browserbase.com/sessions/{session.id}")

            with sync_playwright() as p:
            
                browser = await p.chromium.launch(
                    headless=True,                  
                    args=[
                        '--no-sandbox',
                        '--disable-dev-shm-usage',
                        '--disable-gpu',
                        '--disable-web-security',
                        '--disable-features=VizDisplayCompositor'
                    ])
                page = await browser.new_page()
                                
                # Navigate to the form page
                page.goto(url)

                # Extract the books from the page
                items = page.locator('article.product_pod')
                books = items.all()

                book_data_list = []
                for book in books:

                    book_data = {
                        "title": book.locator('h3 a').get_attribute('title'),
                        "price": book.locator('p.price_color').text_content(),
                        "image": book.locator('div.image_container img').get_attribute('src'),
                        "inStock": book.locator('p.instock.availability').text_content().strip(),
                        "link": book.locator('h3 a').get_attribute('href')
                    }
                    
                    book_data_list.append(book_data)

                print("Shutting down...")
                page.close()
                browser.close()

                return book_data_list
            
        except Exception as e:
            logger("placeholder")
            
            
            
     # ERROR RESULT       
    def _create_error_result(self, url: str, error_message: str) -> ScrapingResult: 
        return ScrapingResult(
            url=url, screenshots={}, dom_structure="", 
            extracted_css={}, color_palette=[], typography={}, 
            layout_info={}, assets={}, metadata={}, 
            success=False, error_message=error_message
        )
                 
    
    # BROWSER CLEANUP
    async def _cleanup_browser(self):
        """Clean up browser resources"""
        try:
            if self.context:
                await self.context.close()
                self.context = None
            if self.browser:
                await self.browser.close()
                self.browser = None
        except Exception as e:
            logger.error(f"Browser cleanup failed: {str(e)}")
        
        
        
    
    

# async def get_html(url: str) -> b4.BeautifulSoup:
#     async with ClientSession() as session:
#         async with session.get(url) as response:
#             text = await response.text()

#             if response.status == 200:
#                 html = b4.BeautifulSoup(markup=text, features="lxml")

#                 return html

#     raise HTTPException(status_code=http_status.HTTP_501_NOT_IMPLEMENTED,
#                         detail=f"Scraper didn't succeed in getting data:\n"
#                                f"\turl: {url}\n"
#                                f"\tstatus code: {response.status}\n"
#                                f"\tresponse text: {text}")
    
    
    