import requests
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class URLShortener:
    def __init__(self):
        self.tinyurl_api = "http://tinyurl.com/api-create.php"
    
    def shorten_url(self, url: str) -> str:
        """Shorten URL using TinyURL service"""
        try:
            params = {'url': url}
            
            response = requests.get(self.tinyurl_api, params=params, timeout=10)
            response.raise_for_status()
            
            shortened_url = response.text.strip()
            
            if shortened_url.startswith('http') and 'tinyurl.com' in shortened_url:
                logger.info(f"URL shortened: {url} -> {shortened_url}")
                return shortened_url
            else:
                logger.warning(f"TinyURL failed: {shortened_url}")
                return self._fallback_shortener(url)
                
        except requests.RequestException as e:
            logger.error(f"TinyURL request error: {e}")
            return self._fallback_shortener(url)
        except Exception as e:
            logger.error(f"Error shortening URL: {e}")
            return url
    
    def _fallback_shortener(self, url: str) -> str:
        """Fallback shortener using is.gd"""
        try:
            api_url = "https://is.gd/create.php"
            params = {
                'format': 'simple',
                'url': url
            }
            
            response = requests.get(api_url, params=params, timeout=5)
            response.raise_for_status()
            
            shortened_url = response.text.strip()
            
            if shortened_url.startswith('http') and 'is.gd' in shortened_url:
                return shortened_url
            else:
                return url
                
        except Exception as e:
            logger.error(f"Fallback shortener error: {e}")
            return url
