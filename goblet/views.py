# Goblet - Web based git repository browser
# Copyright (C) 2012-2014 Dennis Kaarsemaker
# See the LICENSE file for licensing details

from flask import render_template, current_app, redirect, url_for, request, send_file
from flask.views import View
from goblet.encoding import decode
from goblet.render import render
import os
import glob
import pygit2
import re
import stat
import chardet
import mimetypes
from collections import namedtuple
from whelk import shell

class NotFound(Exception):
    pass

class TemplateView(View):
    def render(self, context):
        return render_template(self.template_name, **context)
    def nocommits(self, context):
        return render_template("nocommits.html", **context)

class IndexView(TemplateView):
    template_name = 'repo_index.html'

    def list_repos(self, root, level):
        for file in os.listdir(root):
            path = os.path.join(root, file)
            if not os.path.isdir(path) or not os.access(path, os.R_OK):
                continue
            if path.endswith('.git'):
                yield path
            elif os.path.exists(os.path.join(path, '.git')):
                yield os.path.join(path, '.git')
            elif level > 0:
                for path in self.list_repos(path, level-1):
                    yield path

    def dispatch_request(self):
        root = current_app.config['REPO_ROOT']
        depth = current_app.config['MAX_SEARCH_DEPTH']
        repos = []
        for repo in sorted(self.list_repos(root, depth),key=lambda x:x.lower()):
            try:
                repos.append(pygit2.Repository(repo))
            except KeyError:
                # Something was unreadable
                pass
        for keyword in request.args.get('q', '').lower().split():
            keyword = keyword.strip()
            if keyword:
                repos = [repo for repo in repos if keyword in repo.name.lower() or keyword in repo.description.lower()]
        return self.render({'repos': repos})

class RepoBaseView(TemplateView):
    template_name = None
    def dispatch_request(self, repo, *args, **kwargs):
        root = current_app.config['REPO_ROOT']
        try:
            repo = pygit2.Repository(os.path.join(root, repo))
        except KeyError:
            return "No such repo", 404
        if not repo.head:
            return self.nocommits({'repo': repo})
        data = {'repo': repo, 'action': request.endpoint}
        try:
            ret = self.handle_request(repo, *args, **kwargs)
        except NotFound, e:
            return str(e), 404
        if hasattr(ret, 'status_code'):
            return ret

        if self.template_name:
            data.update(ret)
            if 'ref' in data:
                data['ref_for_commit'] = repo.ref_for_commit(data['ref'])
            elif 'commit' in data:
                data['ref_for_commit'] = repo.ref_for_commit(data['commit'])
            else:
                data['ref_for_commit'] = repo.ref_for_commit(repo.head.target.hex)
            return self.render(data)
        # For rawview
        return ret

class TagsView(RepoBaseView):
    template_name = 'tags.html'
    tags_per_page = 50

    def handle_request(self, repo):
        tags = [repo.lookup_reference(x) for x in repo.listall_references() if x.startswith('refs/tags')]
        tags = [(tag.name[10:], repo[tag.target.hex]) for tag in tags]
        # Annotated tags vs normal tags
        # Result is list of (name, tag or None, commit)
        tags = [(name, hasattr(tag, 'target') and tag or None, hasattr(tag, 'target') and repo[tag.target] or tag) for name, tag in tags]
        # Filter out non-commits
        tags = [x for x in tags if x[2].type == pygit2.GIT_OBJ_COMMIT]
        # Sort by tag-time or commit-time
        tags.sort(reverse=True, key=lambda t: t[1] and t[1].tagger and t[1].tagger.time or t[2].commit_time)
        for keyword in request.args.get('q', '').lower().split():
            keyword = keyword.strip()
            if keyword:
                tags = [tag for tag in tags if keyword in tag[0] or
                        (tag[1] and keyword in tag[1].message) or
                        ((tag[1] and tag[1].tagger) and (keyword in tag[1].tagger.name or keyword in tag[1].tagger.email))]

        page = 1
        try:
            page = int(request.args['page'])
        except (KeyError, ValueError):
            pass
        page = max(1,page)
        next_page = prev_page = None
        total = len(tags)
        if page > 1:
            prev_page = page - 1
        if total > self.tags_per_page * page:
            next_page = page + 1

        start = (page-1) * self.tags_per_page
        end = min(start + 50, total)
        return {'tags': tags[start:end], 'start': start+1, 'end': end, 'total': total, 'prev_page': prev_page, 'next_page': next_page}

