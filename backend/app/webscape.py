import os
import requests
import asyncio
import random
from browserbase import Browserbase
from urllib.parse import urlparse
from dotenv import load_dotenv

# types
from typing import List, Dict, Optional
from dataclasses import dataclass

# from urllib.parse import urljoin
# from aiohttp import ClientSession
# from fastapi import HTTPException
# from fastapi import status as http_status
from playwright.async_api import async_playwright, Page

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
    logger.info("scraping website")
    
    def create_session():
        bb = Browserbase(api_key=os.getenv("BROWSERBASE_KEY"))
        session = bb.sessions.create(
            project_id=os.getenv("BROWSERBASE_ID"),
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
            # Create new page
            page = await self.context.new_page()
            
            # Set up request/response interception for better asset tracking
            requests_log = []
            
            async def handle_request(request):
                requests_log.append({
                    'url': request.url,
                    'resource_type': request.resource_type,
                    'method': request.method
                })
            
            page.on('request', handle_request)
            
            # Navigate to URL with timeout
            await page.goto(url, wait_until='networkidle', timeout=30000)
            
            # Wait for page to be fully loaded
            await page.wait_for_timeout(2000)
            
            # Take screenshots at different viewport sizes
            screenshots = await self._capture_screenshots(page)
            
            # Extract DOM structure
            dom_structure = await page.content()
            
            # Extract CSS information
            extracted_css = await self._extract_css_info(page)
            
            # Extract color palette
            color_palette = await self._extract_color_palette(page)
            
            # Extract typography
            typography = await self._extract_typography(page)
            
            # Extract layout information
            layout_info = await self._extract_layout_info(page)
            
            # Extract assets from requests and DOM
            assets = await self._extract_assets(page, requests_log, url)
            
            # Extract metadata
            metadata = await self._extract_metadata(page)
            
            # Extract metadata
            raw_html = await self._extract_raw_html(page)
            
            await page.close()
            
            return ScrapingResult(
                url=url,
                screenshots=screenshots,
                dom_structure=self._clean_dom(dom_structure),
                extracted_css=extracted_css,
                color_palette=color_palette,
                typography=typography,
                layout_info=layout_info,
                assets=assets,
                metadata=metadata,
                raw_html=raw_html,
                success=True
            )
            
        except Exception as e:
            logger.error(f"Scraping execution failed: {str(e)}")
            return self._create_error_result(url, str(e))
        
    async def _capture_screenshots(self, page: Page) -> Dict[str, str]:
        logger.info("capturing screenshot")
        return {
            "full_page": "screenshot_full_page.png",     
            "viewport": "screenshot_viewport.png"       
        }

    async def _extract_css_info(self, page: Page) -> Dict[str, any]:
        logger.info("extracting css")
        return {
            "body": {"margin": "0", "padding": "0", "font-family": "Arial"},
            ".header": {"background-color": "#ffffff", "height": "60px"},
            ".btn": {"background-color": "#e91e63", "color": "#ffffff", "padding": "10px 20px"}
        }

    async def _extract_color_palette(self, page: Page) -> List[str]:
        logger.info("extracting color")
        return ["#ffffff", "#000000", "#e91e63", "#03a9f4"]

    async def _extract_typography(self, page: Page) -> Dict[str, any]:
        logger.info("extracting typography")
        return {
            "title": "dummy title",
            "description": "dummy description",
            "url": "https://example.com"
        }

    async def _extract_layout_info(self, page: Page) -> Dict[str, any]:
        logger.info("extracting layout info")
        return {
            "header": {"x": 0, "y": 0, "width": 800, "height": 60},
            "main": {"x": 0, "y": 60, "width": 800, "height": 600},
            "footer": {"x": 0, "y": 660, "width": 800, "height": 100}
        }

    async def _extract_assets(self, page: Page, requests_log: List, base_url: str) -> Dict[str, List[str]]:
        logger.info("extracting assets")
        return {
            "images": [f"{base_url}/images/logo.png", f"{base_url}/images/banner.jpg"],  # dummy URLs
            "scripts": [f"{base_url}/js/app.js", f"{base_url}/js/vendor.js"],
            "stylesheets": [f"{base_url}/css/main.css", f"{base_url}/css/theme.css"]
        }

    async def _extract_raw_html(self, page: Page) -> str:  
        logger.info("extracting raw_html")
        return "<!DOCTYPE html><html><head><title>Dummy</title></head><body><p>Dummy HTML content</p></body></html>"

            
    # CHECK URL VALIDITY
    def _is_valid_url(self, url: str) -> bool:
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except:
            return False
            
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
    
    
    