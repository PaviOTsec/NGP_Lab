"""Read-only: print lines matching a regex from files inside a .tgz app package (never extracts).
usage: python -I tools/splunk-uf/tgz_grep.py <pkg.tgz> <member-glob> <regex> [max_lines]"""
import fnmatch
import re
import sys
import tarfile

pkg, glob, rx = sys.argv[1], sys.argv[2], re.compile(sys.argv[3])
limit = int(sys.argv[4]) if len(sys.argv) > 4 else 80
n = 0
with tarfile.open(pkg, "r:*") as tf:
    for m in tf.getmembers():
        if not m.isfile() or not fnmatch.fnmatch(m.name, glob):
            continue
        for i, line in enumerate(tf.extractfile(m).read().decode("utf-8", "replace").splitlines(), 1):
            if rx.search(line):
                print(f"{m.name}:{i}: {line}")
                n += 1
                if n >= limit:
                    sys.exit(0)
