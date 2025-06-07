import os
import requests
import asyncio
import random
import base64
import logging
from browserbase import Browserbase
from urllib.parse import urlparse
from dotenv import load_dotenv
from bs4 import BeautifulSoup
# types
from typing import List, Dict, Optional
from dataclasses import dataclass
from playwright.async_api import async_playwright, Page

# CONFIGURE LOGGING
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
            metadata = await self._extract_metadata(page,requests_log, url)
            
            # Extract html
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
    
    # SCREENSHOT DATA FROM WEBSITE  
    async def _capture_screenshots(self, page: Page) -> Dict[str, str]:
        screenshots = {}
        
        viewports = {
            "desktop": {"width": 1920, "height": 1080},
            "tablet": {"width": 768, "height": 1024},
            "mobile": {"width": 375, "height": 667}
        }
        
        try:
            for viewport_name, viewport_size in viewports.items():
                # Set viewport
                await page.set_viewport_size(viewport_size)
                await page.wait_for_timeout(1000)
                
                # Take full page screenshot
                screenshot_bytes = await page.screenshot(
                    full_page=True,
                    type='png'
                )
                
                # Convert to base64
                screenshots[viewport_name] = base64.b64encode(screenshot_bytes).decode('utf-8')
                
        except Exception as e:
            logger.error(f"Screenshot capture failed: {str(e)}")
        
        return screenshots

    # CSS DATA FROM WEBSITE
    async def _extract_css_info(self, page: Page) -> Dict[str, any]:
        css_info = {
            "body_styles": {},
            "header_styles": {},
            "main_content_styles": {},
            "common_patterns": []
        }
        
        try:
            # Extract body styles
            body_styles = await page.evaluate("""
                () => {
                    const body = document.body;
                    const styles = window.getComputedStyle(body);
                    return {
                        'background-color': styles.backgroundColor,
                        'font-family': styles.fontFamily,
                        'font-size': styles.fontSize,
                        'line-height': styles.lineHeight,
                        'color': styles.color,
                        'margin': styles.margin,
                        'padding': styles.padding
                    };
                }
            """)
            css_info["body_styles"] = body_styles
            
            # Extract header styles if exists
            header_styles = await page.evaluate("""
                () => {
                    const header = document.querySelector('header');
                    if (!header) return null;
                    const styles = window.getComputedStyle(header);
                    return {
                        'background-color': styles.backgroundColor,
                        'height': styles.height,
                        'padding': styles.padding,
                        'position': styles.position,
                        'display': styles.display
                    };
                }
            """)
            if header_styles:
                css_info["header_styles"] = header_styles
            
            common_selectors = ["h1", "h2", "h3", "p", "a", "button", ".container", ".wrapper", "nav"]
            
            for selector in common_selectors:
                try:
                    element_styles = await page.evaluate(f"""
                        () => {{
                            const element = document.querySelector('{selector}');
                            if (!element) return null;
                            const styles = window.getComputedStyle(element);
                            return {{
                                'font-size': styles.fontSize,
                                'font-weight': styles.fontWeight,
                                'color': styles.color,
                                'margin': styles.margin,
                                'padding': styles.padding,
                                'display': styles.display,
                                'background-color': styles.backgroundColor
                            }};
                        }}
                    """)
                    
                    if element_styles:
                        css_info["common_patterns"].append({
                            "selector": selector,
                            "styles": element_styles
                        })
                        
                except Exception as e:
                    logger.debug(f"Failed to extract styles for {selector}: {str(e)}")
                    continue
                    
        except Exception as e:
            logger.error(f"CSS extraction failed: {str(e)}")
        
        return css_info

    async def _extract_color_palette(self, page: Page) -> List[str]:
        try:
            colors = await page.evaluate("""
                () => {
                    const colors = new Set();
                    const elements = document.querySelectorAll('*');
                    
                    // Limit to first 100 elements for performance
                    const elementsArray = Array.from(elements).slice(0, 100);
                    
                    elementsArray.forEach(element => {
                        const styles = window.getComputedStyle(element);
                        const bgColor = styles.backgroundColor;
                        const textColor = styles.color;
                        const borderColor = styles.borderColor;
                        
                        [bgColor, textColor, borderColor].forEach(color => {
                            if (color && 
                                color !== 'rgba(0, 0, 0, 0)' && 
                                color !== 'transparent' &&
                                color !== 'rgba(0, 0, 0, 0)' &&
                                !color.includes('rgba(0, 0, 0, 0)')) {
                                colors.add(color);
                            }
                        });
                    });
                    
                    return Array.from(colors).slice(0, 20);
                }
            """)
            
            return colors or []
            
        except Exception as e:
            logger.error(f"Color extraction failed: {str(e)}")
            return []
        
        
    async def _extract_typography(self, page: Page) -> Dict[str, any]:
        try:
            typography = await page.evaluate("""
                () => {
                    const fonts = new Set();
                    const headings = {};
                    const bodyText = {};
                    
                    // Extract font families
                    const elements = Array.from(document.querySelectorAll('*')).slice(0, 50);
                    elements.forEach(element => {
                        const fontFamily = window.getComputedStyle(element).fontFamily;
                        if (fontFamily) fonts.add(fontFamily);
                    });
                    
                    // Extract heading styles
                    for (let i = 1; i <= 6; i++) {
                        const heading = document.querySelector(`h${i}`);
                        if (heading) {
                            const styles = window.getComputedStyle(heading);
                            headings[`h${i}`] = {
                                'font-size': styles.fontSize,
                                'font-weight': styles.fontWeight,
                                'line-height': styles.lineHeight,
                                'margin': styles.margin,
                                'font-family': styles.fontFamily
                            };
                        }
                    }
                    
                    // Extract body text styles
                    const paragraph = document.querySelector('p');
                    if (paragraph) {
                        const styles = window.getComputedStyle(paragraph);
                        bodyText = {
                            'font-size': styles.fontSize,
                            'line-height': styles.lineHeight,
                            'font-weight': styles.fontWeight,
                            'font-family': styles.fontFamily
                        };
                    }
                    
                    return {
                        fonts: Array.from(fonts),
                        headings: headings,
                        body_text: bodyText
                    };
                }
            """)
            
            return typography
            
        except Exception as e:
            logger.error(f"Typography extraction failed: {str(e)}")
            return {"fonts": [], "headings": {}, "body_text": {}}

    async def _extract_layout_info(self, page: Page) -> Dict[str, any]:
        try:
            layout = await page.evaluate("""
                () => {
                    const structure = [];
                    const gridInfo = {};
                    
                    // Identify main structural elements
                    const structuralTags = ['header', 'nav', 'main', 'section', 'aside', 'footer', 'article'];
                    
                    structuralTags.forEach(tag => {
                        const elements = document.querySelectorAll(tag);
                        if (elements.length > 0) {
                            structure.push({
                                tag: tag,
                                count: elements.length,
                                classes: Array.from(elements).slice(0, 3).map(el => 
                                    el.className ? el.className.split(' ') : []
                                )
                            });
                        }
                    });
                    
                    // Check for grid/flexbox layouts
                    const allElements = Array.from(document.querySelectorAll('*')).slice(0, 30);
                    allElements.forEach(element => {
                        const styles = window.getComputedStyle(element);
                        const display = styles.display;
                        
                        if (display === 'grid' || display === 'flex') {
                            const tagName = element.tagName.toLowerCase();
                            const className = element.className || 'no-class';
                            
                            gridInfo[`${tagName}.${className}`] = {
                                display: display,
                                'justify-content': styles.justifyContent,
                                'align-items': styles.alignItems,
                                'grid-template-columns': styles.gridTemplateColumns,
                                'flex-direction': styles.flexDirection
                            };
                        }
                    });
                    
                    return {
                        structure: structure,
                        grid_info: gridInfo
                    };
                }
            """)
            
            return layout
            
        except Exception as e:
            logger.error(f"Layout extraction failed: {str(e)}")
            return {"structure": [], "grid_info": {}}

    
    async def _extract_assets(self, page: Page, requests_log: List, base_url: str) -> Dict[str, List[str]]:
        assets = {
            "images": [],
            "stylesheets": [],
            "fonts": [],
            "icons": [],
            "scripts": []
        }
        
        try:
            # Extract from DOM
            dom_assets = await page.evaluate("""
                () => {
                    const assets = {
                        images: [],
                        stylesheets: [],
                        fonts: [],
                        icons: [],
                        scripts: []
                    };
                    
                    // Images
                    document.querySelectorAll('img').forEach(img => {
                        if (img.src) assets.images.push(img.src);
                    });
                    
                    // Stylesheets
                    document.querySelectorAll('link[rel="stylesheet"]').forEach(link => {
                        if (link.href) assets.stylesheets.push(link.href);
                    });
                    
                    // Fonts
                    document.querySelectorAll('link').forEach(link => {
                        const href = link.href || '';
                        if (href.includes('fonts') || href.includes('font')) {
                            assets.fonts.push(href);
                        }
                    });
                    
                    // Icons
                    document.querySelectorAll('link[rel*="icon"]').forEach(link => {
                        if (link.href) assets.icons.push(link.href);
                    });
                    
                    // Scripts
                    document.querySelectorAll('script[src]').forEach(script => {
                        if (script.src) assets.scripts.push(script.src);
                    });
                    
                    return assets;
                }
            """)
            
            # Merge DOM assets
            for asset_type, urls in dom_assets.items():
                assets[asset_type].extend(urls)
            
            # Extract from network requests
            for request in requests_log:
                url = request['url']
                resource_type = request['resource_type']
                
                if resource_type == 'image':
                    assets['images'].append(url)
                elif resource_type == 'stylesheet':
                    assets['stylesheets'].append(url)
                elif resource_type == 'font':
                    assets['fonts'].append(url)
                elif resource_type == 'script':
                    assets['scripts'].append(url)
            
            # Remove duplicates and limit count
            for asset_type in assets:
                assets[asset_type] = list(set(assets[asset_type]))[:20]
                
        except Exception as e:
            logger.error(f"Asset extraction failed: {str(e)}")
        
        return assets
    
    async def _extract_metadata(self, page: Page) -> Dict[str, any]:
        try:
            metadata = await page.evaluate("""
                () => {
                    const meta = {
                        title: '',
                        description: '',
                        keywords: '',
                        viewport: '',
                        charset: '',
                        og_data: {}
                    };
                    
                    // Title
                    const title = document.querySelector('title');
                    if (title) meta.title = title.textContent.trim();
                    
                    // Meta tags
                    document.querySelectorAll('meta').forEach(metaTag => {
                        const name = metaTag.getAttribute('name') || '';
                        const property = metaTag.getAttribute('property') || '';
                        const content = metaTag.getAttribute('content') || '';
                        
                        if (name.toLowerCase() === 'description') {
                            meta.description = content;
                        } else if (name.toLowerCase() === 'keywords') {
                            meta.keywords = content;
                        } else if (name.toLowerCase() === 'viewport') {
                            meta.viewport = content;
                        } else if (metaTag.hasAttribute('charset')) {
                            meta.charset = metaTag.getAttribute('charset');
                        } else if (property.startsWith('og:')) {
                            meta.og_data[property] = content;
                        }
                    });
                    
                    return meta;
                }
            """)
            
            return metadata
            
        except Exception as e:
            logger.error(f"Metadata extraction failed: {str(e)}")
            return {}

    async def _extract_raw_html(self, page: Page) -> str:  
        try:
            return page.content()
        
        except Exception as e:
            logger.error(f"Metadata extraction failed: {str(e)}")
            return {}

    def _clean_dom(self, html: str) -> str:
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # Remove scripts
            for script in soup.find_all("script"):
                script.decompose()
            
            # Remove style tags (we extract CSS separately)
            for style in soup.find_all("style"):
                style.decompose()
            
            # Remove comments
            for comment in soup.find_all(string=lambda text: isinstance(text, str) and text.strip().startswith('<!--')):
                comment.extract()
            
            # Remove tracking elements
            tracking_selectors = [
                '[id*="analytics"]', '[class*="analytics"]',
                '[id*="tracking"]', '[class*="tracking"]',
                '[id*="gtm"]', '[class*="gtm"]',
                '[id*="facebook"]', '[class*="facebook"]'
            ]
            
            for selector in tracking_selectors:
                for element in soup.select(selector):
                    element.decompose()
            
            return str(soup)
            
        except Exception as e:
            logger.error(f"DOM cleaning failed: {str(e)}")
            return html
            
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
            layout_info={}, assets={}, metadata={}, raw_html={},
            success=False, error_message=error_message
        )
                 
    
    # BROWSER CLEANUP
    async def _cleanup_browser(self):
        try:
            if self.context:
                await self.context.close()
                self.context = None
            if self.browser:
                await self.browser.close()
                self.browser = None
        except Exception as e:
            logger.error(f"Browser cleanup failed: {str(e)}")
        