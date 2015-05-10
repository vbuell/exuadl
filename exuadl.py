#!/usr/bin/env python3
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
from optparse import OptionParser


class AnsiFormatter(object):
    def __init__(self):
        self.last_line_is_progress = False
        self.last_line_len = 0

    def red(self, txt):
        return "\033[31m"+txt+"\033[0m"

    def error(self, txt):
        return "\033[31m\033[1m"+txt+"\033[0m"

    def warn(self, txt):
        return "\033[33m"+txt+"\033[0m"

    def invert(self, txt):
    #    return "\033[7m"+txt+"\033[0m"
        return "\033[40m\033[37m"+txt+"\033[0m"

    def green(self, txt):
        return "\033[32m"+txt+"\033[0m"

    def skip(self, txt):
        return "\033[34m\033[1m"+txt+"\033[0m"

    def black3(self, txt):
        return txt

    def black2(self, txt):
        return "\033[90m"+txt+"\033[0m"

    def black1(self, txt):
        return "\033[37m"+txt+"\033[0m"

    def black0(self, txt):
        return "\033[97m"+txt+"\033[0m"

    def print_progress(self, line):
        if self.last_line_is_progress and len(line) < self.last_line_len:
            sys.stdout.write(self.green(line) + " "*(self.last_line_len-len(line)) + "\r")
        else:
            sys.stdout.write(self.green(line) + "\r")
        sys.stdout.flush()
        self.last_line_is_progress = True
        self.last_line_len = len(line)

    def print_line(self, line):
        if self.last_line_is_progress:
            sys.stdout.write(" " * self.last_line_len + "\r")
        print(line)
        self.last_line_is_progress = False


class Options():
    pass


class WgetInstance():
    def __init__(self, url, cwd):
        self.percentage = 0
        self.downloaded = 0
        self.speed = 0
        self.error = None
        # If wget supports '--content-disposition' we can get rid of resolving
        self.popen = subprocess.Popen("wget -c --restrict-file-names=nocontrol --content-disposition --progress=bar:force \"%s\"" % url,
                                      shell=True, stderr=subprocess.PIPE, cwd=cwd)
        #, stdout=subprocess.PIPE)
        try:
            self.q = collections.deque(maxlen=128) # atomic .append()
            t = threading.Thread(target=self.read_output, args=(self.popen, self.q.append))
            t.daemon = True
            t.start()
#            time.sleep(2)
        finally:
            pass
#            process.terminate() #NOTE: it doesn't ensure the process termination

    def __del__(self):
        if not self.is_terminated():
            self.popen.terminate()

    def read_output(self, process, append):
        rest = ""
        while True:
            b = process.stderr.read(1024)
            if not b:
                break
            chunks = re.split(r'[\n\r]', rest + b.decode())
            rest = chunks.pop()
            for chunk in chunks:
                self.analyze_line(chunk, append)

    wget_pattern = re.compile(r"^\s*(\d+)%\s*\[[+>= ]+\]\s+([,\d]+)\s+([0-9.-]+[KM]?B?/s)")

    def analyze_line(self, line, append):
        if len(line) == 0:
            return
        match = self.wget_pattern.search(line)
        if match:
            self.percentage = match.group(1)
            self.downloaded = match.group(2)
            self.speed = match.group(3)
        elif line.find("annot") != -1:
            append(ansi.red(line))
            self.error = True
        else:
            append(line)

    def get_status(self):
        """
        Returns status and percentage of download.
        """
        return str(self.percentage) + "%", self.downloaded, self.speed

    def get_status_as_string(self):
        """
        Returns status and percentage of download as string.
        """
        if self.downloaded == 0:
            return "[Starting... ]"
        return "[%s, %s, %s]" % self.get_status()

    def get_output(self, clear=False):
        """
        TODO: Need to synchronize this
        """
        tmp = '\n'.join(self.q)
        if clear:
            self.q.clear()
        return tmp

    def get_ret_code(self):
        return self.popen.poll()

    def is_terminated(self):
        return self.get_ret_code() is not None


