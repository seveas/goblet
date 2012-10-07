from goblet.views import TreeView
import json

class TreeChangedView(repo, path):
    def dispatch_request(self, repo, path):
        root = current_app.config['REPO_ROOT']
        repo = pygit2.Repository(os.path.join(root, repo))
        if not repo.head:
            return self.nocommits(repo=repo)

        ref, path, tree, _ = self.split_ref(repo, path)
        if not ref:
            return path, 404

        lastchanged = repo.tree_lastchanged(ref, path.split('/'))
        return
