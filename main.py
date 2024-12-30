import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from termcolor import colored
import re
import time

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

def download_file(url, base_folder, retries=2): # retries = Maksimal Pengulangan
    attempt = 0
    normalized_url = normalize_url_case(url)

    while attempt < retries:
        try:
            if normalized_url in downloaded_files:
                print(colored(f"Skipped (already downloaded): {url}", 'yellow'))
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
                print(colored(f"Downloaded: {file_path}", 'green'))

                if file_name.endswith('.css'):
                    parse_css_for_resources(file_path, url, base_folder)
                elif file_name.endswith('.js'):
                    parse_js_for_resources(file_path, url, base_folder)

                pending_files.discard(normalized_url)
                downloaded_files.add(normalized_url)
                return

            else:
                print(colored(f"Failed to download (HTTP {response.status_code}): {url}", 'red'))
        except Exception as e:
            print(colored(f"Error downloading {url}: {e}", 'red'))
        
        attempt += 1
        if attempt < retries:
            for remaining in range(0, 0, -1): # Waktu jeda pengulangan
                print(colored(f"Retrying ({attempt}/{retries}) for {url} in {remaining} seconds...", 'cyan'), end='\r')
                time.sleep(1)
            print(" " * 80, end='\r')

    print(colored(f"Max retries reached for {url}. Skipping.", 'red'))
    pending_files.add(normalized_url)

def parse_css_for_resources(css_file_path, base_url, base_folder):
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
                if is_valid_link(full_url):
                    download_file(full_url, base_folder)

        for match in re.finditer(url_pattern, css_content):
            resource_url = match.group(1)
            full_url = urljoin(base_url, resource_url)
            if is_valid_link(full_url):
                download_file(full_url, base_folder)

    except Exception as e:
        print(colored(f"Error reading CSS file {css_file_path}: {e}", 'red'))

def parse_js_for_resources(js_file_path, base_url, base_folder):
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
                    if is_valid_link(full_url):
                        download_file(full_url, base_folder)
                except Exception as e:
                    print(colored(f"Error parsing JS resource: {line}, {e}", 'red'))
    except Exception as e:
        print(colored(f"Error reading JS file {js_file_path}: {e}", 'red'))

def is_valid_link(link):
    try:
        return bool(urlparse(link).scheme and urlparse(link).netloc)
    except Exception as e:
        print(colored(f"Invalid link {link}: {e}", 'red'))
        return False

def scrape_page(page_url, download_folder, visited_urls):
    try:
        normalized_page_url = normalize_url_case(page_url)
        if normalized_page_url in visited_urls:
            return

        visited_urls.add(normalized_page_url)
        response = requests.get(page_url)
        if response.status_code != 200:
            print(colored(f"Failed to fetch page (HTTP {response.status_code}): {page_url}", 'red'))
            return

        soup = BeautifulSoup(response.text, 'html.parser')

        parsed_url = urlparse(page_url)
        base_path = os.path.dirname(parsed_url.path).lstrip('/')
        base_path = normalize_path_case(base_path)
        create_folder(os.path.join(download_folder, base_path))

        html_file_path = os.path.join(download_folder, base_path, os.path.basename(parsed_url.path) or 'index.html')
        html_file_path = normalize_path_case(html_file_path)
        with open(html_file_path, 'w', encoding='utf-8') as file:
            file.write(soup.prettify())
        print(colored(f"Downloaded: {html_file_path}", 'green'))

        for tag, attr in [('link', 'href'), ('script', 'src'), ('img', 'src'), ('video', 'src')]:
            for resource in soup.find_all(tag):
                resource_url = resource.get(attr)
                if resource_url:
                    full_url = urljoin(page_url, resource_url)
                    if is_valid_link(full_url):
                        download_file(full_url, download_folder)

        for div in soup.find_all(style=True):
            style = div['style']
            if 'url(' in style:
                try:
                    url_pattern = r"url\(['\"]?([^'\"]+)['\"]?\)"
                    img_url = re.search(url_pattern, style).group(1)
                    full_url = urljoin(page_url, img_url)
                    if is_valid_link(full_url):
                        download_file(full_url, download_folder)
                except Exception as e:
                    print(colored(f"Error parsing style: {style}, {e}", 'red'))

        for link in soup.find_all('a', href=True):
            href = link['href']
            full_url = urljoin(page_url, href)
            if is_valid_link(full_url) and urlparse(full_url).netloc == urlparse(page_url).netloc:
                scrape_page(full_url, download_folder, visited_urls)

        for pending_url in list(pending_files):
            download_file(pending_url, download_folder)

    except Exception as e:
        print(colored(f"Error scraping {page_url}: {e}", 'red'))

def main():
    page_url = input("Masukkan URL halaman untuk memulai scrapping: ").strip()
    download_folder = 'downloaded_assets'
    create_folder(download_folder)
    scrape_page(page_url, download_folder, set())
    print(colored("Semua sumber daya berhasil diunduh.", 'green'))

if __name__ == "__main__":
    main()
