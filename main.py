import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from termcolor import colored

def create_folder(path):
    if not os.path.exists(path):
        os.makedirs(path)

def download_file(url, base_folder, sub_folder):
    response = requests.get(url)
    if response.status_code == 200:
        parsed_url = urlparse(url)
        file_name = os.path.basename(parsed_url.path)
        file_path = os.path.join(base_folder, sub_folder, file_name)
        create_folder(os.path.dirname(file_path))
        with open(file_path, 'wb') as file:
            file.write(response.content)
        print(colored(f"Downloaded: {file_path}", 'green'))
    else:
        print(colored(f"Failed to download: {url}", 'red'))

def get_sub_folder(url, base_url):
    parsed_base_url = urlparse(base_url)
    parsed_url = urlparse(url)
    base_path = os.path.dirname(parsed_base_url.path)
    relative_path = parsed_url.path.replace(base_path, '').lstrip('/')
    return os.path.dirname(relative_path)

def download_assets(page_url, download_folder):
    create_folder(download_folder)

    response = requests.get(page_url)
    soup = BeautifulSoup(response.text, 'html.parser')

    # Save the main HTML page
    html_file_path = os.path.join(download_folder, os.path.basename(urlparse(page_url).path))
    with open(html_file_path, 'w', encoding='utf-8') as file:
        file.write(soup.prettify())
    print(colored(f"Downloaded: {html_file_path}", 'green'))

    # Download CSS files
    for link in soup.find_all('link', rel='stylesheet'):
        css_url = urljoin(page_url, link['href'])
        sub_folder = get_sub_folder(css_url, page_url)
        download_file(css_url, download_folder, sub_folder)

        # Check for font files in the CSS
        css_response = requests.get(css_url)
        css_soup = BeautifulSoup(css_response.text, 'html.parser')
        for font_url in css_soup.find_all('@font-face'):
            font_url = font_url.get('src')
            if font_url:
                font_url = urljoin(css_url, font_url.split('url(')[-1].split(')')[0].replace('\'', '').replace('\"', ''))
                sub_folder = get_sub_folder(font_url, page_url)
                download_file(font_url, download_folder, sub_folder)

    # Download JavaScript files
    for script in soup.find_all('script', src=True):
        js_url = urljoin(page_url, script['src'])
        sub_folder = get_sub_folder(js_url, page_url)
        download_file(js_url, download_folder, sub_folder)

    # Download font files
    for link in soup.find_all('link', rel='preload', as_='font'):
        font_url = urljoin(page_url, link['href'])
        sub_folder = get_sub_folder(font_url, page_url)
        download_file(font_url, download_folder, sub_folder)

    # Download images
    for img in soup.find_all('img', src=True):
        img_url = urljoin(page_url, img['src'])
        sub_folder = get_sub_folder(img_url, page_url)
        download_file(img_url, download_folder, sub_folder)
    
    # Download background images from inline styles
    for div in soup.find_all(style=True):
        style = div['style']
        if 'background' in style or 'background-image' in style:
            img_url = style.split('url(')[-1].split(')')[0].replace('\'', '').replace('\"', '')
            img_url = urljoin(page_url, img_url)
            sub_folder = get_sub_folder(img_url, page_url)
            download_file(img_url, download_folder, sub_folder)

    print(colored("All assets downloaded.", 'green'))

# Meminta input dari pengguna untuk URL
page_url = input("Masukkan URL halaman untuk mendownload assets: ")
download_folder = 'downloaded_assets'
download_assets(page_url, download_folder)
