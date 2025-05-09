# scraper.py
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options as ChromeOptions
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import re
from datetime import datetime
import time

def count_words(text):
    if not text:
        return 0
    words = re.findall(r'\b\w+\b', text.lower())
    return len(words)

def parse_banner_date(date_text):
    if not date_text or date_text.strip().lower() == "n/a - date not found":
        return "N/A - Date not found"
    date_text_normalized = date_text.replace("a.m.", "AM").replace("p.m.", "PM").strip()
    tz_pattern = r'\b(EDT|EST|CDT|CST|MDT|MST|PDT|PST)\b'
    tz_match = re.search(tz_pattern, date_text_normalized)
    tz_suffix = ""
    if tz_match:
        tz_suffix = " " + tz_match.group(1)
        date_text_normalized = re.sub(tz_pattern, "", date_text_normalized).strip()
    formats_to_try = [
        "%B %d, %Y, %I:%M %p", "%B %d, %Y, %I:%M%p",
        "%b %d, %Y, %I:%M %p", "%b %d, %Y, %I:%M%p",
        "%B %d, %Y", "%b %d, %Y",
        "%m/%d/%Y %I:%M %p", "%m/%d/%Y",
    ]
    for fmt in formats_to_try:
        try:
            dt_obj = datetime.strptime(date_text_normalized, fmt)
            return dt_obj.strftime('%B %d, %Y, %I:%M %p') + tz_suffix
        except ValueError:
            continue
    return date_text


_driver_instance = None # Global-like variable to hold the driver instance for the app's lifetime

def get_or_create_driver(headless=False, force_recreate=False):
    """
    Gets the existing Selenium WebDriver instance or creates a new one.
    The Flask app will call this.
    """
    global _driver_instance
    if force_recreate and _driver_instance:
        _driver_instance.quit()
        _driver_instance = None

    if _driver_instance is None:
        print("Initializing Selenium WebDriver...")
        chrome_options = ChromeOptions()
        if headless:
            chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
        
        try:
            service = ChromeService(ChromeDriverManager().install())
            _driver_instance = webdriver.Chrome(service=service, options=chrome_options)
            print("Selenium WebDriver initialized.")

            if not headless: # Only prompt for login if browser is visible
                print("Navigating to Baltimore Banner for potential login...")
                _driver_instance.get("https://www.thebaltimorebanner.com/")
                try:
                    _driver_instance.find_element(webdriver.common.by.By.CSS_SELECTOR, 'button[aria-label*="Account"]') # Example
                    print("It seems you might already be logged in (found account button).")
                except: # If not found, assume not logged in
                    print("MANUAL STEP REQUIRED:")
                    print("A Chrome browser window (controlled by Selenium) has opened.")
                    print("Please log in to The Baltimore Banner in that window.")
                    input("Press Enter in this console AFTER you have logged in to continue...")
                print("Login step completed or skipped. Proceeding...")

        except Exception as e:
            print(f"Error initializing WebDriver: {e}")
            _driver_instance = None # Ensure it's None if init failed
            raise
    return _driver_instance


def close_driver():
    global _driver_instance
    if _driver_instance:
        print("Closing Selenium WebDriver...")
        _driver_instance.quit()
        _driver_instance = None
        print("WebDriver closed.")

