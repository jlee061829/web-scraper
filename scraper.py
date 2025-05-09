# scraper.py
import undetected_chromedriver as uc # Import undetected_chromedriver
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup
import re
from datetime import datetime
import time
import os

# --- Configuration ---
DEBUG_SAVE_HTML = True
DEBUG_HTML_DIR = "debug_html"

# --- Helper Functions (count_words, parse_banner_date, parse_srcset - keep these as they are) ---
def count_words(text):
    if not text: return 0
    return len(re.findall(r'\b\w+\b', text.lower()))

def parse_banner_date(date_text):
    if not date_text or "n/a" in date_text.strip().lower(): return "N/A - Date not found"
    date_text_normalized = date_text.replace("a.m.", "AM").replace("p.m.", "PM").strip()
    tz_pattern = r'\b(EDT|EST|CDT|CST|MDT|MST|PDT|PST)\b'
    tz_match = re.search(tz_pattern, date_text_normalized)
    tz_suffix = ""
    if tz_match:
        tz_suffix = " " + tz_match.group(1)
        date_text_normalized = re.sub(tz_pattern, "", date_text_normalized).strip()
    formats_to_try = [
        "%B %d, %Y, %I:%M %p", "%B %d, %Y, %I:%M%p", "%b %d, %Y, %I:%M %p", 
        "%b %d, %Y, %I:%M%p", "%B %d, %Y", "%b %d, %Y", "%m/%d/%Y %I:%M %p", "%m/%d/%Y",
    ]
    for fmt in formats_to_try:
        try:
            dt_obj = datetime.strptime(date_text_normalized, fmt)
            return dt_obj.strftime('%B %d, %Y, %I:%M %p') + tz_suffix
        except ValueError: continue
    return date_text

def parse_srcset(srcset_str):
    if not srcset_str: return None
    entries = [s.strip() for s in srcset_str.split(',')]
    best_url, max_width = None, 0
    if not entries: return None
    first_url_candidate = entries[0].split(' ')[0]
    for entry in entries:
        parts = entry.split(' ')
        url = parts[0]
        if len(parts) > 1 and parts[1].endswith('w'):
            try:
                width = int(parts[1][:-1])
                if width > max_width: max_width, best_url = width, url
            except ValueError: continue
        elif best_url is None: best_url = url
    return best_url if best_url else first_url_candidate

# --- Selenium WebDriver Management with undetected-chromedriver ---
_driver_instance = None

def get_or_create_driver(force_recreate=False): # Removed headless option for now
    global _driver_instance
    if force_recreate and _driver_instance:
        _driver_instance.quit()
        _driver_instance = None

    if _driver_instance is None:
        print_debug("Initializing undetected-chromedriver WebDriver...")
        options = uc.ChromeOptions()
        # You can add options here if needed, but UC handles many things automatically
        # options.add_argument('--no-sandbox')
        # options.add_argument('--disable-dev-shm-usage')
        # options.add_argument('--disable-gpu')
        # options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        try:
            # For UC, you might need to specify driver_executable_path if it's not found
            # or ensure chromedriver is in your PATH and compatible.
            # Often, UC handles this well.
            _driver_instance = uc.Chrome(options=options, use_subprocess=True) # use_subprocess can help on some systems
            print_debug("undetected-chromedriver WebDriver initialized.")

            # --- Force Manual Login ---
            print_debug("Navigating to Baltimore Banner for MANDATORY login...")
            _driver_instance.get("https://www.thebaltimorebanner.com/")
            time.sleep(2) # Allow initial page load
            click_cookie_banner(_driver_instance) # Attempt to click cookie banner

            print("MANUAL INTERVENTION REQUIRED:")
            print("An undetected-chromedriver browser window has opened to The Baltimore Banner.")
            print("Please complete the following in THAT window:")
            print("  1. Accept cookies if prompted (script may have already tried).")
            print("  2. Log in with your Baltimore Banner credentials.")
            input("Press Enter in THIS CONSOLE after you have successfully logged in...")
            
            print_debug("Verifying login status post-manual intervention...")
            # Navigate to a known "logged-in" page or check for a specific element
            # Example: navigate to homepage again and check for an account button
            _driver_instance.get("https://www.thebaltimorebanner.com/")
            time.sleep(3) # Allow page to settle
            click_cookie_banner(_driver_instance)
            try:
                WebDriverWait(_driver_instance, 15).until(
                    EC.presence_of_element_located((By.XPATH, '//button[contains(@aria-label, "Account") or contains(@aria-label, "User profile") or @data-qa="NavProfileMenuButton"] | //a[contains(text(), "My Account") or contains(text(), "Sign Out")]'))
                )
                print_debug("Login seems ACTIVE after manual step (found account-related element).")
            except TimeoutException:
                print_debug("WARNING: Could NOT confirm active login after manual step. Scraping may still be affected. Check the browser window.")
            print_debug("Login process complete.")

        except Exception as e:
            print(f"CRITICAL ERROR initializing undetected-chromedriver: {e}")
            if _driver_instance: _driver_instance.quit()
            _driver_instance = None
            raise
    return _driver_instance

