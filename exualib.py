import re, sys, urllib, os
import subprocess
import time
import collections
import threading
import json
import itertools
import urllib.parse
import socket
from urllib.request import urlopen
import concurrent.futures
import html
import exualib
from optparse import OptionParser


def unique(seq, idfun=repr):
    seen = {}
    return [seen.setdefault(idfun(e), e) for e in seq if idfun(e) not in seen]


def map_to_full_url(urls):
    return list(map(lambda a: "http://www.ex.ua" + a, urls))


def get_real_url(url):
    while True:
        try:
            obj = urlopen(url)
            real_url = obj.geturl()
            # urlparsed = urllib.parse(real_url)
            # addr = urlparse.urlunparse((urlparsed[0],) + (socket.gethostbyname(urlparsed.hostname),) + urlparsed[2:])
            return real_url
        except IOError as e:
            print(str(e) + ". Retrying...")
            continue


def parse_folder_name(data):
    # Name of the folder
    names = re.findall(b'<meta name="title" content="(.+)">', data)
    if len(names) != 1:
        raise RuntimeError("Can't parse folder name")
    name = re.sub(r'[/:]', '_', urllib.parse.unquote(names[0].decode()))
    while len(name.encode()) > 255:
        name = name[:-1]
    return html.unescape(name)


def parse_parent_folder_name(data):
    # Name of parent folder (the most top string in the page)
    groups = re.findall(r'<h2>([^<]+)</h2>', data)
    if len(groups) != 1:
        raise RuntimeError("Can't parse parent folder name")
    group = re.sub(r'[/:]', '_', urllib.unquote(groups[0].decode()))
    return html.unescape(group)


def parse_url(base_url):
    # TODO
    pass


def parse_file_urls(html_data):
    urls = re.findall(b'href=(?:"|\')(/get/[^"\']*)(?:"|\')', html_data)
    # Remove duplicates
    urls = unique(urls)
    return map_to_full_url(map(lambda s: s.decode(), urls))


def parse_links_urls(html_data):
    urls = re.findall(b'<p><a href=(?:"|\')(/[0-9]+)\?r=[0-9]+(?:"|\')><b>', html_data)
    # Remove duplicates
    urls = unique(urls)
    return list(map(lambda s: s.decode(), urls))


def parse_all_links_urls_paged(url):
    all_links = []
    parsed_url = urllib.parse.urlsplit(url)
    filtered_query = '&'.join(i for i in parsed_url.query.split('&') if not i.startswith('p='))

    for idx in itertools.count():
        print('Scrapping page #%s...' % idx)
        file_url = urlopen(urllib.parse.urlunsplit(parsed_url[:3] + (filtered_query + 'p=%s' % idx,) + parsed_url[4:]))
        html_data = file_url.read()
        links = parse_links_urls(html_data)
        file_url.close()

        all_links.extend(links)

        if not re.findall(b"<img src='/t3/arr_e.gif", html_data):
            break

    return all_links


def read_url_content(options):
    count = 15
    while True:
        try:
            # ansi.print_line("Fetching list of files to download... ")
            file_url = urlopen(options.url)
            # html_data = UnicodeDammit(file_url.read(), smart_quotes_to="ascii").unicode_markup
            html_data = file_url.read()
            file_url.close()
            return html_data
        except (urllib.error.HTTPError, socket.gaierror, urllib.error.URLError) as e:
            if count < 1:
                print("Cannot read " + options.url)
                raise e
            print(str(e) + ". Retrying...")
            time.sleep(16 - count)
            count -= 1
            continue
