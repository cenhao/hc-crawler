#!/usr/bin/env python
# -*- coding: utf-8 -*-

import getopt
import httplib
import os
import re
import socket
import sys
import threading

usage =\
'''Usage:
    crawler.py -h
    crawler.py [-t <thread num>] [-p <path>] init_url'''
visited_url = {}
thread_num = 1
path = ''

try:
    optlist, args = getopt.getopt(sys.argv[1:], 't:p:h')
except getopt.GetoptError, e:
    print >> sys.stderr, e
    print >> sys.stderr, usage
    exit(1)

for opt, arg in optlist:
    if opt == '-t':
        try:
            thread_num = int(arg)
        except ValueError, e:
            print >> sys.stderr, 'Invalid thread num, it should be an integer.'
            exit(1)
    if opt == '-p':
        path = arg + os.sep
    elif opt == '-h':
        print usage
        exit(0)

if len(args) != 1:
    print >> sys.stderr, usage
    exit(1)

if not os.path.isdir(path):
    os.makedirs(path)

cnt = 0
queue = []
img_pattern = '<a href="(.*\.html)">.*<img class="photo" .* src="(.*)" />'
pattern = re.compile(img_pattern)
output_lock = threading.Lock()
job_lock = threading.Lock()
job_cond = threading.Condition(job_lock)
host, init_url = args[0].split('/')
url = '/' + init_url

def download():
    while True:
        job_cond.acquire()
        while len(queue) <= 0:
            job_cond.wait()

        job = queue.pop(0)
        job_cond.release()
        page, url = job

        if (page < 0):
            return
        while True:
            try:
                conn = httplib.HTTPConnection(host, timeout=2)
                conn.request('GET', url)
                res = conn.getresponse()
                if res.status != 200:
                    output_lock.acquire()
                    print >> sys.stderr, '[http:%d]Get page %d failed, url[%s]' % (res.status, page, url)
                    output_lock.release()
                    continue
                buff = res.read()
                break
            except (httplib.HTTPException, socket.timeout), e:
                output_lock.acquire()
                print >> sys.stderr, '[%s]Get Page %d failed, url[%s]' % (e, page, url)
                output_lock.release()
                continue

        filetype = url.split('.')[-1]
        filename = '%s%03d.%s' % (path, page, filetype)
        with open(filename, 'w') as fp:
            fp.write(buff)

threads = []

for i in xrange(0, thread_num):
    threads.append(threading.Thread(target=download))
    threads[i].start()

conn = httplib.HTTPConnection(host, timeout=3)

try:
    while url not in visited_url:
        while True:
            try:
                cnt += 1
                visited_url[url] = True
                conn.request('GET', url)
                res = conn.getresponse()
                if res.status != 200:
                    output_lock.acquire()
                    print >> sys.stderr, '[http:%d] Main %d failed, url[%s]' % (res.status, cnt, url)
                    output_lock.release()
                    continue
                matched = pattern.search(res.read())
                url = matched.group(1)
                pic = '/' + matched.group(2).split('/', 3)[3]
                print 'produce', cnt
                job_cond.acquire()
                queue.append((cnt, pic))
                job_cond.notify()
                job_cond.release()
                break
            except (httplib.HTTPException, socket.timeout), e:
                output_lock.acquire()
                print >> sys.stderr, '[%s] Main %d failed, url[%s]' % (e, cnt, url)
                output_lock.release()
except KeyboardInterrupt, e:
    job_cond.acquire()
    for i in xrange(0, thread_num):
        queue.append((-1, ''))
    job_cond.notify_all()
    job_cond.release()
finally:
    job_cond.acquire()
    for i in xrange(0, thread_num):
        queue.append((-1, ''))
    job_cond.notify_all()
    job_cond.release()

for i in xrange(0, thread_num):
    threads[i].join()

print 'Done'
