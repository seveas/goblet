# Goblet - Web based git repository browser
# Copyright (C) 2012-2014 Dennis Kaarsemaker
# See the LICENSE file for licensing details

from flask import url_for
from jinja2 import Markup, escape
import pygments
import pygments.formatters
import pygments.lexers
from goblet.encoding import decode
from whelk import shell

import re
import markdown as markdown_
import docutils.core
import time

renderers = {}
image_exts = ('.gif', '.png', '.bmp', '.tif', '.tiff', '.jpg', '.jpeg', '.ppm',
    '.pnm', '.pbm', '.pgm', '.webp', '.ico')

def render(repo, ref, path, entry, plain=False, blame=False):
    renderer = detect_renderer(repo, entry)
    if plain:
        if renderer[0] in ('rest', 'markdown'):
            renderer = ('code', pygments.lexers.get_lexer_for_filename(path))
        elif renderer[0] == 'man':
            renderer = ('code', pygments.lexers.get_lexer_by_name('groff'))
    if blame:
        if renderer[0] in ('rest', 'markdown'):
            renderer = ('code', pygments.lexers.get_lexer_for_filename(path), None, True)
        elif renderer[0] == 'man':
            renderer = ('code', pygments.lexers.get_lexer_by_name('groff'), None, True)
        elif renderer[0] == 'code':
            renderer = list(renderer[:2]) + [None, True]
    return renderer[0], renderers[renderer[0]](repo, ref, path, entry, *renderer[1:])

def detect_renderer(repo, entry):
    name = entry.name.lower()
    ext = name[name.rfind('.'):]
    # First: filename to detect images
    if ext in image_exts:
        return 'image',
    # Known formatters
    if ext in ('.rst', '.rest'):
        return 'rest',
    if ext == '.md':
        return 'markdown',
    if re.match('^\.[1-8](?:fun|p|posix|ssl|perl|pm|gcc|snmp)?$', ext):
        return 'man',
    # Try pygments
    try:
        lexer = pygments.lexers.get_lexer_for_filename(name)
        return 'code', lexer
    except pygments.util.ClassNotFound:
        pass

    obj = repo[entry.oid]
    if obj.size > 1024*1024*5:
        return 'binary',
    data = obj.data

    if data.startswith('#!'):
        shbang = data[:data.find('\n')]
#       Needs to match:
#       #!python
#       #!/path/to/python
#       #!/path/to/my-python
#       #!/path/to/python2.7
#       And any permutation of those features
#                             path     prefix   interp    version
        shbang = re.match(r'#!(?:\S*/)?(?:\S*-)?([^0-9 ]*)(?:\d.*)?', shbang).group(1)
        # Fixers
        shbang = {
            'sh':   'bash',
            'ksh':  'bash',
            'zsh':  'bash',
            'node': 'javascript',
        }.get(shbang, shbang)
        lex = pygments.lexers.find_lexer_class(shbang.title())
        if lex:
            return 'code', lex()

    if '\0' in data:
        return 'binary',

    return 'code', pygments.lexers.TextLexer(), data

def renderer(func):
    renderers[func.__name__] = func
    return func

@renderer
def image(repo, ref, path, entry):
    return Markup("<img src=\"%s\" />") % url_for('raw', repo=repo.name, path="/".join([ref, path]))

@renderer
def plain(repo, ref, path, entry):
    data = escape(decode(repo[entry.oid].data))
    data = re.sub(r'(https?://(?:[-a-zA-Z0-9\._~:/?#\[\]@!\'()*+,;=]+|&amp;)+)', Markup(r'<a href="\1">\1</a>'), data)
    return Markup(u"<pre>%s</pre>" % data)

@renderer
def code(repo, ref, path, entry, lexer, data=None, blame=False):
    from goblet.views import blob_link
    try:
        data = decode(data or repo[entry.oid].data)
    except:
        data = '(Binary data)'
    formatter = pygments.formatters.html.HtmlFormatter(linenos='inline', linenospecial=10, encoding='utf-8', anchorlinenos=True, lineanchors='l')
    html = Markup(pygments.highlight(data, lexer, formatter).decode('utf-8'))
    if blame:
        blame = repo.blame(ref, path)
        if not blame:
            return
        blame.append(None)
        def replace(match):
            line = int(match.group(2)) - 1
            _, orig_line, _, commit = blame[line]
            link = blob_link(repo, commit['hex'], path)
            if blame[-1] == commit['hex']:
                return Markup('        %s<a href="%s#l-%s">%s</a>' % (match.group(1), link, orig_line, match.group(2)))
            link2 = url_for('commit', repo=repo.name, ref=commit['hex'])
            blame[-1] = commit['hex']
            return Markup('<a href="%s" title="%s (%s)">%s</a> %s<a href="%s#l-%s">%s</a>' % (link2, commit['summary'],
                time.strftime('%Y-%m-%d', time.gmtime(int(commit['committer-time']))),
                commit['hex'][:7], match.group(1), link, orig_line, match.group(2)))
        html = re.sub(r'(<a name="l-(\d+)"></a><span class="[^"]+">\s*)(\d+)', replace, html)
    return html

add_plain_link = Markup('''<script type="text/javascript">add_plain_link()</script>''')
@renderer
def markdown(repo, ref, path, entry):
    data = decode(repo[entry.oid].data)
    return Markup(markdown_.Markdown(safe_mode="escape").convert(data)) + add_plain_link

@renderer
def rest(repo, ref, path, entry):
    data = decode(repo[entry.oid].data)
    settings = {
        'file_insertion_enabled': False,
        'raw_enabled': False,
        'output_encoding': 'utf-8',
        'report_level': 5,
    }
    data = docutils.core.publish_parts(data,settings_overrides=settings,writer_name='html')
    return Markup(data['body']) + add_plain_link

@renderer
def man(repo, ref, path, entry):
    res = shell.groff('-Thtml', '-P', '-l', '-mandoc', input=repo[entry.oid].data)
    if res.returncode != 0:
        raise RuntimeError(res.stderr)
    data = decode(res.stdout)
    return Markup(data[data.find('<body>')+6:data.find('</body>')]) + add_plain_link

@renderer
def binary(repo, ref, path, entry):
    return 'Binary file, %d bytes' % repo[entry.oid].size
