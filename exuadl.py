#!/usr/bin/python
import re, sys, os, getopt, glob, shutil, urllib
import subprocess
import time
import collections
import threading

__author__ = 'vbuell'

# TODO:
# - Add downloading resume for directory of links
# - Add support for single files
# - Store list of already downloaded files in working directory

class AnsiFormatter(object):
    def fail(self, txt):
        return "\033[31m"+txt+"\033[0m"

    def error(self, txt):
        return "\033[31m\033[1m"+txt+"\033[0m"

    def warn(self, txt):
        return "\033[33m"+txt+"\033[0m"

    def invert(self, txt):
    #    return "\033[7m"+txt+"\033[0m"
        return "\033[40m\033[37m"+txt+"\033[0m"

    def ok(self, txt):
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


class WgetInstance():
    def __init__(self, url):
        self.percentage = 0
        self.downloaded = 0
        self.speed = 0
        self.error = None
        self.popen = subprocess.Popen("wget -c --progress=bar:force \"%s\"" % url, shell=True, stderr=subprocess.PIPE)
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

    def read_output(self, process, append):
        s = "\n"
        rest = ""
        while True:
            b = process.stderr.read(4)
            if not b:
                break
            ofs = 0
#            while True:
            chunks = re.split(r"[\n\r]", rest + b)
            rest = chunks.pop()
            for chunk in chunks:
                if not self.analyze_line(chunk):
                    append(chunk)

    num = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', ' ']

    wget_pattern = re.compile(r"^\s*(\d+)\%\s*\[[+>= ]+\]\s+([,\d]+)\s+([0-9.-]+[KM]/s)")

    def analyze_line(self, line):
        """
        Returns True if handled. If False, the string is unknown and should be
        appended to output log.
        """
        if len(line) == 0:
            return False
        first_char = line[0]
        if first_char in self.num:
            match = self.wget_pattern.search(line)
            if match:
                self.percentage = match.group(1)
                self.downloaded = match.group(2)
                self.speed = match.group(3)
                return True
        return False

    def get_status(self):
        """
        Returns status and percentage of download.
        """
        return (str(self.percentage) + "%", self.downloaded, self.speed)

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


class GetOutOfLoop(Exception):
    pass

def unique(seq, idfun=repr):
    seen = {}
    return [seen.setdefault(idfun(e),e) for e in seq if idfun(e) not in seen]

def get_real_url(url):
    while True:
        try:
            obj = urllib.urlopen(url)
            real_url = obj.geturl()
            return real_url
        except IOError, e:
            print e, "Retrying..."
            continue


def wget(url):
    print "Exuadl. Parallel downloader v0.30. http://code.google.com/p/exuadl/"
    print

    obj = urllib.urlopen(url)
    data = obj.read()
    obj.close()
    urls = re.findall(r'href=(?:"|\')(/get/[^"\']*)(?:"|\')', data)

    # Remove duplicates
    urls = unique(urls)
    print "Found " + str(len(urls)) + " entries."

    ansi = AnsiFormatter()

    # Save in file
    f = open(".exuadl", "w")
    f.write(url)
    f.close()

    threads = 2
    processes = []

    for url in urls:
        real_url = get_real_url("http://www.ex.ua" + url)
        filename = urllib.unquote(real_url.split('/')[-1])
        obj.close()

        print "downloading %s as '%s'..." % (url, filename)
#        popen = subprocess.Popen("wget -c \"%s\"" % real_url, shell=True) #, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        popen = WgetInstance(real_url)
        processes.append(popen)
        if len(processes) >= threads:
            # Wait for process to be finished
            while True:
                line = ""
                for process in processes[:]:
                    if process.is_terminated():
#                        print "wget instance is finished."
                        processes.remove(process)
                    out = process.get_output(clear=True)
                    if out.strip() != "":
                        print out
                    line += str(process.get_status()) + "    "

                if len(processes) < threads:
                    break

                # Show progress
                sys.stdout.write(ansi.ok(line) + "\r")
                sys.stdout.flush()

                time.sleep(0.3)


if len(sys.argv) == 1:
    try:
        f = open(".exuadl", "r")
        url = f.readline()
        wget(url)
    except IOError:
        print "Can't find saved session. Please specify url to start new download."
else:
    wget(sys.argv[1])


#w = WgetInstance("http://www.ex.ua/get/1494085")
#while True:
#    out = w.get_output(clear=True)
#    if out.strip() != "":
#        print out
#    print w.get_status()
#    if w.is_terminated():
#        print "finished"
#        break
#    time.sleep(0.5)
#
#
