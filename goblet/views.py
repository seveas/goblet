from flask import render_template, current_app, redirect, url_for, request
from flask.views import View
import os
import glob
import pygit2
import re
import stat
import chardet
import mimetypes
from collections import namedtuple

class TemplateView(View):
    def render(self, **context):
        return render_template(self.template_name, **context)
    def nocommits(self, **context):
        return render_template("nocommits.html", **context)

class IndexView(TemplateView):
    template_name = 'repo_index.html'

    def dispatch_request(self):
        root = current_app.config['REPO_ROOT']
        repos = glob.glob(os.path.join(root, '*.git')) + glob.glob(os.path.join(root, '*', '.git'))
        repos = [pygit2.Repository(x) for x in sorted(repos, key=lambda x:x.lower())]
        repos[0].name
        return self.render(repos=repos)

class RefView(TemplateView):
    def lookup_ref(self, repo, ref):
        if not ref:
            return repo.head
        try:
            ref = repo.lookup_reference('refs/heads/' + ref).hex
        except KeyError:
            pass
        try:
            return repo[ref]
        except (KeyError, ValueError):
            return None

class CommitView(RefView):
    template_name = 'commit.html'
    def dispatch_request(self, repo, ref=None):
        root = current_app.config['REPO_ROOT']
        repo = pygit2.Repository(os.path.join(root, repo))
        if not repo.head:
            return self.nocommits(repo=repo)
        ref = self.lookup_ref(repo, ref)
        if not ref:
            return "No such commit", 404

        if not ref.parents:
            diff = {'changes': {'files': [(None, x.name) for x in ref.tree]}}
            diff_, stat = fakediff(ref.tree)
        else:
            diff = ref.parents[0].tree.diff(ref.tree)
            diff_, stat = realdiff(diff)
        return self.render(repo=repo, commit=ref, diff=diff, formatdiff=diff_, stat=stat)

def fakediff(tree):
    files = {}
    stat = {}
    for file in tree:
        lines = file.to_object().data.split('\n')
        stat[file.name] = {'+': len(lines), '-': 0}
        files[file.name] = [{
            'header': '@@ -0,0 +1,%d' % len(lines),
            'data': [(x, pygit2.GIT_DIFF_LINE_ADDITION) for x in lines],
            'new_start': 0,
            'old_start': 0,
        }]
    stat[None] = {'-': sum([x['-'] for x in stat.values()]), '+': sum([x['+'] for x in stat.values()])}
    return files, stat

def realdiff(diff):
    files = {}
    stat = {}
    # Can happen with subproject-only commits
    if not diff.changes:
        return {}, {None: {'+': 0, '-': 0}}
    for file in diff.changes['files']:
        files[file[1]] = []
        stat[file[1]] = {'-': 0, '+': 0}
    for hunk in diff.changes['hunks']:
        files[hunk.new_file].append(hunk)
        stat[hunk.new_file]['-'] += len([x for x in hunk.data if x[1] == pygit2.GIT_DIFF_LINE_DELETION])
        stat[hunk.new_file]['+'] += len([x for x in hunk.data if x[1] == pygit2.GIT_DIFF_LINE_ADDITION])
    stat[None] = {'-': sum([x['-'] for x in stat.values()]), '+': sum([x['+'] for x in stat.values()])}
    return files, stat

class LogView(RefView):
    template_name = 'log.html'
    commits_per_page = 50

    def dispatch_request(self, repo, ref=None):
        root = current_app.config['REPO_ROOT']
        repo = pygit2.Repository(os.path.join(root, repo))
        if not repo.head:
            return self.nocommits(repo=repo)
        ref = self.lookup_ref(repo, ref)
        if not ref:
            return "No such commit", 404

        page = 1
        try:
            page = int(request.args['page'])
        except (KeyError, ValueError):
            pass
        page = max(1,page)
        next_page = prev_page = None
        if page > 1:
            prev_page = page - 1

        log = list(repo.get_commits(ref, skip=self.commits_per_page * (page-1), count=self.commits_per_page))
        if log[-1].parents:
            next_page = page + 1
        shas = [x.hex for x in log]
        return self.render(repo=repo, ref=repo.symref(ref), log=list(log), shas=shas, next_page=next_page, prev_page=prev_page)

