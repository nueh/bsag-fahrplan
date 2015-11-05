#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import absolute_import
from HAFASProvider import HAFASProvider
import json
from datetime import datetime
import getopt
import sys
# from io import open

optlist, args = getopt.getopt(sys.argv[1:], u'q:f:')
options = {}
for key,val in optlist:
    options[key] = val

if not u'-q' in options:
    options[u'-q'] = u"HB Kurfürstenallee".encode('utf-8')
if not u'-f' in options:
    print u"Missing target file name param '-f'"
    exit(1)

h = HAFASProvider()
res,conns = h.get_stboard(query=options[u'-q'])

#tz = pytz.timezone('Europe/Berlin')

data = json.dumps({ u'info' : res, u'connections': conns }, ensure_ascii=False, sort_keys=True,
                  indent=4, separators=(u',', u': ')).encode('utf-8')

print u"Writing to file " + options[u'-f']

f = open(options['-f'], "w")
f.write(data)
f.close()