def click_cookie_banner(driver_instance):
    # (Keep your click_cookie_banner function as it was)
    cookie_selectors = [
        "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'accept all')]",
        "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'accept cookies')]",
        "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'agree')]",
        "//button[@id='onetrust-accept-btn-handler']",
        "//button[contains(@class, 'cookie-accept')]"
    ]
    for selector in cookie_selectors:
        try:
            cookie_button = WebDriverWait(driver_instance, 3).until(EC.element_to_be_clickable((By.XPATH, selector)))
            cookie_button.click()
            print_debug(f"Clicked cookie banner using selector: {selector}")
            time.sleep(1); return True
        except: continue
    print_debug("No cookie banner found/clicked with provided selectors."); return False


def close_driver():
    global _driver_instance
    if _driver_instance:
        print_debug("Closing undetected-chromedriver WebDriver...")
        _driver_instance.quit()
        _driver_instance = None
        print_debug("WebDriver closed.")

def print_debug(message): print(f"DEBUG: {message}")

def save_html_debug(page_source, url_for_filename):
    if not DEBUG_SAVE_HTML: return
    if not os.path.exists(DEBUG_HTML_DIR): os.makedirs(DEBUG_HTML_DIR)
    filename_part = re.sub(r'[^a-zA-Z0-9_-]', '_', url_for_filename.split("://")[-1])[:100]
    filepath = os.path.join(DEBUG_HTML_DIR, f"uc_content_{filename_part}.html") # Prefix with uc_
    try:
        with open(filepath, "w", encoding="utf-8") as f: f.write(page_source)
        print_debug(f"Page source saved to {filepath}")
    except Exception as e: print_debug(f"Error saving HTML to {filepath}: {e}")

