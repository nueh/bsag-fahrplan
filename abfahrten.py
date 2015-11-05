#!/usr/bin/env python
# -*- coding: utf-8 -*-
 
from __future__ import division
from __future__ import absolute_import
from HAFASProvider import HAFASProvider
import json
from datetime import datetime
import sys
import getopt

optlist, args = getopt.getopt(sys.argv[1:], u'q:f:')
options = {}
for key,val in optlist:
    options[key] = val

if not u'-q' in options:
    options[u'-q'] = u"HB Kurfürstenallee".encode('utf-8')

h = HAFASProvider()

res,conns = h.get_stboard(query=options[u'-q'])

i = 0
for x in conns:
    #print(datetime.fromtimestamp(x['time'], tzinfo=tz).strftime('%H:%M:%S') + '\t' +  x['name']['normal'] + "\t" + x['direction']['normal'])
    if x[u'delay']/60 > 0:
        print x[u'time'] + u'\t' +  x[u'name'][u'normal'] + u"\t" + x[u'direction'][u'normal'] + u"\t + " + u"{:.0f}".format(x[u'delay']/60)
    else:
        print x[u'time'] + u'\t' +  x[u'name'][u'normal'] + u"\t" + x[u'direction'][u'normal']
    if i > 20: break
    i += 1


#print (json.dumps(conns, sort_keys=True,
#                  indent=4, separators=(',', ': ')))
