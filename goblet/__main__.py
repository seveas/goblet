# Goblet - Web based git repository browser
# Copyright (C) 2012-2014 Dennis Kaarsemaker
# See the LICENSE file for licensing details

# If we're running from a git checkout, make sure we use the checkout
import os, sys
git_checkout = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
git_checkout = os.path.exists(os.path.join(git_checkout, '.git')) and git_checkout or None
if git_checkout:
    sys.path.insert(0, git_checkout)

from flask import Flask
import goblet.monkey
import goblet.filters
import goblet.views as v
import goblet.json_views as j
from goblet.encoding import decode
import stat

class Defaults:
    REPO_ROOT      = git_checkout and os.path.dirname(git_checkout) or os.getcwd()
    MAX_SEARCH_DEPTH = 2
    CACHE_ROOT     = '/tmp/goblet-snapshots'
    USE_X_SENDFILE = False
    USE_X_ACCEL_REDIRECT = False
    ADMINS         = []
    SENDER         = 'webmaster@localhost'
    CLONE_URLS_BASE = {}
    DEBUG          = os.environ.get('GOBLET_DEBUG', 'False').lower() == 'true'
    THEME          = 'default'
    ABOUT = """<h2>About git &amp; goblet</h2>
<p>
<a href="http://git-scm.com">Git</a> is a free and open source distributed
version control system designed to handle everything from small to very large
projects with speed and efficiency. 
</p>
<p>
Goblet is a fast web-based git repository browser using libgit2.
</p>
"""

class Goblet(Flask):
    def __call__(self, environ, start_response):
        def x_accel_start_response(status, headers, exc_info=None):
            if self.config['USE_X_ACCEL_REDIRECT']:
                for num, (header, value) in enumerate(headers):
                    if header == 'X-Sendfile':
                        fn = value[value.rfind('/')+1:]
                        if os.path.exists(os.path.join(self.config['CACHE_ROOT'], fn)):
                            headers[num] = ('X-Accel-Redirect', '/snapshots/' + fn)
                        break
            return start_response(status, headers, exc_info)
        return super(Goblet, self).__call__(environ, x_accel_start_response)

app = Goblet(__name__)
app.config.from_object(Defaults)
if 'GOBLET_SETTINGS' in os.environ:
    app.config.from_envvar("GOBLET_SETTINGS")

app.template_folder = os.path.join('themes', app.config['THEME'], 'templates')
app.static_folder = os.path.join('themes', app.config['THEME'], 'static')

# Configure parts of flask/jinja
goblet.filters.register_filters(app)
@app.context_processor
def inject_functions():
    return {
        'tree_link':    v.tree_link,
        'raw_link':     v.raw_link,
        'blame_link':   v.blame_link,
        'blob_link':    v.blob_link,
        'history_link': v.history_link,
        'file_icon':    v.file_icon,
        'decode':       decode,
        'S_ISGITLNK':   stat.S_ISGITLNK,
    }

# URL structure
app.add_url_rule('/', view_func=v.IndexView.as_view('index'))
app.add_url_rule('/<path:repo>/', view_func=v.RepoView.as_view('repo'))
app.add_url_rule('/<repo>/tree/<path:path>/', view_func=v.TreeView.as_view('tree'))
app.add_url_rule('/j/<path:repo>/treechanged/<path:path>/', view_func=j.TreeChangedView.as_view('treechanged'))
app.add_url_rule('/<path:repo>/history/<path:path>', view_func=v.HistoryView.as_view('history'))
app.add_url_rule('/<path:repo>/blame/<path:path>', view_func=v.BlobView.as_view('blame'))
app.add_url_rule('/<path:repo>/blob/<path:path>', view_func=v.BlobView.as_view('blob'))
app.add_url_rule('/<path:repo>/raw/<path:path>', view_func=v.RawView.as_view('raw'))
app.add_url_rule('/<path:repo>/patch/<path:ref>/', view_func=v.PatchView.as_view('patch'))
app.add_url_rule('/<path:repo>/commit/<path:ref>/', view_func=v.CommitView.as_view('commit'))
app.add_url_rule('/<path:repo>/commits/', view_func=v.LogView.as_view('commits'))
app.add_url_rule('/<path:repo>/commits/<path:ref>/', view_func=v.LogView.as_view('ref_commits'))
app.add_url_rule('/<path:repo>/tags/', view_func=v.TagsView.as_view('tags'))
app.add_url_rule('/<path:repo>/snapshot/<path:ref>/<format>/', view_func=v.SnapshotView.as_view('snapshot'))

# Logging
if not app.debug and app.config['ADMINS']:
    import logging, logging.handlers
    class SMTPHandler(logging.handlers.SMTPHandler):
        def format(self, msg):
            from flask import request
            msg = super(SMTPHandler, self).format(msg)
            get = '\n'.join(['%s=%s' % (x, request.args[x]) for x in request.args])
            post = '\n'.join(['%s=%s' % (x, str(request.form[x])[:1000]) for x in request.form])
            cookies = '\n'.join(['%s=%s' % (x, request.cookies[x]) for x in request.cookies])
            env = '\n'.join(['%s=%s' % (x, request.environ[x]) for x in request.environ])
            hdr = '\n'.join([': '.join(x) for x in request.headers])
            return ("%s\n\nGET variables:\n%s\n\nPOST variables:\n%s\n\nCookies:\n%s\n\n" +
                    "HTTP Headers:\n%s\n\nEnvironment:\n%s") % (msg, get, post, cookies, hdr, env)

    mail_handler = SMTPHandler('127.0.0.1', app.config['SENDER'], app.config['ADMINS'], "Goblet error")
    mail_handler.setLevel(logging.ERROR)
    app.logger.addHandler(mail_handler)

if __name__ == '__main__':
    os.chdir('/')
    app.run()