# Repo, path and blob

class PathView(RepoBaseView):
    def split_ref(self, repo, path, expects_file=False):
        file = None
        # First extract branch, which can contain slashes
        for ref in sorted(repo.branches(), key = lambda x: -len(x)):
            if path.startswith(ref):
                path = path.replace(ref, '')[1:]
                tree = repo[repo.lookup_reference('refs/heads/%s' % ref).target.hex].tree
                break
        else:
            # OK, maybe a tag?
            for ref in sorted(repo.tags(), key = lambda x: -len(x)):
                if path.startswith(ref):
                    path = path.replace(ref, '')[1:]
                    ref = repo.lookup_reference('refs/tags/%s' % ref).target.hex
                    if repo[ref].type == pygit2.GIT_OBJ_TAG:
                        ref = repo[repo[ref].target].hex
                    tree = repo[ref].tree
                    break
            else:
                # Or a commit
                if '/' in path:
                    ref, path = path.split('/', 1)
                else:
                    ref, path = path, ''
                try:
                    tree = repo[ref].tree
                except (KeyError, ValueError):
                    raise NotFound("No such commit/ref")

        # Remainder is path
        path_ = path.split('/')
        while path and path_:
            if path_[0] not in tree:
                raise NotFound("No such file")
            entry = tree[path_.pop(0)]

            if expects_file and not path_:
                if not stat.S_ISREG(entry.filemode):
                    raise NotFound("Not a file")
                file = entry
            elif not stat.S_ISDIR(entry.filemode):
                raise NotFound("Not a folder")
            else:
                tree = repo[entry.oid]
        if expects_file and not file:
            raise NotFound("No such file")

        return ref, path, tree, file

class TreeView(PathView):
    template_name = 'tree.html'
    results_per_page = 50

    def handle_request(self, repo, path):
        ref, path, tree, _ = self.split_ref(repo, path)
        if 'q' in request.args:
            return self.git_grep(repo, ref, path)
        return {'tree': tree, 'ref': ref, 'path': path}

    def git_grep(self, repo, ref, path):
        self.template_name = 'search.html'
        results = list(repo.grep(ref, path, request.args['q']))

        page = 1
        try:
            page = int(request.args['page'])
        except (KeyError, ValueError):
            pass
        page = max(1,page)
        next_page = prev_page = None
        total = len(results)
        if page > 1:
            prev_page = page - 1
        if total > self.results_per_page * page:
            next_page = page + 1

        start = (page-1) * self.results_per_page
        end = min(start + 50, total)

        return {'results': results[start:end], 'start': start+1, 'end': end, 'total': total,
                'ref': ref, 'path': path, 'next_page': next_page, 'prev_page': prev_page}

class RepoView(TreeView):
    def handle_request(self, repo):
        tree = repo[repo.head.target].tree
        if 'q' in request.args:
            ref = repo.ref_for_commit(repo.head.target.hex)
            return redirect(url_for('tree', repo=repo.name, path=ref) + '?q=' + request.args['q'])
        readme = renderer = rendered_file = None
        for file in tree:
            if re.match(r'^readme(?:.(?:txt|rst|md))?$', file.name, flags=re.I):
                readme = file
                renderer, rendered_file = render(repo, repo.head, '', readme)
        return {'readme': readme, 'tree': tree, 'ref': repo.ref_for_commit(repo.head.target.hex),
                'path': '', 'show_clone_urls': True, 'renderer': renderer, 'rendered_file': rendered_file}

