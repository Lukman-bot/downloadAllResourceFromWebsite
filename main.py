import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from termcolor import colored

def create_folder(path):
    if not os.path.exists(path):
        os.makedirs(path)

downloaded_files = set()

def download_file(url, base_folder):
    if url in downloaded_files:
        print(colored(f"Skipped (already downloaded): {url}", 'yellow'))
        return
    downloaded_files.add(url)
    response = requests.get(url)
    if response.status_code == 200:
        parsed_url = urlparse(url)
        file_name = os.path.basename(parsed_url.path)
        folder_path = os.path.join(base_folder, os.path.dirname(parsed_url.path).lstrip('/'))
        create_folder(folder_path)
        file_path = os.path.join(folder_path, file_name)
        with open(file_path, 'wb') as file:
            file.write(response.content)
        print(colored(f"Downloaded: {file_path}", 'green'))
    else:
        print(colored(f"Failed to download: {url}", 'red'))


def is_valid_link(link):
    # Ignore links with ID fragments
    return not urlparse(link).fragment

def scrape_page(page_url, download_folder, visited_urls):
    if page_url in visited_urls:
        return

    visited_urls.add(page_url)
    response = requests.get(page_url)
    if response.status_code != 200:
        print(colored(f"Failed to fetch page: {page_url}", 'red'))
        return

    soup = BeautifulSoup(response.text, 'html.parser')

    # Save the main HTML page
    parsed_url = urlparse(page_url)
    base_path = os.path.dirname(parsed_url.path).lstrip('/')
    create_folder(os.path.join(download_folder, base_path))
    html_file_path = os.path.join(download_folder, base_path, os.path.basename(parsed_url.path) or 'index.html')
    with open(html_file_path, 'w', encoding='utf-8') as file:
        file.write(soup.prettify())
    print(colored(f"Downloaded: {html_file_path}", 'green'))

    # Download CSS, JS, images, and font files
    for tag, attr in [('link', 'href'), ('script', 'src'), ('img', 'src')]:
        for resource in soup.find_all(tag):
            resource_url = resource.get(attr)
            if resource_url:
                full_url = urljoin(page_url, resource_url)
                if is_valid_link(full_url):
                    download_file(full_url, download_folder)

    # Download inline styles' background images
    for div in soup.find_all(style=True):
        style = div['style']
        if 'background' in style or 'background-image' in style:
            img_url = style.split('url(')[-1].split(')')[0].replace('"', '').replace("'", '')
            full_url = urljoin(page_url, img_url)
            if is_valid_link(full_url):
                download_file(full_url, download_folder)

    # Recursively download linked HTML pages
    for link in soup.find_all('a', href=True):
        href = link['href']
        full_url = urljoin(page_url, href)
        if is_valid_link(full_url) and urlparse(full_url).netloc == urlparse(page_url).netloc:
            scrape_page(full_url, download_folder, visited_urls)

def main():
    page_url = input("Masukkan URL halaman untuk memulai scrapping: ").strip()
    download_folder = 'downloaded_assets'
    create_folder(download_folder)
    scrape_page(page_url, download_folder, set())
    print(colored("Semua sumber daya berhasil diunduh.", 'green'))

if __name__ == "__main__":
    main()