# --- Main Scraping Function ---
def scrape_article_data(article_url):
    driver = None
    try:
        driver = get_or_create_driver() # Will now force login if driver is None
    except Exception as e:
        return {"error": f"Fatal: Could not get/create WebDriver: {str(e)}"}

    if not driver: return {"error": "WebDriver instance not available."}

    print_debug(f"Attempting to navigate to article: {article_url}")
    page_source = None
    try:
        driver.get(article_url)
        # Wait for a *very basic* element to ensure *some* page has loaded before checking title
        WebDriverWait(driver, 25).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        current_page_title = driver.title
        print_debug(f"  Navigation supposedly complete. Current URL: {driver.current_url}")
        print_debug(f"  Page Title: {current_page_title}")

        # If it's a 404 page based on title, bail early
        if "404" in current_page_title.lower() or "page not found" in current_page_title.lower():
            print_debug(f"  WARNING: Detected 404 based on page title for {article_url}")
            save_html_debug(driver.page_source, f"404_{article_url}")
            return {"error": f"404 Page Not Found for article (Title: {current_page_title})."}

        # Now wait for actual article content indicators
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "article, main, div.rich-text--article-body, h1[data-qa='Heading']"))
        )
        print_debug("  Key article elements seem present.")
        
        time.sleep(2) # Small pause for any final JS rendering
        page_source = driver.page_source
        save_html_debug(page_source, article_url) # Save the (hopefully) correct page

    except TimeoutException:
        current_title_on_timeout = "N/A"
        try: current_title_on_timeout = driver.title
        except: pass
        print_debug(f"  ERROR: Timeout waiting for page elements on {article_url}. Title: {current_title_on_timeout}")
        if driver: save_html_debug(driver.page_source if driver.page_source else "No source on timeout", f"timeout_{article_url}")
        return {"error": f"Timeout loading full page/elements for {article_url}. Check saved HTML. Current title: {current_title_on_timeout}"}
    except Exception as e:
        print_debug(f"  ERROR: Selenium navigation error for {article_url}. Error: {e}")
        return {"error": f"Selenium navigation error: {e}"}

    if not page_source: return {"error": "Failed to retrieve page source after navigation."}
    
    # --- BeautifulSoup Parsing Logic (Keep your refined parsing logic from previous successful attempts) ---
    soup = BeautifulSoup(page_source, 'html.parser')
    data = {'url': article_url}

    # 1. Headline (Using the refined selectors)
    headline_selectors = ['h1[data-qa="Heading"]', 'h1.font-bold.leading-tight', 'article h1', 'header h1', 'h1']
    headline_text = "N/A - Headline not found"
    for selector in headline_selectors:
        tag = soup.select_one(selector)
        if tag and tag.get_text(strip=True): headline_text = tag.get_text(strip=True); break
    data['headline'] = headline_text
    data['headline_word_count'] = count_words(headline_text)

    # 2. Date Posted (Using the refined selectors)
    data['date_posted'] = "N/A - Date not found"
    date_selectors_and_attrs = [('time[datetime]', 'datetime'), ('time', 'text'), ('span[class*="timestamp"]', 'text'), ('p[class*="timestamp"]', 'text'), ('div[class*="Byline"] span', 'text'), ('div[class*="PageMetaData"]', 'text'), ('div.items-center.text-sm span', 'text')]
    for selector, content_type in date_selectors_and_attrs:
        tag = soup.select_one(selector)
        if tag:
            raw_date_text = tag.get('datetime') if content_type == 'datetime' else tag.get_text(strip=True)
            if raw_date_text:
                if content_type == 'datetime':
                    try: data['date_posted'] = datetime.fromisoformat(raw_date_text.replace('Z', '+00:00')).strftime('%B %d, %Y, %I:%M %p %Z'); break
                    except ValueError: pass
                parsed_dt = parse_banner_date(raw_date_text)
                if parsed_dt != raw_date_text or ("N/A" not in parsed_dt and parsed_dt.strip()): data['date_posted'] = parsed_dt; break
    
    # 3. Article Word Count (Using the refined selectors)
    article_text_content = ""; text_extraction_block = None
    article_body_selectors = ['div.rich-text__content', 'div.rich-text--article-body', 'div[data-qa="ArticleBody"]', 'section[data-qa="ArticleBody"]', 'div[class*="article-body"]', 'article']
    for selector in article_body_selectors:
        block = soup.select_one(selector)
        if block:
            if selector == 'article':
                for non_content_selector in ['header', 'footer', '.related-articles', '.comments', 'nav', 'aside', '.share-tools', '.ad-container']:
                    for el in block.select(non_content_selector): el.decompose()
            temp_text = block.get_text(separator=' ', strip=True)
            if count_words(temp_text) > 30: # Lowered slightly for more permissive matching on potentially short articles
                article_text_content, text_extraction_block = temp_text, block
                print_debug(f"  Article text extracted using selector: '{selector}' (Words: {count_words(temp_text)})")
                break
    data['article_word_count'] = count_words(article_text_content)
    if data['article_word_count'] == 0: print_debug("  WARNING: Article word count is 0.")

    # 4. Images (Using the refined logic)
    images_list, found_image_srcs = [], set()
    search_contexts = []
    if text_extraction_block: search_contexts.append(text_extraction_block)
    article_tag = soup.find('article'); main_tag = soup.find('main')
    if article_tag and article_tag not in search_contexts : search_contexts.append(article_tag)
    if not search_contexts: search_contexts.append(soup)

    for i_ctx, context in enumerate(search_contexts):
        for fig in context.find_all('figure', recursive=True):
            img_tag = fig.find('img')
            if img_tag:
                src, data_src, srcset = img_tag.get('src'), img_tag.get('data-src'), img_tag.get('srcset')
                img_url = data_src or src
                if srcset and (not img_url or "placeholder" in str(img_url).lower()): img_url = parse_srcset(srcset) or img_url
                if not img_url and src: img_url = src
                if img_url and img_url.startswith('http') and img_url not in found_image_srcs and not img_url.startswith('data:image') and "placeholder" not in img_url.lower():
                    alt, cap_tag, cap = img_tag.get('alt',''), fig.find('figcaption'), ""
                    if cap_tag: cap = cap_tag.get_text(strip=True)
                    final_alt = alt.strip()
                    if (not final_alt or final_alt.lower() in ["image", "photo", "picture"]) and cap: final_alt = cap
                    elif cap and final_alt and final_alt.lower() != cap.lower(): final_alt = f"{final_alt} - {cap}"
                    images_list.append({'src':img_url, 'alt':final_alt if final_alt else "Article Image"}); found_image_srcs.add(img_url)
        for img_tag in context.find_all('img', recursive=True):
            src, data_src, srcset = img_tag.get('src'), img_tag.get('data-src'), img_tag.get('srcset')
            img_url = data_src or src
            if srcset and (not img_url or "placeholder" in str(img_url).lower()): img_url = parse_srcset(srcset) or img_url
            if not img_url and src: img_url = src
            if img_url and img_url.startswith('http') and img_url not in found_image_srcs and not img_url.startswith('data:image') and "placeholder" not in img_url.lower():
                w_attr, h_attr, min_dim = img_tag.get('width','0'), img_tag.get('height','0'), 75
                try: w,h = int(re.sub(r'\D','',str(w_attr))), int(re.sub(r'\D','',str(h_attr)))
                except ValueError: w,h = 0,0
                if (w>0 and w<min_dim) and (h>0 and h<min_dim): continue
                skip_kw_img = ['logo','avatar','icon','ads','spinner','gravatar','pixel','badge','captcha','spacer','feed','mtrctk','scorecardresearch','bing.com/action','track','static.arcpublishing']
                if any(kw in img_url.lower() for kw in skip_kw_img): continue
                images_list.append({'src':img_url,'alt':img_tag.get('alt','Article Image')}); found_image_srcs.add(img_url)
        if images_list and context != soup and i_ctx == 0 : # If images found in most specific context
            print_debug(f"  Found {len(images_list)} images in primary context. Not searching broader contexts for images."); break
            
    data['images'] = images_list; data['image_count'] = len(images_list)
    if not images_list and data['article_word_count'] > 10: print_debug("  No content images found despite finding article text.")
    
    return data

