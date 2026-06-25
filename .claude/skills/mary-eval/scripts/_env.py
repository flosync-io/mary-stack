"""Minimal .env loader (no dependency on python-dotenv).

Loads KEY=VALUE pairs into os.environ WITHOUT overriding variables already set
in the real environment (so an explicit shell export always wins). Search order
(all found files are applied, later ones do not override earlier-set keys):

    1. an explicit path passed to load_env()
    2. $MARY_ENV
    3. ./.env               (current working directory)
    4. ~/.mary-eval.env     (per-user, survives across projects)
    5. <skill-dir>/.env     (next to the bundled scripts)
"""

import os


def _parse(path):
    vals = {}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("export "):
                    line = line[len("export "):]
                if "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k, v = k.strip(), v.strip()
                if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
                    v = v[1:-1]
                vals[k] = v
    except OSError:
        pass
    return vals


def load_env(explicit_path=None):
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        explicit_path,
        os.environ.get("MARY_ENV"),
        os.path.join(os.getcwd(), ".env"),
        os.path.expanduser("~/.mary-eval.env"),
        os.path.join(here, "..", ".env"),
    ]
    loaded = []
    for p in candidates:
        if p and os.path.isfile(p):
            for k, v in _parse(p).items():
                os.environ.setdefault(k, v)
            loaded.append(os.path.abspath(p))
    return loaded
