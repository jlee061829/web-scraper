# scraper.py
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime

def count_words(text):
    """Counts words in a given string."""
    if not text:
        return 0
    words = re.findall(r'\b\w+\b', text.lower())
    return len(words)

def scrape_article_data(article_url):
    """
    Scrapes data from a Baltimore Banner article URL.
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    try:
        response = requests.get(article_url, headers=headers, timeout=10)
        response.raise_for_status()  # Raise an exception for HTTP errors
    except requests.RequestException as e:
        print(f"Error fetching URL: {e}")
        return {"error": f"Could not fetch the article. Please check the URL. Error: {e}"}

    soup = BeautifulSoup(response.content, 'html.parser')
    data = {}

    # 1. Headline and Headline Word Count
    headline_tag = soup.find('h1', class_=lambda x: x and 'font-bold' in x and 'leading-tight' in x) # More robust class search
    if not headline_tag: # Fallback if the specific classes aren't found
        headline_tag = soup.find('h1')

    if headline_tag:
        headline_text = headline_tag.get_text(strip=True)
        data['headline'] = headline_text
        data['headline_word_count'] = count_words(headline_text)
    else:
        data['headline'] = "N/A - Headline not found"
        data['headline_word_count'] = 0

    # 2. Date Posted
    # The Banner often uses <time datetime="..."> or a span with date information
    date_tag = soup.find('time', attrs={'datetime': True})
    if date_tag and date_tag.get('datetime'):
        try:
            # Example datetime: "2023-10-27T09:00:00.000Z"
            date_str = date_tag['datetime']
            # Parse the ISO format date and reformat it
            parsed_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            data['date_posted'] = parsed_date.strftime('%B %d, %Y, %I:%M %p %Z')
        except ValueError:
            data['date_posted'] = date_tag.get_text(strip=True) # Fallback to text if parsing fails
    else:
        # Fallback: Look for elements that might contain date-like text
        # This is highly site-specific and might need adjustment
        possible_date_elements = soup.find_all(['span', 'p', 'div'], string=re.compile(r'\w+ \d{1,2}, \d{4}'))
        if possible_date_elements:
            data['date_posted'] = possible_date_elements[0].get_text(strip=True)
        else:
            data['date_posted'] = "N/A - Date not found"


    # 3. Article Word Count (main content)
    # The main article content seems to be within a div with class 'rich-text--article-body'
    article_body_div = soup.find('div', class_='rich-text--article-body')
    article_text_content = ""
    if article_body_div:
        # Get text from all paragraphs within this div
        paragraphs = article_body_div.find_all('p')
        article_text_content = " ".join([p.get_text(strip=True) for p in paragraphs])
        data['article_word_count'] = count_words(article_text_content)
    else:
        data['article_word_count'] = 0
        print("Warning: Could not find the main article body element ('div.rich-text--article-body'). Word count might be inaccurate.")
        # Fallback to a more generic content search if specific class fails
        # This is less precise.
        main_content_area = soup.find('article') or soup.find('main')
        if main_content_area:
            article_text_content = main_content_area.get_text(separator=' ', strip=True)
            data['article_word_count'] = count_words(article_text_content)


    # 4. Images and Number of Images (within the article body)
    images = []
    if article_body_div: # Search for images only within the identified article body
        img_tags = article_body_div.find_all('img')
        for img in img_tags:
            src = img.get('src')
            if src and src.startswith('http'): # Ensure it's a full URL
                alt_text = img.get('alt', 'Image')
                images.append({'src': src, 'alt': alt_text})
    elif main_content_area: # Fallback if specific body div not found
         img_tags = main_content_area.find_all('img')
         for img in img_tags:
            src = img.get('src')
            if src and src.startswith('http'):
                alt_text = img.get('alt', 'Image')
                images.append({'src': src, 'alt': alt_text})


    data['images'] = images
    data['image_count'] = len(images)

    return data

if __name__ == '__main__':
    # Example usage (for testing the scraper directly)
    # test_url = "https://www.thebaltimorebanner.com/community/criminal-justice/baltimore-police-officer-arrested-misconduct-in-office-second-degree-assault-YLDS3OWVT5BOXNIHOVWQQYBWUE/"
    test_url = "https://www.thebaltimorebanner.com/politics-power/local-government/mayor-scott-state-of-the-city-address-Z62LLS4Y7BH4JKEAFPMHUWZVS4/"
    # test_url = "https://www.thebaltimorebanner.com/culture/food-drink/suspension-ales-taproom-grand-opening-ingrid-gregg-RYB4N2B2U5EBTDO7C6NZXUHRXA/" # Article with images
    
    if not test_url.startswith("https://www.thebaltimorebanner.com/"):
        print("Warning: This scraper is specifically designed for The Baltimore Banner URLs.")
    
    scraped_info = scrape_article_data(test_url)
    if "error" in scraped_info:
        print(f"Error: {scraped_info['error']}")
    else:
        for key, value in scraped_info.items():
            if key == 'images':
                print(f"{key.replace('_', ' ').title()}: {len(value)} images found")
                # for img in value:
                #     print(f"  - {img['src']} (Alt: {img['alt']})")
            else:
                print(f"{key.replace('_', ' ').title()}: {value}")