class WgetError(Exception):
    pass


class GetOutOfLoop(Exception):
    pass


def unique(seq, idfun=repr):
    seen = {}
    return [seen.setdefault(idfun(e), e) for e in seq if idfun(e) not in seen]


def get_real_url(url):
    while True:
        try:
            obj = urlopen(url)
            real_url = obj.geturl()
            # urlparsed = urllib.parse(real_url)
            # addr = urlparse.urlunparse((urlparsed[0],) + (socket.gethostbyname(urlparsed.hostname),) + urlparsed[2:])
            return real_url
        except IOError as e:
            ansi.print_line(str(e) + ". Retrying...")
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


def parse_file_urls(html_data):
    urls = re.findall(b'href=(?:"|\')(/get/[^"\']*)(?:"|\')', html_data)
    # Remove duplicates
    urls = unique(urls)
    return list(map(lambda s: s.decode(), urls))


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
        ansi.print_line('Scrapping page #%s...' % idx)
        file_url = urlopen(urllib.parse.urlunsplit(parsed_url[:3] + (filtered_query + 'p=%s' % idx,) + parsed_url[4:]))
        html_data = file_url.read()
        links = parse_links_urls(html_data)
        file_url.close()

        all_links.extend(links)

        if not re.findall(b"<img src='/t3/arr_e.gif", html_data):
            break

    return all_links


def parse_options(arg):
    parser = OptionParser()
    parser.add_option("-s", "--skip", dest="skip", type="int",
                      help="skip first N files", default=0)
    parser.add_option("-t", "--threads", dest="threads", type="int",
                      help="use N threads", default=2)
    parser.add_option("-p", "--level", dest="level", type="int",
                      help="directory level. 0 - download to current. 1 - create directory. 2 - create <parent_dir>/<dir>, etc",
                      default=0)
    parser.add_option("-f", "--fast",
                      action="store_true", dest="faststart", default=False,
                      help="use cached urls (only for resuming)")
    parser.add_option("-c", "--do-not-download",
                      action="store_true", dest="crawl", default=False,
                      help="crawl and create file structure but not download")
    parser.add_option("-q", "--quiet",
                      action="store_false", dest="verbose", default=True,
                      help="don't print status messages to stdout")
    (options, args) = parser.parse_args(args=arg)
    options.url = args[1]

    return options


def save_state_to_file(options):
    with open('.exuadl', 'w') as file_state:
        data = options.__dict__.copy()
        del data['crawl']
        json.dump(data, file_state, sort_keys=True, indent=4, separators=(',', ': '))


def load_state_from_file():
    try:
        with open('.exuadl', 'r') as f:
            # Try new format
            try:
                # Hack: python-dict-object
                class objectview(object):
                    def __init__(self, d):
                        self.__dict__ = d

                options = objectview(json.load(f))
            except ValueError:
                print(ansi.skip("Config file doesn't seem to be a valid json. Trying to parse it in old way... If succesfull, it will be converted to new json-based format"))
                # Handle old-style config. Do not forget to seek to 0 after json library...
                f.seek(0)
                url = f.readline()
                argss = url.split(" ")
                argss.insert(0, sys.argv[0])
                options = parse_options(argss)
            # This is kinda dirty. We shouldn't take level into account when loading the state from file, as we are
            # already in the right directory
            options.level = 0

            # Add new options
            if not hasattr(options, 'faststart'): options.faststart = False
            if not hasattr(options, 'crawl'): options.crawl = False
            if not hasattr(options, 'urls_original'): options.urls_original = []
            return options
    except IOError:
        raise WgetError("Can't find saved session. Please specify url to start new download.")


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
                ansi.print_line(ansi.red("Cannot read " + options.url))
                raise e
            ansi.print_line(str(e) + ". Retrying...")
            time.sleep(16 - count)
            count -= 1
            continue


