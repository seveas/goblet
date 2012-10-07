#!/usr/bin/python

from flask import Flask
import os, sys
import goblet.monkey
import goblet.filters
import goblet.views as v
import goblet.render

root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, root)

REPO_ROOT = os.path.dirname(root)
DEBUG = 1

app = Flask(__name__)
app.config.from_object(__name__)
goblet.filters.register_filters(app)

# URL structure
app.add_url_rule('/', view_func=v.IndexView.as_view('index'))
app.add_url_rule('/<repo>/', view_func=v.RepoView.as_view('repo'))
app.add_url_rule('/<repo>/tree/<path:path>/', view_func=v.TreeView.as_view('tree'))
app.add_url_rule('/j/<repo>/treechanged/<path:path>/', view_func=j.TreeChangedView.as_view('treechanged'))
app.add_url_rule('/<repo>/blob/<path:path>', view_func=v.BlobView.as_view('blob'))
app.add_url_rule('/<repo>/raw/<path:path>', view_func=v.RawView.as_view('raw'))
app.add_url_rule('/<repo>/commit/<path:ref>/', view_func=v.CommitView.as_view('commit'))
app.add_url_rule('/<repo>/commits/', view_func=v.LogView.as_view('log'))
app.add_url_rule('/<repo>/commits/<path:ref>/', view_func=v.LogView.as_view('log'))

@app.context_processor
def inject_functions():
    return {
        'tree_link': v.tree_link,
        'file_icon': v.file_icon,
        'render':    goblet.render.render,
    }

if __name__ == '__main__':
    app.run()
