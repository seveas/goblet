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
import goblet.render
from goblet.encoding import decode

class Defaults:
    REPO_ROOT      = git_checkout and os.path.dirname(git_checkout) or '/srv/git'
    CACHE_ROOT     = '/tmp/goblet_snapshot'
    USE_X_SENDFILE = False
    USE_X_ACCEL_REDIRECT = False
    ADMINS         = []
    SENDER         = 'webmaster@localhost'
    CLONE_URLS_BASE = {}
    DEBUG          = os.environ.get('GOBLET_DEBUG', 'False').lower() == 'true'

class Goblet(Flask):
    def __call__(self, environ, start_response):
        def x_accel_start_response(status, headers, exc_info=None):
            if self.config['USE_X_ACCEL_REDIRECT']:
                for num, (header, value) in enumerate(headers):
                    if header == 'X-Sendfile':
                        headers[num] = ('X-Accel-Redirect', '/snapshots/' + value[value.rfind('/')+1:])
                        break
            return start_response(status, headers, exc_info)
        return super(Goblet, self).__call__(environ, x_accel_start_response)

app = Goblet(__name__)
app.config.from_object(Defaults)
if 'GOBLET_SETTINGS' in os.environ:
    app.config.from_envvar("GOBLET_SETTINGS")

# Configure parts of flask/jinja
goblet.filters.register_filters(app)
@app.context_processor
def inject_functions():
    return {
        'tree_link':  v.tree_link,
        'raw_link':   v.raw_link,
        'blame_link': v.blame_link,
        'blob_link': v.blob_link,
        'file_icon':  v.file_icon,
        'render':     goblet.render.render,
        'decode':     decode,
    }

# URL structure
app.add_url_rule('/', view_func=v.IndexView.as_view('index'))
app.add_url_rule('/<repo>/', view_func=v.RepoView.as_view('repo'))
app.add_url_rule('/<repo>/tree/<path:path>/', view_func=v.TreeView.as_view('tree'))
app.add_url_rule('/j/<repo>/treechanged/<path:path>/', view_func=j.TreeChangedView.as_view('treechanged'))
app.add_url_rule('/<repo>/blame/<path:path>', view_func=v.BlobView.as_view('blame'))
app.add_url_rule('/<repo>/blob/<path:path>', view_func=v.BlobView.as_view('blob'))
app.add_url_rule('/<repo>/raw/<path:path>', view_func=v.RawView.as_view('raw'))
app.add_url_rule('/<repo>/patch/<path:ref>/', view_func=v.PatchView.as_view('patch'))
app.add_url_rule('/<repo>/commit/<path:ref>/', view_func=v.CommitView.as_view('commit'))
app.add_url_rule('/<repo>/commits/', view_func=v.LogView.as_view('commits'))
app.add_url_rule('/<repo>/commits/<path:ref>/', view_func=v.LogView.as_view('commits'))
app.add_url_rule('/<repo>/tags/', view_func=v.TagsView.as_view('tags'))
app.add_url_rule('/<repo>/snapshot/<path:ref>/<format>/', view_func=v.SnapshotView.as_view('snapshot'))

# Logging
if not app.debug and app.config['ADMINS']:
    import logging
    from logging.handlers import SMTPHandler
    mail_handler = SMTPHandler('127.0.0.1', app.config['SENDER'], app.config['ADMINS'], "Goblet error")
    mail_handler.setLevel(logging.ERROR)
    app.logger.addHandler(mail_handler)

if __name__ == '__main__':
    app.run()
