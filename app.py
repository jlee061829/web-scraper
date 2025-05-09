# app.py
from flask import Flask, render_template, request
from scraper import scrape_article_data, close_driver, get_or_create_driver
import atexit

app = Flask(__name__)
app.secret_key = 'your_very_secret_key'

# Initialize driver when app starts (if not in test mode)
# This ensures the login prompt happens once when the app starts.
if not app.testing:
    try:
        get_or_create_driver(headless=False) # Start non-headless for login
    except Exception as e:
        print(f"CRITICAL: Failed to initialize Selenium WebDriver on app startup: {e}")
        # Optionally, exit or run in a degraded mode
        # exit(1)


@app.route('/', methods=['GET', 'POST'])
def index():
    data = None
    error_message = None
    article_url_input = ""

    if request.method == 'POST':
        article_url_input = request.form.get('article_url')
        if article_url_input:
            if not article_url_input.startswith("https://www.thebaltimorebanner.com/"):
                error_message = "Please enter a valid URL from thebaltimorebanner.com."
            else:
                try:
                    # The driver should already be initialized and logged in
                    scraped_output = scrape_article_data(article_url_input)
                    if "error" in scraped_output:
                        error_message = scraped_output["error"]
                    else:
                        data = scraped_output
                except Exception as e:
                    error_message = f"An unexpected error occurred during scraping: {str(e)}"
                    # Optionally, try to re-initialize driver or just report error
                    print(f"Scraping error: {e}")
        else:
            error_message = "Please enter an article URL."
            
    return render_template('index.html', data=data, error=error_message, article_url=article_url_input)

# Ensure the driver is closed when the Flask app exits
atexit.register(close_driver)

if __name__ == '__main__':
    # Note: Flask's reloader can cause issues with global resources like Selenium driver.
    # For development, run with use_reloader=False if you encounter issues with
    # the driver being closed and reopened unexpectedly, or multiple login prompts.
    app.run(debug=True, use_reloader=False)