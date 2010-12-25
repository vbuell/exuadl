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

class WgetInstance():
    def __init__(self, url):
        self.percentage = 0
        self.error = None
        self.popen = subprocess.Popen("wget -c \"%s\"" % url, shell=True, stderr=subprocess.PIPE) #, stdout=subprocess.PIPE)
        try:
            # save last `number_of_lines` lines of the process output
            number_of_lines = 200
            self.q = collections.deque(maxlen=number_of_lines) # atomic .append()
            t = threading.Thread(target=self.read_output, args=(self.popen, self.q.append))
            t.daemon = True
            t.start()
#            time.sleep(2)
        finally:
            pass
#            process.terminate() #NOTE: it doesn't ensure the process termination
        # create thread with wget

    def read_output(self, process, append):
        for line in iter(process.stderr.readline, ""):
            print "<<<", line
            append(line)

    def get_status(self):
        """
        Returns status and percentage of download.
        """
        return (self.percentage, self.error)

    def get_output(self):
        return '\n'.join(self.q)

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
#    global w
#    if w == 0: w = len(url)
    obj = urllib.urlopen(url)
    data = obj.read()
    obj.close()
    urls = re.findall(r'href=(?:"|\')(/get/[^"\']*)(?:"|\')', data)
    print urls

    # Remove duplicates
    urls = unique(urls)
    print "Found " + str(len(urls)) + " entries."

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
        popen = subprocess.Popen("wget -c \"%s\"" % real_url, shell=True) #, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        processes.append(popen)
        if len(processes) >= threads:
            # Wait for process to be finished
            while True:
                for process in processes[:]:
                    exit_code = process.poll()
                    if exit_code != None:
                        # the process has terminated.
                        print "wget instance is finished."
                        processes.remove(process)
#                    else:
#                        print "In else"
#                        o = process.stdout.readline()
#                        print "After stdout readline"
#                        err = process.stderr.readline()
#                        print "After stderr readline"
#                        print o, err
#                        if o == '' and process.poll() != None: break
                if len(processes) < threads:
                    break
                time.sleep(0.5)


#    with urllib.urlopen(url) as f:
#        for u in f:
#            print u
#            s = u.decode('latin1')
#            m = re.search('<li>.*href="([^\.].*)"', s)
#            if m:
#                t = url + m.group(1)
#                if t[-1] == '/': wget(t)
#                else:
#                    d = os.path.dirname(t[w:])
#                    if d == '': d = './'
#                    if not os.path.exists(d): os.makedirs(os.path.dirname(t[w:]))
#                    sys.stdout.write(" %s \r" % (" " * 50))
#                    print('GET', t)
#                    urllib2.urlretrieve(t, t[w:], wbar)

                # Real start


if len(sys.argv) == 1:
    try:
        f = open(".exuadl", "r")
        url = f.readline()
        wget(url)
    except IOError:
        print "Can't find saved session. Please "
else:
    wget(sys.argv[1])
