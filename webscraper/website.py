import requests
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from datetime import datetime
import os
import shutil

def fdate(dt=None):
    if dt is None: return str(datetime.now().strftime('%Y-%m-%d'))
    return str(dt.strftime('%Y-%m-%d'))

def ftime(dt=None):
    if dt is None: return str(datetime.now().strftime('%H:%M:%S'))
    return str(dt.strftime('%H:%M:%S'))

class Cache:
    BASE_NAME = 'caches'
    BASE_PATH = os.path.join(os.getcwd(), BASE_NAME)
    HOMEPAGE_NAME = '* homepage'

    def __init__(self, website):
        self.website = website
        self.superpath = os.path.join(Cache.BASE_PATH, self.website.domain)
        # If domain has never been visited, create folder for entire domain
        if not os.path.exists(self.superpath): os.makedirs(self.superpath)

        # Create subfolder for queries
        name = Cache.HOMEPAGE_NAME if website.is_homepage else self.website.rel_url
        name = name.replace('/', '-')[1:]
        self.path = os.path.join(self.superpath, name)
        if not os.path.exists(self.path): os.makedirs(self.path)

        # Key: query.id = (url, date, time)
        self.storage = dict()

    def store_query(self, query, name=None):
        date_path = os.path.join(self.path, query.date_of)
        # If no queries stored today, create dated folder
        if not os.path.exists(date_path): os.makedirs(date_path)

        file_name = f"{query.time_of} {query.action}" if name is None else name
        file_path = os.path.join(date_path, file_name)

        # Write query report to file
        with open(file_path, 'w') as file:  # Shouldn't need to write more than once in a file ('w' creates/overwrites)
            file.writelines(query.get_report())
            file.close()
        # Store during runtime
        self.storage[query.id] = query

        print(f"Successfully cached {query.action} query \"{query.id}\"")
        return file_path

    def load(self, date=None):
        path = self.path if date is None else os.path.join(self.path, date)
        assert os.path.exists(path)

        filepaths = []
        for path, _, filenames in os.walk(path):
            for filename in filenames:
                filepath = os.path.join(path, filename)
                filepaths.append(filepath)

        for path in filepaths:
            query = Query.reconstruct_from_report(path)
            self.storage[query.id] = query

    def clear(self, date=None):
        path = self.path if date is None else os.path.join(self.path, date)
        assert os.path.exists(path)

        for item in os.listdir(path):
            shutil.rmtree(os.path.join(path, item))

    @staticmethod
    def _get_contents(path):
        dirs = list()
        files = list()
        for path in os.listdir(path):
            if os.path.isdir(path): dirs.add(path)
            if os.path.isfile(path): files.add(path)
        return dirs, files

    @staticmethod
    def get_all_domains():
        return Cache.get_contents(Cache.BASE_PATH)[0]

class Query:
    REPORT_CONTENT_START = 4
    LINKS = "Link Scrape"
    TEXT = "Text Scrape"

    def __init__(self, page_url, content, action, dt=None):
        self.page_url = page_url
        self.content = content
        self.action = action

        # dt can be given as a parameter to reconstruct queries from text
        if dt is None:
            dt = datetime.now()
            self.date_of = fdate(dt)
            self.time_of = ftime(dt)
        else:
            date, time = dt
            self.date_of = date
            self.time_of = time

        self.id = (self.page_url, self.date_of, self.time_of)

    def __str__(self): return str(self.content)

    def get_report(self):
        report = [self.page_url + "\n",
                  self.action + "\n",
                  self.date_of + "\n",
                  self.time_of + "\n"]

        if self.action == Query.LINKS:
            for line in self.content:
                report.append(line + "\n")

        return report

    @staticmethod
    def reconstruct_from_report(report_path):
        with open(report_path, 'r') as file:
            lines = file.read().splitlines()
            file.close()

        url, action, date, time = lines[:Query.REPORT_CONTENT_START]
        content = lines[Query.REPORT_CONTENT_START:]
        return Query(url, content, action, (date, time))


class Website:
    def __init__(self, url):
        self.main_url = url     # URL of page
        self.rel_url = str(urlparse(self.main_url).path)    # Path following domain, (=main_url if homepage)
        self.domain = str(urlparse(self.main_url).netloc)
        self.is_homepage = self.main_url == self.rel_url

        # Updated every request
        self.resp = None
        self.html = None
        self.soup = None
        self.last_request = None

        self.cache = Cache(self)

    def __str__(self): return self.html

    def request(self):
        print(f"Requesting {self.main_url}")
        r = requests.get(self.main_url)
        self.last_request = datetime.now()

        if not r.ok:
            print(f"Failed to request {self.main_url}")
            return False

        print(f"Successfully requested {self.main_url}")
        self.resp = r
        self.html = r.text
        self.soup = BeautifulSoup(r.text, features="lxml")
        return True

    def scrape_links(self, same_domain=False, as_set=False):
        links = set() if as_set else list()

        for link in self.soup.find_all('a', href=True):
            href = link.get('href')
            link = str(href).strip('/"#')

            if "//" not in link: continue   # Scrape "external" links only
            if same_domain and self.domain not in link: continue

            if as_set: links.add(link)
            else: links.append(link)

        return Query(self.main_url, links, Query.LINKS)

    def scrape_text(self):
        # https://stackoverflow.com/questions/1936466/how-to-scrape-only-visible-webpage-text-with-beautifulsoup
        from bs4.element import Comment

        def tag_visible(element):
            if element.parent.name in ['style', 'script', 'head', 'title', 'meta', '[document]']:
                return False
            if isinstance(element, Comment):
                return False
            return True

        def text_from_html(body):
            soup = BeautifulSoup(body, 'html.parser')
            texts = soup.findAll(text=True)
            visible_texts = filter(tag_visible, texts)
            return u" ".join(t.strip() for t in visible_texts)

        text = text_from_html(self.html)
        return Query(self.main_url, text, Query.TEXT)


    def cache(self, query):
        return self._cache.store_query(query)