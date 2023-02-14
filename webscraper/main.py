from website import Website

page_to_scrape = 'https://www.cs.cornell.edu/home/kleinber/'
subpage_sample = None

w = Website(page_to_scrape)
w.request()
q = w.scrape_text()