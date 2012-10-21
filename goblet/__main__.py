#!/usr/bin/python

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

class Defaults:
    REPO_ROOT      = git_checkout and os.path.dirname(git_checkout) or '/srv/git'
    CACHE_ROOT     = '/tmp/goblet_snapshot'
    USE_X_SENDFILE = False
    ADMINS         = []
    SENDER         = 'webmaster@localhost'

app = Flask(__name__)
app.config.from_object(Defaults)
if 'GOBLET_SETTINGS' in os.environ:
    app.config.from_envvar("GOBLET_SETTINGS")

# Configure parts of flask/jinja
goblet.filters.register_filters(app)
@app.context_processor
def inject_functions():
    return {
        'tree_link': v.tree_link,
        'file_icon': v.file_icon,
        'render':    goblet.render.render,
    }

# URL structure
app.add_url_rule('/', view_func=v.IndexView.as_view('index'))
app.add_url_rule('/<repo>/', view_func=v.RepoView.as_view('repo'))
app.add_url_rule('/<repo>/tree/<path:path>/', view_func=v.TreeView.as_view('tree'))
app.add_url_rule('/j/<repo>/treechanged/<path:path>/', view_func=j.TreeChangedView.as_view('treechanged'))
app.add_url_rule('/<repo>/blob/<path:path>', view_func=v.BlobView.as_view('blob'))
app.add_url_rule('/<repo>/raw/<path:path>', view_func=v.RawView.as_view('raw'))
app.add_url_rule('/<repo>/commit/<path:ref>/', view_func=v.CommitView.as_view('commit'))
app.add_url_rule('/<repo>/commits/', view_func=v.LogView.as_view('commits'))
app.add_url_rule('/<repo>/commits/<path:ref>/', view_func=v.LogView.as_view('commits'))
app.add_url_rule('/<repo>/tags/', view_func=v.TagsView.as_view('tags'))
app.add_url_rule('/<repo>/snapshot/<path:ref>/<format>/', view_func=v.SnapshotView.as_view('snapshot'))


if __name__ == '__main__':
    app.run()