class BlobView(PathView):
    template_name = 'blob.html'

    def handle_request(self, repo, path):
        ref, path, tree, file = self.split_ref(repo, path, expects_file=True)
        folder = '/' in path and path[:path.rfind('/')] or None
        renderer, rendered_file  = render(repo, ref, path, file, blame=request.endpoint == 'blame', plain=request.args.get('plain') == '1')
        # For empty blames, a redirect to the history is better
        if rendered_file is None:
            return redirect(url_for('history', repo=repo.name, path='%s/%s' % (ref, path)))
        return {'tree': tree, 'ref': ref, 'path': path, 'file': file, 'folder': folder, 'rendered_file': rendered_file, 'renderer': renderer}

class RawView(PathView):
    template = None
    def handle_request(self, repo, path):
        ref, path, tree, file = self.split_ref(repo, path, expects_file=True)
        if not ref:
            raise NotFound("No such file")

        # Try to detect the mimetype
        mimetype, encoding = mimetypes.guess_type(file.name)
        data = repo[file.hex].data
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

# Log, snapshot, commit and diff

class RefView(RepoBaseView):
    def lookup_ref(self, repo, ref):
        if not ref:
            return repo.head.target
        try:
            ref = repo.lookup_reference('refs/heads/' + ref).target.hex
        except (KeyError, ValueError):
            pass
        try:
            ref = repo.lookup_reference('refs/tags/' + ref).target.hex
        except (KeyError, ValueError):
            pass
        try:
            obj = repo[ref]
            if obj.type == pygit2.GIT_OBJ_TAG:
                obj = repo[obj.target]
            if obj.type != pygit2.GIT_OBJ_COMMIT:
                raise NotFound("No such commit/ref")
            return obj
        except (KeyError, ValueError):
            raise NotFound("No such commit/ref")

class LogView(RefView):
    template_name = 'log.html'
    commits_per_page = 50

    def handle_request(self, repo, ref=None):
        ref = self.lookup_ref(repo, ref)
        page = 1
        try:
            page = int(request.args['page'])
        except (KeyError, ValueError):
            pass
        page = max(1,page)
        next_page = prev_page = None
        if page > 1:
            prev_page = page - 1

        log = list(repo.get_commits(ref, skip=self.commits_per_page * (page-1), count=self.commits_per_page, search=request.args.get('q', '')))
        if log and log[-1].parents:
            next_page = page + 1
        shas = [x.hex for x in log]
        return {'ref': repo.ref_for_commit(ref), 'log': log, 'shas': shas, 'refs': repo.reverse_refs, 'next_page': next_page, 'prev_page': prev_page}

class HistoryView(PathView,RefView):
    template_name = 'log.html'
    commits_per_page = 50

    def handle_request(self, repo, path):
        ref, path, tree, file = self.split_ref(repo, path, expects_file=True)
        ref = self.lookup_ref(repo, ref)
        page = 1
        try:
            page = int(request.args['page'])
        except (KeyError, ValueError):
            pass
        page = max(1,page)
        next_page = prev_page = None
        if page > 1:
            prev_page = page - 1

        log = list(repo.get_commits(ref, skip=self.commits_per_page * (page-1), count=self.commits_per_page, file=path))
        if log and log[-1].parents and len(log) == self.commits_per_page:
            next_page = page + 1
        shas = [x.hex for x in log]
        return {'ref': repo.ref_for_commit(ref), 'log': log, 'shas': shas, 'refs': repo.reverse_refs, 'next_page': next_page, 'prev_page': prev_page}