class PathView(TemplateView):
    def split_ref(self, repo, path, expects_file=False):
        file = None
        # First extract branch, which can contain slashes
        for ref in sorted(repo.branches(), key = lambda x: -len(x)):
            if path.startswith(ref):
                path = path.replace(ref, '')[1:]
                tree = repo[repo.lookup_reference('refs/heads/%s' % ref).hex].tree
                break
        else:
            # OK, maybe a tag? XXX
            # Or a commit
            if '/' in path:
                ref, path = path.split('/', 1)
            else:
                ref, path = path, ''
            if ref in repo:
                tree = repo[ref].tree
            else:
                return None, 'No such ref', None, None

        # Remainder is path
        path_ = path.split('/')
        while path and path_:
            if path_[0] not in tree:
                return None, 'No such path', None, None
            entry = tree[path_.pop(0)]

            if expects_file and not path_:
                if not stat.S_ISREG(entry.filemode):
                    return None, 'Not a file', None, None 
                file = entry
            elif not stat.S_ISDIR(entry.filemode):
                return None, 'Not a path %s %s %s' % (entry.name, str(path_), str(expects_file)), None, None 
            else:
                tree = entry.to_object()

        return ref, path, tree, file

class TreeView(PathView):
    template_name = 'tree.html'

    def dispatch_request(self, repo, path):
        root = current_app.config['REPO_ROOT']
        repo = pygit2.Repository(os.path.join(root, repo))
        if not repo.head:
            return self.nocommits(repo=repo)

        ref, path, tree, _ = self.split_ref(repo, path)
        if not ref:
            return path, 404
        return self.render(repo=repo, tree=tree, ref=ref, path=path)

class BlobView(PathView):
    template_name = 'blob.html'

    def dispatch_request(self, repo, path):
        root = current_app.config['REPO_ROOT']
        repo = pygit2.Repository(os.path.join(root, repo))
        if not repo.head:
            return self.nocommits(repo=repo)

        ref, path, tree, file = self.split_ref(repo, path, expects_file=True)
        if not ref:
            return path, 404
        return self.render(repo=repo, tree=tree, ref=ref, path=path, file=file)

class RawView(PathView):
    def dispatch_request(self, repo, path):
        root = current_app.config['REPO_ROOT']
        repo = pygit2.Repository(os.path.join(root, repo))
        if not repo.head:
            return self.nocommits(repo=repo)

        ref, path, tree, file = self.split_ref(repo, path, expects_file=True)
        if not ref:
            return path, 404

        # Try to detect the mimetype
        mimetype, encoding = mimetypes.guess_type(file.name)
        data = file.to_object().data
        # shbang'ed: text/plain will do
        if not mimetype and data[:2] == '#!':
            mimetype = 'text/plain'
        # For text mimetypes, guess an encoding
        if not mimetype:
            if '\0' in data:
                mimetype = 'application/octet-stream'
            else:
                mimetype = 'text/plain'
        if mimetype.startswith('text/') and not encoding:
            encoding = chardet.detect(data)['encoding']
        headers = {'Content-Type': mimetype}
        if encoding:
            headers['Content-Encoding'] = encoding
        return (data, 200, headers)

class RepoView(TreeView):
    def dispatch_request(self, repo):
        root = current_app.config['REPO_ROOT']
        repo = pygit2.Repository(os.path.join(root, repo))
        if not repo.head:
            return self.nocommits(repo=repo)
        tree = repo.head.tree
        readme = readme_name = renderer = None
        for file in tree:
            if re.match(r'^readme(?:.(?:txt|rst|md))?$', file.name, flags=re.I):
                readme = file
        return self.render(repo=repo, readme=readme, tree=tree, ref=repo.symref(repo.head), path='')

Fakefile = namedtuple('Fakefile', ('name', 'filemode'))
def tree_link(repo, ref, path, file):
    if isinstance(file, str):
        file = Fakefile(name=file, filemode=stat.S_IFREG)
    if path:
        tree_path = '/'.join([ref, path, file.name])
    else:
        tree_path = '/'.join([ref, file.name])
    if stat.S_ISDIR(file.filemode):
        return url_for('tree', repo=repo.name, path=tree_path)
    if stat.S_ISREG(file.filemode):
        return url_for('blob', repo=repo.name, path=tree_path)

def file_icon(file):
    mode = getattr(file, 'filemode', stat.S_IFREG)
    if stat.S_ISDIR(mode):
        return "/static/folder_icon.png"
    if stat.S_IXUSR & mode:
        return "/static/script_icon.png"
    if stat.S_ISLNK(mode):
        return "/static/link_icon.png"
    if stat.S_ISGITLNK(mode):
        return "/static/repo_icon.png"
    return "/static/file_icon.png"