def wget(options, exit_if_directory_exists=False, cwd=os.getcwd()):
    dirs = []
    cwd_original = os.getcwd()
    if not options.faststart or not options.urls_original:
        html_data = read_url_content(options)

        urls = parse_file_urls(html_data)
        # ansi.print_line("Found " + str(len(urls)) + " files. ")

        if not urls:
            dirs = parse_all_links_urls_paged(options.url)
            # ansi.print_line('Found %s dirs.' % len(dirs))

        if options.level >= 1:
            cwd_ = cwd + '/' + parse_folder_name(html_data)
            if options.level >= 2:
                cwd_ = cwd + '/' + parse_parent_folder_name(html_data) + '/' + cwd
            if not os.path.exists(cwd_):
                os.makedirs(cwd_)
            elif exit_if_directory_exists:
                print('Directory exists - skipping')
                return
            cwd = cwd_
        print('Working in %s dirs:%s files:%s' % (cwd, len(dirs), len(urls)))
        os.chdir(cwd)

        urls = map_to_full_url(urls[options.skip:])

        options.urls_original = urls

        # Save html
        fh = open('.html', 'wb')
        fh.write(html_data)
        fh.close()

        # Save in file
        save_state_to_file(options)
    else:
        urls = options.urls_original

    if not options.crawl:
        download_urls(urls, cwd, options)

    def fork_wget(dir_link):
        options_args = Options()
        options_args.level = 1
        options_args.skip = 0
        options_args.threads = 2
        options_args.crawl = True
        options_args.url = "http://www.ex.ua" + dir_link
        options_args.faststart = True
        options_args.urls_original = None
        wget(options_args, exit_if_directory_exists=True, cwd=cwd)

    list(executor.map(fork_wget, dirs))

    os.chdir(cwd_original)


def map_to_full_url(urls):
    return list(map(lambda a: "http://www.ex.ua" + a, urls))


def resolve_urls(urls):
    return list(map(get_real_url, urls))


def download_urls(urls, directory_path, options):
    processes = []

    try:
        iterator = urls.__iter__()
        current_url = next(iterator)
        while 1:
            if len(processes) < options.threads and current_url:
                resolved_url = current_url  # get_real_url(current_url)
                filename = urllib.parse.unquote(resolved_url.split('/')[-1])
                ansi.print_line("Downloading %s as '%s'..." % (current_url, filename))
                wget_downloader = WgetInstance(resolved_url, directory_path)
                processes.append(wget_downloader)
                try:
                    current_url = next(iterator)
                except StopIteration:
                    current_url = None

            processes_status_line = []
            for process in processes[:]:
                if process.error:
                    raise GetOutOfLoop()
                if process.is_terminated():
                    processes.remove(process)
                out = process.get_output(clear=True)
                if out.strip() != "":
                    ansi.print_line(ansi.black2(out))
                processes_status_line.append(ansi.invert(process.get_status_as_string()))

            # Show progress
            ansi.print_progress("    ".join(processes_status_line))

            if not current_url and len(processes) == 0:
                break

            time.sleep(0.3)
        ansi.print_line("Finished.")
    except GetOutOfLoop:
        # Show the rest
        for process in processes[:]:
            if process.is_terminated():
                processes.remove(process)
            out = process.get_output(clear=True)
            if out.strip() != "":
                ansi.print_line(ansi.black2(out))
        ansi.print_line("Terminating due to wget error.")


if __name__ == '__main__':
    print("Exuadl v0.40. Parallel recursive downloader.")
    print("Homepage: https://github.com/vbuell/exuadl")
    print()

    ansi = AnsiFormatter()
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=8)

    try:
        if len(sys.argv) == 1:
            wget(load_state_from_file())
        else:
            wget(parse_options(sys.argv))
    except WgetError as e:
        print(ansi.error(e.message))
