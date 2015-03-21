#!/usr/bin/python
import re, sys, urllib
import subprocess
import time
import collections
import threading
from optparse import OptionParser

__author__ = 'vbuell'
# TODO:
# - Add downloading resume for directory of links
# - Add support for single files
# - Store list of already downloaded files in working directory
# - Ask user if resume file is already exists and new are gonna be created


class AnsiFormatter(object):
    def __init__(self):
        self.last_line_is_progress = False
        self.last_line_len = 0

    def fail(self, txt):
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

    def home(self):
        return "\033[2J\033[H"

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
        print line
        self.last_line_is_progress = False


class WgetInstance():
    def __init__(self, url):
        self.percentage = 0
        self.downloaded = 0
        self.speed = 0
        self.error = None
        # If wget supports '--content-disposition' we can get rid of resolving
        self.popen = subprocess.Popen("wget -c --restrict-file-names=nocontrol --progress=bar:force \"%s\"" % url, shell=True, stderr=subprocess.PIPE)
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
            ofs = 0
#            while True:
            chunks = re.split(r"[\n\r]", rest + b)
            rest = chunks.pop()
            for chunk in chunks:
                self.analyze_line(chunk, append)

    wget_pattern = re.compile(r"^\s*(\d+)\%\s*\[[+>= ]+\]\s+([,\d]+)\s+([0-9.-]+[KM]?B?/s)")

    def analyze_line(self, line, append):
        if len(line) == 0:
            return
        match = self.wget_pattern.search(line)
        if match:
            self.percentage = match.group(1)
            self.downloaded = match.group(2)
            self.speed = match.group(3)
        elif line.find("annot") != -1:
            append(ansi.fail(line))
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
            obj = urllib.urlopen(url)
            real_url = obj.geturl()
            return real_url
        except IOError, e:
            ansi.print_line(str(e) + ". Retrying...")
            continue


def resolver(urls, real_filenames):
    ansi.print_line(ansi.black2("Resolver started."))
    for url in urls:
        real_url = get_real_url("http://www.ex.ua" + url)
        real_filenames[url] = real_url


def wget(arg):
    parser = OptionParser()
    parser.add_option("-s", "--skip", dest="skip",
                      help="skip first N files", default=0)
    parser.add_option("-t", "--threads", dest="threads",
                      help="use N threads", default=2)
    parser.add_option("-q", "--quiet",
                      action="store_false", dest="verbose", default=True,
                      help="don't print status messages to stdout")

    (options, args) = parser.parse_args(args=arg)

    url = args[1]

    print "Exuadl v0.31. Parallel recursive downloader."
    print "Homepage: http://code.google.com/p/exuadl/"
    print

    # Save in file
    f = open(".exuadl", "w")
    f.write(" ".join(arg[1:]))
    f.close()

    sys.stdout.write("Fetching list of files to download... ")
    obj = urllib.urlopen(url)
    data = obj.read()
    obj.close()
    urls = re.findall(r'href=(?:"|\')(/get/[^"\']*)(?:"|\')', data)

    # Remove duplicates
    urls = unique(urls)
    print "Found " + str(len(urls)) + " files."

    urls = urls[int(options.skip):]

    threads = int(options.threads)
    processes = []
    real_filenames = {}

    t1 = threading.Thread(target=resolver, args=(urls[::2], real_filenames))
    t1.daemon = True
    t1.start()
    t2 = threading.Thread(target=resolver, args=(urls[1::2], real_filenames))
    t2.daemon = True
    t2.start()

    try:
        iterator = urls.__iter__()
        current_url = iterator.next()
        while 1:
            if len(processes) < threads and current_url and current_url in real_filenames:
                filename = urllib.unquote(real_filenames[current_url].split('/')[-1])
                print "Downloading %s as '%s'..." % (current_url, filename)
                popen = WgetInstance(real_filenames[current_url])
                processes.append(popen)
                try:
                    current_url = iterator.next()
                except:
                    current_url = None

            line = ""
            for process in processes[:]:
                if process.error:
                    raise WgetError()
                if process.is_terminated():
                    processes.remove(process)
                out = process.get_output(clear=True)
                if out.strip() != "":
                    ansi.print_line(ansi.black2(out))
                line += ansi.invert(process.get_status_as_string()) + "    "

            # Show progress
            ansi.print_progress(line)

            if not current_url and len(processes) == 0:
                break

            time.sleep(0.3)
        ansi.print_line("Finished.")
    except WgetError:
        # Show the rest
        for process in processes[:]:
            if process.is_terminated():
                processes.remove(process)
            out = process.get_output(clear=True)
            if out.strip() != "":
                ansi.print_line(ansi.black2(out))
        ansi.print_line("Terminating due to wget error.")


if __name__ == '__main__':
    ansi = AnsiFormatter()

    if len(sys.argv) == 1:
        try:
            f = open(".exuadl", "r")
            url = f.readline()
            argss = url.split(" ")
            argss.insert(0, sys.argv[0])
        except IOError:
            print "Can't find saved session. Please specify url to start new download."
        else:
            wget(argss)
    else:
        wget(sys.argv)
