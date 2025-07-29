import re
import requests
from bs4 import BeautifulSoup
import urllib.parse
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

class AmazonScraper:
    def __init__(self):
        self.affiliate_tag = "budgetlooks08-21"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9,hi;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
    
    async def extract_product_info(self, url: str) -> Optional[Dict[str, str]]:
        """Extract product information from Amazon URL"""
        try:
            clean_url = self._clean_amazon_url(url)
            
            if not clean_url:
                logger.error(f"Invalid Amazon URL: {url}")
                return None
            
            response = requests.get(clean_url, headers=self.headers, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            product_info = {
                'title': self._extract_title(soup),
                'price': self._extract_price(soup),
                'image_url': self._extract_image_url(soup),
                'url': clean_url
            }
            
            logger.info(f"Successfully extracted: {product_info['title']}")
            return product_info
            
        except requests.RequestException as e:
            logger.error(f"Request error: {e}")
            return None
        except Exception as e:
            logger.error(f"Error extracting product info: {e}")
            return None
    
    def _clean_amazon_url(self, url: str) -> Optional[str]:
        """Clean Amazon URL to get the base product URL"""
        try:
            asin_pattern = r'/(?:dp|gp/product)/([A-Z0-9]{10})'
            match = re.search(asin_pattern, url)
            
            if not match:
                return None
            
            asin = match.group(1)
            parsed_url = urllib.parse.urlparse(url)
            domain = parsed_url.netloc
            
            clean_url = f"https://{domain}/dp/{asin}"
            return clean_url
            
        except Exception as e:
            logger.error(f"Error cleaning URL: {e}")
            return None
    
    def _extract_title(self, soup: BeautifulSoup) -> str:
        """Extract product title"""
        try:
            title_selectors = [
                '#productTitle',
                '.product-title',
                'h1.a-size-large',
                'h1 span',
                '[data-automation-id="product-title"]'
            ]
            
            for selector in title_selectors:
                title_element = soup.select_one(selector)
                if title_element:
                    title = title_element.get_text(strip=True)
                    if title:
                        return title[:200]
            
            return "Amazon Product"
            
        except Exception as e:
            logger.error(f"Error extracting title: {e}")
            return "Amazon Product"
    
    def _extract_price(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract product price"""
        try:
            price_selectors = [
                '.a-price .a-offscreen',
                '.a-price-whole',
                '#price_inside_buybox',
                '.a-price.a-text-price.a-size-medium.apexPriceToPay',
                '[data-automation-id="product-price"]',
                '.a-price-range'
            ]
            
            for selector in price_selectors:
                price_element = soup.select_one(selector)
                if price_element:
                    price = price_element.get_text(strip=True)
                    if price and any(char.isdigit() for char in price):
                        return price
            
            return None
            
        except Exception as e:
            logger.error(f"Error extracting price: {e}")
            return None
    
    def _extract_image_url(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract product image URL"""
        try:
            image_selectors = [
                '#landingImage',
                '#imgBlkFront',
                '#main-image',
                '.a-dynamic-image',
                '[data-automation-id="product-image"]'
            ]
            
            for selector in image_selectors:
                img_element = soup.select_one(selector)
                if img_element:
                    img_url = img_element.get('src') or img_element.get('data-src')
                    
                    if img_url and isinstance(img_url, str):
                        # Clean up image URL
                        img_url = re.sub(r'\._[A-Z0-9_,]+_\.', '.', img_url)
                        
                        if img_url.startswith('//'):
                            img_url = 'https:' + img_url
                        elif img_url.startswith('/'):
                            continue
                        
                        if img_url.startswith('http'):
                            return img_url
            
            return None
            
        except Exception as e:
            logger.error(f"Error extracting image: {e}")
            return None
    
    def generate_affiliate_link(self, url: str) -> str:
        """Generate affiliate link with tag"""
        try:
            parsed_url = urllib.parse.urlparse(url)
            query_params = urllib.parse.parse_qs(parsed_url.query)
            
            query_params['tag'] = [self.affiliate_tag]
            
            new_query = urllib.parse.urlencode(query_params, doseq=True)
            
            affiliate_url = urllib.parse.urlunparse((
                parsed_url.scheme,
                parsed_url.netloc,
                parsed_url.path,
                parsed_url.params,
                new_query,
                parsed_url.fragment
            ))
            
            return affiliate_url
            
        except Exception as e:
            logger.error(f"Error generating affiliate link: {e}")
            separator = '&' if '?' in url else '?'
            return f"{url}{separator}tag={self.affiliate_tag}"
