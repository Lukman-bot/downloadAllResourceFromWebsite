import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from termcolor import colored
import re
import time
from datetime import datetime

def create_folder(path):
    if not os.path.exists(path):
        os.makedirs(path)

downloaded_files = set()
pending_files = set()

def normalize_path_case(path):
    return os.path.normpath(path).lower()

def normalize_url_case(url):
    parsed = urlparse(url)
    normalized_path = parsed.path.lower()
    return urljoin(parsed.geturl(), normalized_path)

def is_valid_link(url, base_domain=None):
    parsed = urlparse(url)
    if not bool(parsed.netloc) or not bool(parsed.scheme):
        return False
    if base_domain and parsed.netloc != base_domain:
        return False
    return True

def log_message(log_folder, website_url, message):
    date_str = datetime.now().strftime('%Y-%m-%d')
    log_file = os.path.join(log_folder, f"{date_str}.log")
    create_folder(log_folder)

    timestamp = datetime.now().strftime('[%H:%M %d-%m-%Y]')
    with open(log_file, 'a', encoding='utf-8') as log:
        log_message = f"{timestamp}{message}\n"
        if "===== Begin" in message and not os.path.getsize(log_file):
            log.write(log_message)  # Add only the header if the file is empty
        else:
            log.write(log_message)

def finalize_log(log_folder, website_url):
    date_str = datetime.now().strftime('%Y-%m-%d')
    log_file = os.path.join(log_folder, f"{date_str}.log")
    with open(log_file, 'a', encoding='utf-8') as log:
        log.write(f"===== End =====\n")

def log_colored_message(log_folder, website_url, message, color):
    prefix = {'yellow': '[warning]', 'red': '[danger]', 'cyan': '[info]', 'green': '[success]'}.get(color, '')
    log_message(log_folder, website_url, f"{prefix} {message}")
    print(colored(message, color))

def download_file(url, base_folder, retries=1, log_folder=None, website_url=None, base_domain=None):
    attempt = 0
    normalized_url = normalize_url_case(url)

    while attempt < retries:
        try:
            if normalized_url in downloaded_files:
                log_colored_message(log_folder, website_url, f"Skipped (already downloaded): {url}", 'yellow')
                return

            if not is_valid_link(url, base_domain):
                log_colored_message(log_folder, website_url, f"Invalid or external URL: {url}", 'yellow')
                return

            response = requests.get(url)
            if response.status_code == 200:
                parsed_url = urlparse(url)
                file_name = os.path.basename(parsed_url.path) or 'index.html'
                folder_path = os.path.join(base_folder, os.path.dirname(parsed_url.path).lstrip('/'))
                folder_path = normalize_path_case(folder_path)
                create_folder(folder_path)

                file_path = os.path.join(folder_path, file_name)
                file_path = normalize_path_case(file_path)

                with open(file_path, 'wb') as file:
                    file.write(response.content)
                log_colored_message(log_folder, website_url, f"Downloaded: {file_path}", 'green')

                if file_name.endswith('.css'):
                    parse_css_for_resources(file_path, url, base_folder, log_folder, website_url, base_domain)
                elif file_name.endswith('.js'):
                    parse_js_for_resources(file_path, url, base_folder, log_folder, website_url, base_domain)

                pending_files.discard(normalized_url)
                downloaded_files.add(normalized_url)
                return

            else:
                log_colored_message(log_folder, website_url, f"Failed to download (HTTP {response.status_code}): {url}", 'red')
        except Exception as e:
            log_colored_message(log_folder, website_url, f"Error downloading {url}: {e}", 'red')

        attempt += 1
        if attempt < retries:
            log_colored_message(log_folder, website_url, f"Retrying ({attempt}/{retries}) for {url}...", 'cyan')
            time.sleep(1)

    log_colored_message(log_folder, website_url, f"Max retries reached for {url}. Skipping.", 'red')
    pending_files.add(normalized_url)

def parse_css_for_resources(css_file_path, base_url, base_folder, log_folder, website_url, base_domain):
    try:
        with open(css_file_path, 'r', encoding='utf-8') as file:
            css_content = file.read()

        font_face_pattern = r"@font-face\s*{[^}]*src:\s*([^;]+);"
        url_pattern = r"url\(['\"]?([^'\"]+)['\"]?\)"

        for match in re.finditer(font_face_pattern, css_content, re.IGNORECASE):
            src_declaration = match.group(1)
            for url_match in re.finditer(url_pattern, src_declaration):
                resource_url = url_match.group(1)
                full_url = urljoin(base_url, resource_url)
                if is_valid_link(full_url, base_domain):
                    download_file(full_url, base_folder, log_folder=log_folder, website_url=website_url, base_domain=base_domain)

        for match in re.finditer(url_pattern, css_content):
            resource_url = match.group(1)
            full_url = urljoin(base_url, resource_url)
            if is_valid_link(full_url, base_domain):
                download_file(full_url, base_folder, log_folder=log_folder, website_url=website_url, base_domain=base_domain)

    except Exception as e:
        log_colored_message(log_folder, website_url, f"Error reading CSS file {css_file_path}: {e}", 'red')

