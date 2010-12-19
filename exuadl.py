#!/usr/bin/python
import re, sys, os, getopt, glob, shutil, urllib
import subprocess
import time

__author__ = 'vbuell'

class GetOutOfLoop( Exception ):
    pass

def unique(seq, idfun=repr):
    seen = {}
    return [seen.setdefault(idfun(e),e) for e in seq if idfun(e) not in seen]

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

    threads = 1;
    processes = []

    for url in urls:
        obj = urllib.urlopen("http://www.ex.ua" + url)
        real_url = obj.geturl()
        filename = urllib.unquote(obj.geturl().split('/')[-1])
        obj.close()

        print "downloading %s as '%s'..." % (url, filename)
        popen = subprocess.Popen("wget -c \"%s\"" % real_url, shell=True)
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
                if len(processes) < threads:
                    break
                time.sleep(1)


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

wget(sys.argv[1])
