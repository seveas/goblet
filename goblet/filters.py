# Goblet - Web based git repository browser
# Copyright (C) 2012-2014 Dennis Kaarsemaker
# See the LICENSE file for licensing details

from flask import current_app as app, url_for
from jinja2 import Markup, escape, Undefined
from collections import defaultdict
import hashlib
from goblet.memoize import memoize
from goblet.encoding import decode as decode_
import stat
import time
import re

filters = {}
def filter(name_or_func):
    if callable(name_or_func):
        filters[name_or_func.__name__] = name_or_func
        return name_or_func
    def decorator(func):
        filters[name_or_func] = func
        return func
    return decorator

@filter('gravatar')
@memoize
def gravatar(email, size=21):
    return 'http://www.gravatar.com/avatar/%s?s=%d&d=mm' % (hashlib.md5(email).hexdigest(), size)

@filter
def humantime(ctime):
    timediff = time.time() - ctime
    if timediff < 0:
        return 'in the future'
    if timediff < 60:
        return 'just now'
    if timediff < 120:
        return 'a minute ago'
    if timediff < 3600:
        return "%d minutes ago" % (timediff / 60)
    if timediff < 7200:
        return "an hour ago"
    if timediff < 86400:
        return "%d hours ago" % (timediff / 3600)
    if timediff < 172800:
        return "a day ago"
    if timediff < 2592000:
        return "%d days ago" % (timediff / 86400)
    if timediff < 5184000:
        return "a month ago"
    if timediff < 31104000:
        return "%d months ago" % (timediff / 2592000)
    if timediff < 62208000:
        return "a year ago"
    return "%d years ago" % (timediff / 31104000)

@filter
def shortmsg(message):
    message += "\n"
    short, long = message.split('\n', 1)
    if len(short) > 80:
        short = escape(short[:short.rfind(' ',0,80)]) + Markup('&hellip;')
    return short

@filter
def longmsg(message):
    message += "\n"
    short, long = message.split('\n', 1)
    if len(short) > 80:
        long = message
    long = re.sub(r'^[-a-z]+(-[a-z]+)*:.+\n', '', long, flags=re.MULTILINE|re.I).strip()
    if not long:
        return ""
    return Markup('<pre class="invisible">%s</pre>') % escape(long)

@filter
def acks(message):
    if '\n' not in message:
        return []
    acks = defaultdict(list)
    for ack, who in re.findall(r'^([-a-z]+(?:-[a-z]+)*):(.+?)(?:<.*)?\n', message.split('\n', 1)[1], flags=re.MULTILINE|re.I):
        ack = ack.lower().replace('-', ' ')
        ack = ack[0].upper() + ack[1:] # Can't use title
        acks[ack].append(who.strip())
    return sorted(acks.items())

@filter
def strftime(timestamp, format):
    return time.strftime(format, time.gmtime(timestamp))

@filter
def decode(data):
    return decode_(data)

@filter
def ornull(data):
    if isinstance(data, list):
        for d in data:
            if not isinstance(d, Undefined):
                data = d
                break
        else:
            return 'null'
    if isinstance(data, Undefined):
        return 'null'
    for attr in ('name', 'hex'):
        data = getattr(data, attr, data)
    return Markup('"%s"') % data

@filter
def highlight(data, search):
    return Markup(data).replace(Markup(search), Markup('<span class="searchresult">%s</span>' % Markup(search)))

@filter
def dlength(diff):
    return len(list(diff))

def register_filters(app):
    app.jinja_env.filters.update(filters)