snapshot_formats = {
    'zip': ('zip', None,            'zip'    ),
    'xz':  ('tar', ['xz'],          'tar.xz' ),
    'gz':  ('tar', ['gzip',  '-9'], 'tar.gz' ),
    'bz2': ('tar', ['bzip2', '-9'], 'tar.bz2'),
}
class SnapshotView(RefView):
    def handle_request(self, repo, ref, format):
        ref = self.lookup_ref(repo, ref)
        format, compressor, ext = snapshot_formats.get(format, (None, None))
        if not format:
            raise NotFound("No such snapshot format")
        cache_dir = current_app.config['CACHE_ROOT']
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir)

        desc = repo.describe(ref.hex).replace('/', '-')
        filename_compressed = os.path.join(cache_dir, '%s-%s.%s' % (repo.name, desc, ext))
        filename_uncompressed = os.path.join(cache_dir, '%s-%s.%s' % (repo.name, desc, format))
        if not os.path.exists(filename_compressed):
            ret = repo.git('archive', '--format', format, '--prefix', '%s-%s/' % (repo.name, desc), '--output', filename_uncompressed, ref.hex)
            if ret.returncode != 0:
                raise RuntimeError(ret.stderr)
            if compressor:
                compressor = compressor[:]
                compressor.append(filename_uncompressed)
                ret = getattr(shell, compressor[0])(*compressor[1:])
                if ret.returncode != 0:
                    raise RuntimeError(ret.stderr)
        return send_file(filename_compressed, attachment_filename=os.path.basename(filename_compressed), as_attachment=True, cache_timeout=86400)

class CommitView(RefView):
    template_name = 'commit.html'

    def handle_request(self, repo, ref=None):
        ref = self.lookup_ref(repo, ref)
        stat = {}
        if not ref.parents:
            diff = ref.tree.diff_to_tree(swap=True)
        else:
            diff = ref.parents[0].tree.diff_to_tree(ref.tree)
        for file in diff:
            s = stat[file.new_file_path] = {'-': 0, '+': 0}
            for hunk in file.hunks:
                hs = [x[0] for x in hunk.lines]
                s['-'] += hs.count('-')
                s['+'] += hs.count('+')
                s['%'] = int(100.0 * s['+'] / (s['-']+s['+']))
        stat[None] = {'-': sum([x['-'] for x in stat.values()]), '+': sum([x['+'] for x in stat.values()])}
        return {'commit': ref, 'diff': diff, 'stat': stat}

class PatchView(RefView):
    def handle_request(self, repo, ref=None):
        ref = self.lookup_ref(repo, ref)
        # XXX port to pygit2
        data = repo.git('format-patch', '--stdout', '%s^..%s' % (ref.hex, ref.hex)).stdout
        return (data, 200, [{'Content-Type': 'text/plain', 'Content-Encoding': 'utf-8'}])

Fakefile = namedtuple('Fakefile', ('name', 'filemode'))
def tree_link(repo, ref, path, file):
    if isinstance(file, str):
        file = Fakefile(name=file, filemode=stat.S_IFREG)
    if path:
        tree_path = '/'.join([ref, path, decode(file.name)])
    else:
        tree_path = '/'.join([ref, decode(file.name)])
    if stat.S_ISDIR(file.filemode):
        return url_for('tree', repo=repo.name, path=tree_path)
    if stat.S_ISREG(file.filemode):
        return url_for('blob', repo=repo.name, path=tree_path)

def blob_link(repo, ref, path, file=None):
    parts = [x for x in (ref, path, file) if x]
    return url_for('blob', repo=repo.name, path='/'.join(parts))

def raw_link(repo, ref, path, file=None):
    parts = [x for x in (ref, path, file) if x]
    return url_for('raw', repo=repo.name, path='/'.join(parts))

def blame_link(repo, ref, path, file=None):
    parts = [x for x in (ref, path, file) if x]
    return url_for('blame', repo=repo.name, path='/'.join(parts))

def history_link(repo, ref, path, file=None):
    parts = [x for x in (ref, path, file) if x]
    return url_for('history', repo=repo.name, path='/'.join(parts))

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