def scrape_article_data(article_url):
    """
    Scrapes data from a Baltimore Banner article URL using Selenium and BeautifulSoup.
    Relies on a shared WebDriver instance managed by get_or_create_driver().
    """
    driver = None
    try:
        driver = get_or_create_driver(headless=False)
    except Exception as e:
        return {"error": f"Could not get Selenium WebDriver: {str(e)}"}

    if not driver: # Should not happen if exception is raised properly
         return {"error": "WebDriver instance is not available."}

    try:
        print(f"Navigating to article: {article_url}")
        driver.get(article_url)
        time.sleep(5) # Wait for dynamic content, paywall checks, JS rendering
        page_source = driver.page_source
    except Exception as e:
        # Don't close the shared driver here on a per-article error
        return {"error": f"Selenium could not load the article URL. Error: {e}"}

    # --- BeautifulSoup Parsing Logic (largely unchanged) ---
    soup = BeautifulSoup(page_source, 'html.parser')
    data = {'url': article_url}

    # 1. Headline
    headline_tag = soup.select_one('h1.font-bold, h1[class*="headline"], header h1, h1[data-qa="Heading"]')
    if not headline_tag: headline_tag = soup.find('h1')
    if headline_tag:
        headline_text = headline_tag.get_text(strip=True)
        data['headline'] = headline_text
        data['headline_word_count'] = count_words(headline_text)
    else:
        data['headline'] = "N/A - Headline not found"
        data['headline_word_count'] = 0

    # 2. Date Posted
    data['date_posted'] = "N/A - Date not found"
    # Strategy: Look for <time datetime="..."> first.
    # Then look for specific patterns in the byline area.
    time_tag_dt = soup.find('time', attrs={'datetime': True})
    if time_tag_dt and time_tag_dt.get('datetime'):
        try:
            date_str = time_tag_dt['datetime']
            parsed_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            data['date_posted'] = parsed_date.strftime('%B %d, %Y, %I:%M %p %Z')
        except ValueError:
            date_text_content = time_tag_dt.get_text(strip=True)
            if date_text_content:
                parsed_dt_text = parse_banner_date(date_text_content)
                if parsed_dt_text != date_text_content: data['date_posted'] = parsed_dt_text

    if data['date_posted'] == "N/A - Date not found":
        # Look in typical byline/metadata containers
        byline_containers = soup.select('div[class*="Byline"], div[class*="timestamp"], p[class*="timestamp"], span[class*="timestamp"], div[class*="PageMetaData"], div.items-center.text-sm')
        for container in byline_containers:
            text_content = container.get_text(" ", strip=True)
            # More specific regex for dates within these containers
            match = re.search(r"(\w+\s+\d{1,2},\s+\d{4}(?:,\s*\d{1,2}:\d{2}\s*(?:a\.m\.|p\.m\.)(?:\s*\w+)?)?)", text_content, re.IGNORECASE)
            if match:
                parsed_dt_text = parse_banner_date(match.group(1))
                if parsed_dt_text != match.group(1) or "N/A" not in parsed_dt_text:
                    data['date_posted'] = parsed_dt_text
                    break
        # Fallback to any <time> tag's text content if still not found
        if data['date_posted'] == "N/A - Date not found":
            all_time_tags = soup.find_all('time')
            for t_tag in all_time_tags:
                text = t_tag.get_text(strip=True)
                if text:
                    parsed_dt_text = parse_banner_date(text)
                    if parsed_dt_text != text or "N/A" not in parsed_dt_text :
                        data['date_posted'] = parsed_dt_text
                        break


    # 3. Article Word Count
    article_text_content = ""
    text_extraction_block = None
    # Selectors ordered from most likely/specific to more general
    article_body_selectors = [
        'div.rich-text__content',
        'div.rich-text--article-body',
        'div[data-qa="ArticleBody"]',
        'section[data-qa="ArticleBody"]', # Some sites use section
        'div[class*="article-body"]',
        'div[class*="ArticlePage-articleBody"]',
        'article[class*="ArticlePage"] div[class*="body"]',
        'article .entry-content', # Common WordPress class
        'article' # Broadest fallback
    ]
    for selector in article_body_selectors:
        block = soup.select_one(selector)
        if block:
            # Filter out known non-content blocks if using a broad selector like 'article'
            if selector == 'article':
                for non_content_selector in ['header', 'footer', '.related-articles', '.comments']:
                    for el in block.select(non_content_selector):
                        el.decompose() # Remove these parts before getting text

            temp_text = block.get_text(separator=' ', strip=True)
            if count_words(temp_text) > 50: # Require a reasonable amount of text
                article_text_content = temp_text
                text_extraction_block = block
                # print(f"DEBUG: Text extracted using selector: '{selector}'")
                break
    data['article_word_count'] = count_words(article_text_content)

    # 4. Images and Number of Images (search within the identified text_extraction_block or fallback to soup)
    images = []
    found_image_srcs = set()
    search_context_for_images = text_extraction_block if text_extraction_block and data['article_word_count'] > 0 else soup

    if search_context_for_images:
        figure_tags = search_context_for_images.find_all('figure', recursive=True) # recursive is default but explicit
        for fig in figure_tags:
            img_tag = fig.find('img')
            if img_tag:
                src = img_tag.get('src') or img_tag.get('data-src') # Check data-src for lazy loading
                if src and src.startswith('http') and src not in found_image_srcs:
                    # Attempt to get a more meaningful alt text from figcaption if img alt is poor
                    alt_text = img_tag.get('alt', '')
                    figcaption_tag = fig.find('figcaption')
                    caption_text = figcaption_tag.get_text(strip=True) if figcaption_tag else ''
                    
                    final_alt = alt_text
                    if (not alt_text or alt_text.lower() in ["image", "photo", "", "graphic", "illustration"]) and caption_text:
                        final_alt = caption_text
                    elif caption_text and alt_text != caption_text and alt_text.lower() not in ["image", "photo", "", "graphic", "illustration"]:
                         final_alt = f"{alt_text} - {caption_text}"
                    
                    images.append({'src': src, 'alt': final_alt if final_alt else "Article Image"})
                    found_image_srcs.add(src)
        
        # Fallback for images not in figures, but still within the article body
        if not images and text_extraction_block: # Only if no images found in figures and we have a body
            direct_img_tags = text_extraction_block.find_all('img')
            for img_tag in direct_img_tags:
                src = img_tag.get('src') or img_tag.get('data-src')
                if src and src.startswith('http') and src not in found_image_srcs:
                    # Add filters to avoid tiny/irrelevant images
                    width = img_tag.get('width', '0')
                    height = img_tag.get('height', '0')
                    try: # Ensure width/height are digits if present
                        w, h = int(re.sub(r'\D', '', width)), int(re.sub(r'\D', '', height))
                        if w < 100 and h < 100 and (w != 0 or h != 0): # Skip small images if dimensions are known
                            continue
                    except ValueError:
                        pass # If width/height not parsable, proceed
                    
                    if any(keyword in src.lower() for keyword in ['logo', 'avatar', 'icon', 'ads', 'spinner', 'gravatar', 'pixel', 'banner/button', 'feed']):
                        continue

                    alt_text = img_tag.get('alt', 'Article Image')
                    images.append({'src': src, 'alt': alt_text})
                    found_image_srcs.add(src)

    data['images'] = images
    data['image_count'] = len(images)
    return data