# --- Main Execution (for testing) ---
if __name__ == '__main__':
    if DEBUG_SAVE_HTML and not os.path.exists(DEBUG_HTML_DIR):
        os.makedirs(DEBUG_HTML_DIR); print(f"Created debug HTML directory: {DEBUG_HTML_DIR}")

    test_urls = [
        "https://www.thebaltimorebanner.com/politics-power/national-politics/trump-librarian-congress-carla-hayden-E7CCMFF425CGXIVY3BXAMKWHSE/",
        "https://www.thebaltimorebanner.com/culture/food-drink/suspension-ales-taproom-grand-opening-ingrid-gregg-RYB4N2B2U5EBTDO7C6NZXUHRXA/",
        "https://www.thebaltimorebanner.com/sports/orioles-mlb/baltimore-orioles-brandon-hyde-manager-of-the-year-finalist-YIXCTXNOHJDPJL6QL7MXHQLGVQ/"
    ]
    # A known good article (as of Dec 2023, may change) for control:
    # test_urls.append("https://www.thebaltimorebanner.com/community/criminal-justice/baltimore-police-data-shows-continued-reductions-in-homicides-shootings-MPYV3X33BBA7ZMSKKIKSCQZVTE/")

    try:
        get_or_create_driver() # This handles the initial login prompt
        for i, test_url in enumerate(test_urls):
            print(f"\n--- Scraping Test URL {i+1}: {test_url} ---")
            scraped_info = scrape_article_data(test_url)
            if "error" in scraped_info: print(f"Error: {scraped_info['error']}")
            else:
                print(f"Headline: \"{scraped_info.get('headline', 'N/A')}\" ({scraped_info.get('headline_word_count', 0)} words)")
                print(f"Date Posted: {scraped_info.get('date_posted', 'N/A')}")
                print(f"Article Word Count: {scraped_info.get('article_word_count', 0)}")
                print(f"Image Count: {scraped_info.get('image_count', 0)}")
                if scraped_info.get('images'):
                    print("Images Found:")
                    for img_idx, img in enumerate(scraped_info['images']):
                        print(f"  {img_idx+1}. Src: {img['src']}\n     Alt: {img['alt'][:100]}")
                elif scraped_info.get('article_word_count', 0) > 10 : print("No content images found in article body.")
            print("--- End Scraping Test ---")
    except Exception as e:
        print(f"An TOP LEVEL unexpected error occurred during the test run: {e}")
        import traceback; traceback.print_exc()
    finally:
        close_driver()