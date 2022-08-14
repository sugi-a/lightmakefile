import sys, os, hashlib, json, pickle, hashlib, hmac
from pathlib import Path, PurePath
from collections import namedtuple

from ..core.rule import Event, IRule
from .file import IFile, IVFile

class Rule(IRule):
    def __init__(
        self,
        yfiles,
        xfiles,
        deplist,
        method,
        args,
        kwargs,
        memo,
        name=None,
    ):
        self.yfiles = yfiles
        self.xfiles = xfiles
        self._deplist = deplist
        self._method = method
        self._args = args
        self._kwargs = kwargs
        self.name = name
        self.memo = memo


    def should_update(
        self,
        par_updated,
        dry_run
    ):
        for k,f in self.xfiles:
            if not os.path.exists(f.path):
                if dry_run:
                    return True
                else:
                    raise Exception(f'Input file {f.path} is missing')

            if os.path.getmtime(f.path) == 0:
                if dry_run:
                    return True
                else:
                    raise Exception(
                        f'Input file {f.path} has mtime of 0. '
                        f'Input files with mtime of 0 are considered to be '
                        f'invalid for reducing operational error.'
                    )

        if dry_run and par_updated:
            return True

        if any(not os.path.exists(f.path) for f in self.yfiles):
            return True

        oldest_y = min(os.path.getmtime(f.path) for f in self.yfiles)

        if oldest_y <= 0:
            return True

        xvfiles = [] # input VFiles that are updated

        for k,f in self.xfiles:
            if os.path.getmtime(f.path) > oldest_y:
                if isinstance(f, IVFile):
                    xvfiles.append((k,f))
                else:
                    return True

        memo = load_memo(self.metadata_fname)

        if memo is None:
            return True

        vfile_hashes, arg_memo = memo

        hash_dic = {tuple(k): (h,t) for k,h,t in vfile_hashes}
            
        for k,f in xvfiles:
            if k not in hash_dic:
                return True

            mtime = os.path.getmtime(f.path)
            hash_, mtime_ = hash_dic[k]

            # Optimization: skip computing hash if the current mtime
            # is equal to the one in the cache
            if mtime != mtime_ and f.get_hash() != hash_:
                return True

        try:
            if not self.memo.compare(arg_memo):
                return True
        except Exception:
            raise Exception(
                f'Failed to check memoized arguments '
                f'loaded from {self.metadata_fname}'
            )

        return False


    def preprocess(self, callback):
        for f in self.yfiles:
            try:
                os.makedirs(f.path.parent, exist_ok=True)
            except:
                pass


    def postprocess(self, callback, succ):
        if succ:
            self.update_memo()
        else:
            # set mtime to 0
            for f in self.yfiles:
                try:
                    os.utime(f.path, (0, 0))
                except:
                    pass

            # delete vfile cache
            try:
                os.remove(self.metadata_fname)
            except:
                pass


    @property
    def metadata_fname(self):
        p = PurePath(self.yfiles[0].path)
        return p.parent / '.jtcmake' / p.name


    def update_memo(self):
        xvfiles = [(k,v) for k,v in self.xfiles if isinstance(v, IVFile)]
        save_memo(self.metadata_fname, xvfiles, self.memo.memo)


    @property
    def method(self): return self._method

    @property
    def args(self): return self._args

    @property
    def kwargs(self): return self._kwargs

    @property
    def deplist(self): return self._deplist


def create_vfile_hashes(vfiles):
    """
    list of (NestKey, file name, mtime)
    """
    res = [(k, f.get_hash(), os.path.getmtime(f.path)) for k,f in vfiles]
    res = json.loads(json.dumps(res)) # round trip JSON conversion
    return res
    

def save_vfile_hashes(metadata_fname, vfiles):
    hashes = create_vfile_hashes(vfiles)
    os.makedirs(Path(metadata_fname).parent, exist_ok=True)
    with open(metadata_fname, 'w') as f:
        try:
            json.dump(hashes, f)
        except Exception as e:
            raise ValueError(
                f'Failed to save IVFile hashes as JSON to {metadata_fname}.'
                f'This may be because some dictionary keys in the arguments'
                f' to specify the IVFile objects are not JSON convertible.'
            ) from e


def load_vfile_hashes(metadata_fname):
    if not os.path.exists(metadata_fname):
        return []

    with open(metadata_fname) as f:
        return json.load(f)


def save_memo(metadata_fname, vfiles, args_memo):
    vfile_hashes = create_vfile_hashes(vfiles)
    data = { "vfiles": vfile_hashes, "args": args_memo }
    os.makedirs(Path(metadata_fname).parent, exist_ok=True)
    with open(metadata_fname, 'w') as f:
        json.dump(data, f)


def load_memo(metadata_fname):
    if not os.path.exists(metadata_fname):
        return None

    with open(metadata_fname) as f:
        data = json.load(f)

    vfile_hashes = data['vfiles']
    args = data['args']

    return vfile_hashes, args
    