def parse_js_for_resources(js_file_path, base_url, base_folder, log_folder, website_url, base_domain):
    try:
        with open(js_file_path, 'r', encoding='utf-8') as file:
            js_content = file.read()

        for line in js_content.splitlines():
            if 'http' in line or 'url(' in line:
                try:
                    if 'url(' in line:
                        resource_url = line.split('url(')[-1].split(')')[0].replace('"', '').replace("'", '')
                    else:
                        resource_url = line.split('"')[1] if '"' in line else line.split("'")[1]
                    full_url = urljoin(base_url, resource_url)
                    if is_valid_link(full_url, base_domain):
                        download_file(full_url, base_folder, log_folder=log_folder, website_url=website_url, base_domain=base_domain)
                except Exception as e:
                    log_colored_message(log_folder, website_url, f"Error parsing JS resource: {line}, {e}", 'red')
    except Exception as e:
        log_colored_message(log_folder, website_url, f"Error reading JS file {js_file_path}: {e}", 'red')

def scrape_page(page_url, download_folder, visited_urls, log_folder):
    try:
        parsed_base_url = urlparse(page_url)
        base_domain = parsed_base_url.netloc

        normalized_page_url = normalize_url_case(page_url)
        if normalized_page_url in visited_urls:
            return

        visited_urls.add(normalized_page_url)
        response = requests.get(page_url)
        if response.status_code != 200:
            log_colored_message(log_folder, page_url, f"Failed to fetch page (HTTP {response.status_code}): {page_url}", 'red')
            return

        soup = BeautifulSoup(response.text, 'html.parser')

        log_message(log_folder, page_url, f"===== Begin {page_url} =====")

        parsed_url = urlparse(page_url)
        base_path = os.path.dirname(parsed_url.path).lstrip('/')
        base_path = normalize_path_case(base_path)
        create_folder(os.path.join(download_folder, base_path))

        html_file_path = os.path.join(download_folder, base_path, os.path.basename(parsed_url.path) or 'index.html')
        html_file_path = normalize_path_case(html_file_path)
        with open(html_file_path, 'w', encoding='utf-8') as file:
            file.write(soup.prettify())
        log_colored_message(log_folder, page_url, f"Downloaded: {html_file_path}", 'green')

        for tag, attr in [('link', 'href'), ('script', 'src'), ('img', 'src'), ('video', 'src')]:
            for resource in soup.find_all(tag):
                resource_url = resource.get(attr)
                if resource_url:
                    full_url = urljoin(page_url, resource_url)
                    if is_valid_link(full_url, base_domain):
                        download_file(full_url, download_folder, log_folder=log_folder, website_url=page_url, base_domain=base_domain)

        for div in soup.find_all(style=True):
            style = div['style']
            if 'url(' in style:
                try:
                    url_pattern = r"url\(['\"]?([^'\"]+)['\"]?\)"
                    img_url = re.search(url_pattern, style).group(1)
                    full_url = urljoin(page_url, img_url)
                    if is_valid_link(full_url, base_domain):
                        download_file(full_url, download_folder, log_folder=log_folder, website_url=page_url, base_domain=base_domain)
                except Exception as e:
                    log_colored_message(log_folder, page_url, f"Error parsing style: {style}, {e}", 'red')

        for link in soup.find_all('a', href=True):
            href = link['href']
            full_url = urljoin(page_url, href)
            if is_valid_link(full_url, base_domain) and urlparse(full_url).netloc == base_domain:
                scrape_page(full_url, download_folder, visited_urls, log_folder)

        for pending_url in list(pending_files):
            download_file(pending_url, download_folder, log_folder=log_folder, website_url=page_url, base_domain=base_domain)

        finalize_log(log_folder, page_url)

    except Exception as e:
        log_colored_message(log_folder, page_url, f"Error scraping {page_url}: {e}", 'red')

def main():
    page_url = input("Masukkan URL halaman untuk memulai scrapping: ").strip()
    download_folder = 'downloaded_assets'
    log_folder = 'logs'
    create_folder(download_folder)
    scrape_page(page_url, download_folder, set(), log_folder)
    print(colored("Semua sumber daya berhasil diunduh.", 'green'))

if __name__ == "__main__":
    main()
