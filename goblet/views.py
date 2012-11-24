from flask import render_template, current_app, redirect, url_for, request, send_file
from flask.views import View
from goblet.encoding import decode
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

    def dispatch_request(self):
        root = current_app.config['REPO_ROOT']
        repos = glob.glob(os.path.join(root, '*.git')) + glob.glob(os.path.join(root, '*', '.git'))
        repos = [pygit2.Repository(x) for x in sorted(repos, key=lambda x:x.lower())]
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

        if self.template_name:
            data.update(ret)
            if 'ref' in data:
                data['symref'] = repo.symref(data['ref'])
            elif 'commit' in data:
                data['symref'] = repo.symref(data['commit'])
            else:
                data['symref'] = repo.symref(repo.head)
            return self.render(data)
        # For rawview
        return ret

class TagsView(RepoBaseView):
    template_name = 'tags.html'
    tags_per_page = 50

    def handle_request(self, repo):
        tags = [repo.lookup_reference(x) for x in repo.listall_references() if x.startswith('refs/tags')]
        tags = [(tag.name[10:], repo[tag.hex]) for tag in tags]
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
                tree = repo[repo.lookup_reference('refs/heads/%s' % ref).hex].tree
                break
        else:
            # OK, maybe a tag?
            for ref in sorted(repo.tags(), key = lambda x: -len(x)):
                if path.startswith(ref):
                    path = path.replace(ref, '')[1:]
                    ref = repo.lookup_reference('refs/tags/%s' % ref).hex
                    if repo[ref].type == pygit2.GIT_OBJ_TAG:
                        tree = repo[repo[ref].target].tree
                    else:
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
                tree = entry.to_object()
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
                'ref': ref.hex, 'path': path, 'next_page': next_page, 'prev_page': prev_page}

class RepoView(TreeView):
    def handle_request(self, repo):
        tree = repo.head.tree
        if 'q' in request.args:
            return self.git_grep(repo, repo.head, '')
        readme = None
        for file in tree:
            if re.match(r'^readme(?:.(?:txt|rst|md))?$', file.name, flags=re.I):
                readme = file
        return {'readme': readme, 'tree': tree, 'ref': repo.symref(repo.head), 'path': '', 'show_clone_urls': True}

class BlobView(PathView):
    template_name = 'blob.html'

    def handle_request(self, repo, path):
        ref, path, tree, file = self.split_ref(repo, path, expects_file=True)
        folder = '/' in path and path[:path.rfind('/')] or None
        return {'tree': tree, 'ref': ref, 'path': path, 'file': file, 'folder': folder}

class RawView(PathView):
    template = None
    def handle_request(self, repo, path):
        ref, path, tree, file = self.split_ref(repo, path, expects_file=True)
        if not ref:
            raise NotFound("No such file")

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

# Log, snapshot, commit and diff

class RefView(RepoBaseView):
    def lookup_ref(self, repo, ref):
        if not ref:
            return repo.head
        try:
            ref = repo.lookup_reference('refs/heads/' + ref).hex
        except KeyError:
            pass
        try:
            ref = repo.lookup_reference('refs/tags/' + ref).hex
        except KeyError:
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
        refs = repo.commit_to_ref_hash()
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
        if log[-1].parents:
            next_page = page + 1
        shas = [x.hex for x in log]
        return {'ref': repo.symref(ref), 'log': log, 'shas': shas, 'refs': refs, 'next_page': next_page, 'prev_page': prev_page}

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
        if not ref.parents:
            diff = {'changes': {'files': [(None, x) for x in repo.ls_tree(ref.tree)]}}
            diff_, stat = fakediff(ref.tree)
        else:
            diff = ref.parents[0].tree.diff(ref.tree)
            diff_, stat = realdiff(diff)
        return {'commit': ref, 'diff': diff, 'formatdiff': diff_, 'stat': stat}

class PatchView(RefView):
    def handle_request(self, repo, ref=None):
        ref = self.lookup_ref(repo, ref)
        # XXX port to pygit2
        data = repo.git('format-patch', '--stdout', '%s^..%s' % (ref.hex, ref.hex)).stdout
        return (data, 200, [{'Content-Type': 'text/plain', 'Content-Encoding': 'utf-8'}])

def fakediff(tree):
    files = {}
    fstat = {}
    for file in tree:
        if stat.S_ISDIR(file.filemode):
            f2, s2 = fakediff(file.to_object())
            for f in f2:
                files[os.path.join(file.name, f)] = f2[f]
                fstat[os.path.join(file.name, f)] = s2[f]
            continue

        data = file.to_object().data
        if '\0' in data:
            # Binary file, ignore
            continue
        data = decode(data)
        lines = data.strip().split('\n')
        fstat[file.name] = {'+': len(lines), '-': 0}
        files[file.name] = [{
            'header': '@@ -0,0 +1,%d' % len(lines),
            'data': [(x, pygit2.GIT_DIFF_LINE_ADDITION) for x in lines],
            'new_start': 1,
            'old_start': 0,
        }]
    fstat[None] = {'-': sum([x['-'] for x in fstat.values()]), '+': sum([x['+'] for x in fstat.values()])}
    return files, fstat

def realdiff(diff):
    files = {}
    stat = {}
    # Can happen with subproject-only commits
    if not diff.changes:
        return {}, {None: {'+': 0, '-': 0}}
    for file in diff.changes['files']:
        files[file[1]] = []
        stat[file[1]] = {'-': 0, '+': 0}
    for hunk in diff.changes.get('hunks', []):
        files[hunk.new_file].append(hunk)
        stat[hunk.new_file]['-'] += len([x for x in hunk.data if x[1] == pygit2.GIT_DIFF_LINE_DELETION])
        stat[hunk.new_file]['+'] += len([x for x in hunk.data if x[1] == pygit2.GIT_DIFF_LINE_ADDITION])
    stat[None] = {'-': sum([x['-'] for x in stat.values()]), '+': sum([x['+'] for x in stat.values()])}
    return files, stat

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

def blob_link(repo, ref, path, file=None):
    parts = [x for x in (ref, path, file) if x]
    return url_for('blob', repo=repo.name, path='/'.join(parts))

def raw_link(repo, ref, path, file=None):
    parts = [x for x in (ref, path, file) if x]
    return url_for('raw', repo=repo.name, path='/'.join(parts))

def blame_link(repo, ref, path, file=None):
    parts = [x for x in (ref, path, file) if x]
    return url_for('blame', repo=repo.name, path='/'.join(parts))

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
