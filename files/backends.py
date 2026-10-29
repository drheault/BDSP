"""Storage backends for file roots: a local/mounted path, or an SMB share via smbprotocol."""

import os
import posixpath
from dataclasses import dataclass
from datetime import datetime


@dataclass
class Entry:
    name: str
    is_dir: bool
    size: int = 0
    modified: datetime | None = None
    rel: str = ""


class BackendError(Exception):
    pass


def _safe_join(base: str, rel: str) -> str:
    rel = (rel or "").replace("\\", "/").strip("/")
    parts = [p for p in rel.split("/") if p not in ("", ".", "..")]
    return os.path.join(base, *parts) if parts else base, "/".join(parts)


class MountBackend:
    def __init__(self, root):
        self.root = root
        self.base = root.path

    def _full(self, rel):
        full, clean = _safe_join(self.base, rel)
        return full, clean

    def available(self):
        return os.path.isdir(self.base)

    def listdir(self, rel=""):
        full, clean = self._full(rel)
        if not os.path.isdir(full):
            raise BackendError(f"Folder not found: {clean or '/'} (is the share mounted at {self.base}?)")
        out = []
        for name in sorted(os.listdir(full), key=str.lower):
            if name.startswith((".", "~$")):
                continue
            p = os.path.join(full, name)
            try:
                st = os.stat(p)
            except OSError:
                continue
            out.append(Entry(name=name, is_dir=os.path.isdir(p), size=st.st_size, modified=datetime.fromtimestamp(st.st_mtime), rel=posixpath.join(clean, name)))
        return sorted(out, key=lambda e: (not e.is_dir, e.name.lower()))

    def open(self, rel):
        full, _ = self._full(rel)
        if not os.path.isfile(full):
            raise BackendError("File not found.")
        return open(full, "rb"), os.path.basename(full), os.path.getsize(full)

    def save(self, rel_dir, filename, fileobj):
        full, clean = self._full(rel_dir)
        os.makedirs(full, exist_ok=True)
        name = os.path.basename(filename)
        target = os.path.join(full, name)
        with open(target, "wb") as f:
            for chunk in fileobj.chunks() if hasattr(fileobj, "chunks") else iter(lambda: fileobj.read(1 << 20), b""):
                f.write(chunk)
        return posixpath.join(clean, name)

    def mkdir(self, rel_dir, name):
        full, _ = self._full(rel_dir)
        os.makedirs(os.path.join(full, os.path.basename(name)), exist_ok=True)

    def walk(self, rel=""):
        full, clean = self._full(rel)
        for dirpath, dirnames, filenames in os.walk(full):
            dirnames[:] = [d for d in dirnames if not d.startswith(".")]
            for fn in filenames:
                if fn.startswith((".", "~$")):
                    continue
                p = os.path.join(dirpath, fn)
                st = os.stat(p)
                yield Entry(name=fn, is_dir=False, size=st.st_size, modified=datetime.fromtimestamp(st.st_mtime), rel=posixpath.relpath(p, self.base).replace("\\", "/"))


class SMBBackend:
    """UNC access through smbprotocol's high-level `smbclient` API."""

    def __init__(self, root):
        self.root = root
        self.base = root.path.rstrip("\\/")
        try:
            import smbclient  # noqa: F401
        except ImportError as e:  # pragma: no cover
            raise BackendError("smbprotocol is not installed.") from e
        import smbclient

        self.smb = smbclient
        self.smb.register_session(self._server(), username=root.username or None, password=root.password or None, connection_timeout=10)

    def _server(self):
        return self.base.lstrip("\\/").split("\\")[0].split("/")[0]

    def _full(self, rel):
        _, clean = _safe_join("", rel)
        return (self.base + ("\\" + clean.replace("/", "\\") if clean else "")), clean

    def available(self):
        try:
            self.smb.listdir(self.base)
            return True
        except Exception:
            return False

    def listdir(self, rel=""):
        full, clean = self._full(rel)
        out = []
        try:
            for name in self.smb.listdir(full):
                if name.startswith((".", "~$")):
                    continue
                p = full + "\\" + name
                st = self.smb.stat(p)
                is_dir = self.smb.path.isdir(p)
                out.append(Entry(name=name, is_dir=is_dir, size=0 if is_dir else st.st_size, modified=datetime.fromtimestamp(st.st_mtime), rel=posixpath.join(clean, name)))
        except Exception as e:
            raise BackendError(f"SMB error: {e}") from e
        return sorted(out, key=lambda e: (not e.is_dir, e.name.lower()))

    def open(self, rel):
        full, _ = self._full(rel)
        try:
            f = self.smb.open_file(full, mode="rb")
            return f, full.rsplit("\\", 1)[-1], self.smb.stat(full).st_size
        except Exception as e:
            raise BackendError(f"SMB error: {e}") from e

    def save(self, rel_dir, filename, fileobj):
        full, clean = self._full(rel_dir)
        name = os.path.basename(filename)
        try:
            with self.smb.open_file(full + "\\" + name, mode="wb") as f:
                for chunk in fileobj.chunks():
                    f.write(chunk)
        except Exception as e:
            raise BackendError(f"SMB error: {e}") from e
        return posixpath.join(clean, name)

    def mkdir(self, rel_dir, name):
        full, _ = self._full(rel_dir)
        self.smb.mkdir(full + "\\" + os.path.basename(name))

    def walk(self, rel=""):
        full, clean = self._full(rel)
        for dirpath, dirnames, filenames in self.smb.walk(full):
            for fn in filenames:
                if fn.startswith((".", "~$")):
                    continue
                p = dirpath + "\\" + fn
                st = self.smb.stat(p)
                relp = p[len(self.base):].strip("\\").replace("\\", "/")
                yield Entry(name=fn, is_dir=False, size=st.st_size, modified=datetime.fromtimestamp(st.st_mtime), rel=relp)


def backend_for(root):
    return SMBBackend(root) if root.kind == "smb" else MountBackend(root)