if __name__ == '__main__':
    # Test script for direct execution
    test_url = "https://www.thebaltimorebanner.com/politics-power/national-politics/trump-librarian-congress-carla-hayden-E7CCMFF425CGXIVY3BXAMKWHSE/"
    # test_url = "https://www.thebaltimorebanner.com/culture/food-drink/suspension-ales-taproom-grand-opening-ingrid-gregg-RYB4N2B2U5EBTDO7C6NZXUHRXA/" # Another article

    print(f"\n--- Testing Selenium Scraper for URL: {test_url} ---")
    # The get_or_create_driver will handle the initial login prompt
    
    try:
        # This call ensures the driver is up and login prompt is shown if needed.
        get_or_create_driver(headless=False) # Force non-headless for testing login
        
        print(f"Attempting to scrape: {test_url}")
        scraped_info = scrape_article_data(test_url)

        if "error" in scraped_info:
            print(f"Error: {scraped_info['error']}")
        else:
            print(f"Headline: \"{scraped_info.get('headline', 'N/A')}\" ({scraped_info.get('headline_word_count', 0)} words)")
            print(f"Date Posted: {scraped_info.get('date_posted', 'N/A')}")
            print(f"Article Word Count: {scraped_info.get('article_word_count', 0)}")
            print(f"Image Count: {scraped_info.get('image_count', 0)}")
            if scraped_info.get('images'):
                print("Images Found:")
                for img_idx, img in enumerate(scraped_info['images']):
                    print(f"  {img_idx+1}. Src: {img['src']}, Alt: {img['alt'][:60]}...")
            else:
                print("No images found in article body.")
    except Exception as e:
        print(f"An error occurred during the test: {e}")
    finally:
        close_driver() # Close the driver when the test script finishes
    print("--- End Selenium Scraping Test ---")