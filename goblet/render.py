from flask import url_for
from jinja2 import Markup, escape
import pygments
import pygments.formatters
import pygments.lexers
from goblet.encoding import decode

import re
import markdown as markdown_
import docutils.core

renderers = {}
image_exts = ('.gif', '.png', '.bmp', '.tif', '.tiff', '.jpg', '.jpeg', 'ppm',
    'pnm', 'pbm', 'pgm', 'webp')

def render(repo, ref, path, entry, no_highlight=False):
    renderer = detect_renderer(entry)
    if renderer[0] == 'code' and no_highlight:
        renderer = ('plain',)
    return renderers[renderer[0]](repo, ref, path, entry, *renderer[1:])

def detect_renderer(entry):
    name = entry.name.lower()
    # First: filename to detect images
    if name.endswith(image_exts):
        return 'image',
    # Known formatters
    if name.endswith(('.rst', '.rest')):
        return 'rest',
    if name.endswith('.md'):
        return 'markdown',
    # Try pygments
    try:
        lexer = pygments.lexers.get_lexer_for_filename(name)
        return 'code', lexer
    except pygments.util.ClassNotFound:
        pass

    obj = entry.to_object()
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
    data = escape(decode(entry.to_object().data))
    data = re.sub(r'(https?://(?:[-a-zA-Z0-9\._~:/?#\[\]@!\'()*+,;=]+|&amp;)+)', Markup(r'<a href="\1">\1</a>'), data)
    return Markup(u"<pre>%s</pre>" % data)

@renderer
def code(repo, ref, path, entry, lexer, data=None):
    data = decode(data or entry.to_object().data)
    formatter = pygments.formatters.html.HtmlFormatter(linenos='inline', linenospecial=10, encoding='utf-8')
    return Markup(pygments.highlight(data, lexer, formatter).decode('utf-8'))

@renderer
def markdown(repo, ref, path, entry):
    data = decode(entry.to_object().data)
    return Markup(markdown_.Markdown(safe_mode="escape").convert(data))

@renderer
def rest(repo, ref, path, entry):
    data = decode(entry.to_object().data)
    settings = {
        'file_insertion_enabled': False,
        'raw_enabled': False,
        'output_encoding': 'utf-8',
        'report_level': 5,
    }
    data = docutils.core.publish_parts(data,settings_overrides=settings,writer_name='html')
    return Markup(data['body'])

@renderer
def binary(repo, ref, path, entry):
    return 'Binary file, %d bytes' % entry.to_object().size
