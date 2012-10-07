from goblet.views import PathView
from goblet.filters import humantime, shortmsg
from jinja2 import escape
import json

class TreeChangedView(PathView):
    def handle_request(self, repo, path):
        ref, path, tree, _ = self.split_ref(repo, path)
        if ref not in repo:
            ref = repo.lookup_reference('refs/heads/%s' % ref).hex
        lastchanged = repo.tree_lastchanged(repo[ref], path and path.split('/') or [])
        ret = {}
        for file, data in lastchanged.iteritems():
            ret[file] = [data['hex'][:7], humantime(data['commit'].commit_time), data['commit'].hex, escape(shortmsg(data['commit'].message))]
        return json.dumps(ret), 200, {'Content-Type': 'application/json'}
