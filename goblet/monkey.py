import os
import pygit2
from flask import current_app
from memoize import memoize
import pwd
import pygments.lexers
import stat

class Repository(pygit2.Repository):
    @memoize
    def get_description(self):
        desc = os.path.join(self.path, 'description')
        if not os.path.exists(desc):
            return ""
        with open(desc) as fd:
            return fd.read()
    description = property(get_description)

    @memoize
    def get_name(self):
        name = self.path.replace(current_app.config['REPO_ROOT'], '')
        if name.startswith('/'):
            name = name[1:]
        if name.endswith('/.git/'):
            name = name[:-6]
        else:
            name = name[:-1]
        return name
    name = property(get_name)

    @memoize
    def get_owner(self):
        try:
            return self.config['gitweb.owner']
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
        files = dict([(x.name, {'id': x.oid, 'hex': x.hex, 'commit': None}) for x in get_tree(commit.tree, path)])
        last_commit = commit

        for commit in self.walk(commit.hex, pygit2.GIT_SORT_TIME):
            tree = get_tree(commit.tree, path)

            # No tree? Last commit introduced us!
            if not tree:
                for file in files:
                    if not files[file]['commit']:
                        files[file]['commit'] = last_commit
                break

            # Find changes
            done = 0
            for file in files:
                if files[file]['commit']:
                    done += 1
                    continue
                if file not in tree or tree[file].oid != files[file]['id']:
                    files[file]['commit'] = last_commit
                    done += 1

            # Are we done yet?
            last_commit = commit
            if done == len(files):
                break

        # Any files that still don't have a commit were last changed in
        # the initial commit
        for file in files:
            if not files[file]['commit']:
                files[file]['commit'] = last_commit
        
        return files

def get_tree(tree, path):
    try:
        for dir in path:
            tree = tree[dir].to_object()
    except KeyError:
        return None
    return tree

pygit2.Repository = Repository

def S_ISGITLNK(mode):
    return (mode & 0160000) == 0160000
stat.S_ISGITLNK = S_ISGITLNK

# Let's detect .pl as perl instead of prolog
pygments.lexers.LEXERS['PrologLexer'] = ('pygments.lexers.compiled', 'Prolog', ('prolog',), ('*.prolog', '*.pro'), ('text/x-prolog',))
