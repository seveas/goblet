# Goblet - Web based git repository browser
# Copyright (C) 2012-2014 Dennis Kaarsemaker
# See the LICENSE file for licensing details

from goblet.views import PathView
from goblet.filters import shortmsg
from jinja2 import escape
import json
from flask import send_file, request, redirect, config, current_app
import os

class TreeChangedView(PathView):
    def handle_request(self, repo, path):
        ref, path, tree, _ = self.split_ref(repo, path)
        try:
            if ref not in repo:
                ref = repo.lookup_reference('refs/heads/%s' % ref).target.hex
        except ValueError:
            ref = repo.lookup_reference('refs/heads/%s' % ref).target.hex
        if hasattr(repo[ref], 'target'):
            ref = repo[repo[ref].target].hex
        cfile = os.path.join(repo.cpath, 'dirlog_%s_%s.json' % (ref, path.replace('/', '_')))
        if not os.path.exists(cfile):
            tree = repo[ref].tree
            for elt in path.split('/'):
                if elt:
                    tree = repo[tree[elt].hex]
            lastchanged = repo.tree_lastchanged(repo[ref], path)
            commits = {}
            for commit in set(lastchanged.values()):
                commit = repo[commit]
                commits[commit.hex] = [commit.commit_time, escape(shortmsg(commit.message))]
            for file in lastchanged:
                lastchanged[file] = (lastchanged[file], tree[file].hex[:7])
            ret = {'files': lastchanged, 'commits': commits}
            if not current_app.config['TESTING']:
                with open(cfile, 'w') as fd:
                    json.dump(ret, fd)
        if current_app.config['TESTING']:
            # When testing, we're not writing to the file, so we can't send_file or redirect
            return json.dumps(ret)
        elif 'wsgi.version' in request.environ and request.environ['SERVER_PORT'] != '5000':
            # Redirect to the file, let the webserver deal with it
            return redirect(cfile.replace(current_app.config['REPO_ROOT'], ''))
        else:
            return send_file(cfile)
