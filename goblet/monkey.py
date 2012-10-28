import os
import pygit2
from flask import current_app
from memoize import memoize
import pwd
import pygments.lexers
import stat
from whelk import shell
from goblet.encoding import decode
from collections import defaultdict

class Repository(pygit2.Repository):
    def __init__(self, path):
        if os.path.exists(path):
            return super(Repository, self).__init__(path)
        else:
            return super(Repository, self).__init__(path + '.git')

    @memoize
    def get_description(self):
        desc = os.path.join(self.path, 'description')
        if not os.path.exists(desc):
            return ""
        with open(desc) as fd:
            return decode(fd.read())
    description = property(get_description)

    @memoize
    def get_name(self):
        name = self.path.replace(current_app.config['REPO_ROOT'], '')
        if name.startswith('/'):
            name = name[1:]
        if name.endswith('/.git/'):
            name = name[:-6]
        else:
            name = name[:-5]
        return name
    name = property(get_name)

    @memoize
    def get_clone_urls(self):
        clone_base = current_app.config.get('CLONE_URLS_BASE', {})
        ret = {}
        for proto in ('git', 'ssh', 'http'):
            try:
                ret[proto] = self.config['goblet.cloneurl%s' % proto]
                continue
            except KeyError:
                pass
            if proto not in clone_base:
                continue
            if self.config['core.bare']:
                ret[proto] = clone_base[proto] + os.path.basename(self.path)
            else:
                ret[proto] = clone_base[proto] + os.path.basename(os.path.dirname(os.path.dirname(self.path)))
        return ret
    clone_urls = property(get_clone_urls)

    @memoize
    def get_owner(self):
        try:
            return self.config['goblet.owner']
        except KeyError:
            uid = os.stat(self.path).st_uid
            pwn = pwd.getpwuid(uid)
            if pwn.pw_gecos:
                if ',' in pwn.pw_gecos:
                    return pwn.pw_gecos[:pwn.pw_gecos.find(',')]
                return pwn.pw_gecos
            return pwn.pw_name
    owner = property(get_owner)

    def branches(self):
        return sorted([x[11:] for x in self.listall_references() if x.startswith('refs/heads/')])

    def tags(self):
        return sorted([x[10:] for x in self.listall_references() if x.startswith('refs/tags/')])

    def commit_to_ref_hash(self):
        ret = defaultdict(list)
        for ref in self.listall_references():
            if ref.startswith('refs/remotes/'):
                continue
            if ref.startswith('refs/tags/'):
                obj = self[self.lookup_reference(ref).hex]
                if obj.type == pygit2.GIT_OBJ_COMMIT:
                    ret[obj.hex].append(('tag', ref[10:]))
                else:
                    ret[self[self[obj.target].hex].hex].append(('tag', ref[10:]))
            else:
                ret[self.lookup_reference(ref).hex].append(('head', ref[11:]))
        return ret

    def symref(self, hex):
        if hasattr(hex, 'hex'):
            hex = hex.hex
        for ref in self.listall_references():
            if not ref.startswith('refs/heads/'):
                continue
            if self.lookup_reference(ref).hex == hex:
                return ref[11:]
        return hex

    @property
    def head(self):
        try:
            return super(Repository, self).head
        except pygit2.GitError:
            return None

    def get_commits(self, ref, skip, count):
        for num, commit in enumerate(self.walk(ref.hex, pygit2.GIT_SORT_TIME)):
            if num < skip:
                continue
            if num >= skip + count:
                break
            yield commit

    def describe(self, commit):
        tags = [self.lookup_reference(x) for x in self.listall_references() if x.startswith('refs/tags')]
        if not tags:
            return 'g' + commit[:7]
        tags = [(tag.name[10:], self[tag.hex]) for tag in tags]
        tags = dict([(hasattr(obj, 'target') and self[obj.target].hex or obj.hex, name) for name, obj in tags])
        count = 0
        for parent in self.walk(commit, pygit2.GIT_SORT_TIME):
            if parent.hex in tags:
                if count == 0:
                    return tags[parent.hex]
                return '%s-%d-g%s' % (tags[parent.hex], count, commit[:7])
            count += 1
        return 'g' + commit[:7]

    def ls_tree(self, tree, path=''):
        ret = []
        for entry in tree:
            if stat.S_ISDIR(entry.filemode):
                ret += self.ls_tree(entry.to_object(), os.path.join(path, entry.name))
            else:
                ret.append(os.path.join(path, entry.name))
        return ret

    def tree_lastchanged(self, commit, path):
        """Get a dict containing oid and commit that last changed files in a directory"""
        files = dict([(x.name, {'id': x.oid, 'hex': x.hex, 'commit': None, 'addition': True}) for x in get_tree(commit.tree, path)])
        todo = files.keys()
        commit_ = commit

        for commit in self.walk(commit.hex, pygit2.GIT_SORT_TIME):
            tree = get_tree(commit.tree, path)
            if not tree:
                continue
            # If we don't have the tree, consider this as possible addition point
            addition = None
            for file in todo[:]:
                if file not in tree:
                    continue
                for parent in commit.parents:
                    ptree = get_tree(parent.tree, path)
                    if file in ptree and tree[file].oid == ptree[file].oid:
                        break
                else:
                    files[file]['commit'] = commit
                    todo.remove(file)

        return files

    def blame(self, commit, path):
        contents = self.git('blame', '-p', path)

    def git(self, *args):
        return shell.git('--git-dir', self.path, *args)

def get_tree(tree, path):
    for dir in path:
        if dir not in tree:
            return None
        tree = tree[dir].to_object()
    return tree

pygit2.Repository = Repository

def S_ISGITLNK(mode):
    return (mode & 0160000) == 0160000
stat.S_ISGITLNK = S_ISGITLNK

# Let's detect .pl as perl instead of prolog
pygments.lexers.LEXERS['PrologLexer'] = ('pygments.lexers.compiled', 'Prolog', ('prolog',), ('*.prolog', '*.pro'), ('text/x-prolog',))
