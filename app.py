# app.py
from flask import Flask, render_template, request, redirect, url_for
from scraper import scrape_article_data # Ensure scraper.py is in the same directory

app = Flask(__name__)
app.secret_key = 'your_very_secret_key' # Important for session management, even if not used directly here

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
                scraped_output = scrape_article_data(article_url_input)
                if "error" in scraped_output:
                    error_message = scraped_output["error"]
                else:
                    data = scraped_output
        else:
            error_message = "Please enter an article URL."
            
    return render_template('index.html', data=data, error=error_message, article_url=article_url_input)

if __name__ == '__main__':
    app.run(debug=True)