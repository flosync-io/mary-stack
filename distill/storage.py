#!/usr/bin/env python3
"""
distill/storage.py — single Supabase I/O layer for the distill block.

All reads/writes to Supabase (vault table + mary-memory Storage bucket) go
through this module. Nothing else in distill/ imports requests or touches
Supabase directly.

Instantiate with source="bucket" (default) or source="local":

  bucket: reads SUPABASE_URL + SUPABASE_SERVICE_KEY (falls back to
          SUPABASE_API_KEY) from env or a .env file in the repo root.

  local:  same signatures, no network. list_promotable scans a dir of
          runtime blobs; get/put_knowledge read/write local files;
          mark_promoted is a no-op. Used by smoke tests.

mark_promoted() is implemented but NOT yet called from promote.py --apply;
that wiring is the next step.
"""
import glob, json, os, requests
from pathlib import Path

BUCKET = "mary-memory"
RESOLVED_STATUSES = ("green", "resolved")


def _load_env(path=None):
    """Load key=value pairs from a .env file into os.environ (no third-party dep)."""
    candidates = []
    if path:
        candidates.append(Path(path))
    candidates += [
        Path(__file__).parent.parent / ".env",
        Path.home() / ".mary.env",
    ]
    for p in candidates:
        if p.exists():
            with open(p) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, _, v = line.partition("=")
                        os.environ.setdefault(k.strip(), v.strip())
            return


class StorageClient:
    """
    Thin I/O wrapper for Supabase Storage (mary-memory bucket) and the
    PostgREST vault table.

    Parameters
    ----------
    source : "bucket" | "local"
    local_runtime_dir   : path to dir of {conv_id}.json blobs  (local mode)
    local_knowledge_dir : path to dir holding knowledge-{machine}.json  (local mode)
    env_file            : explicit path to a .env file (bucket mode)
    """

    def __init__(self, source="bucket", local_runtime_dir=None,
                 local_knowledge_dir=None, env_file=None):
        self.source = source
        if source == "bucket":
            _load_env(env_file)
            self._url = os.environ.get("SUPABASE_URL", "").rstrip("/")
            self._key = (os.environ.get("SUPABASE_SERVICE_KEY") or
                         os.environ.get("SUPABASE_API_KEY") or "")
            if not self._url or not self._key:
                raise RuntimeError(
                    "SUPABASE_URL and SUPABASE_SERVICE_KEY (or SUPABASE_API_KEY) "
                    "must be set in environment or .env"
                )
            self._auth = {
                "apikey": self._key,
                "Authorization": f"Bearer {self._key}",
            }
        else:
            self._local_rt = local_runtime_dir or ""
            self._local_kb = local_knowledge_dir or ""

    # ── internal helpers ──────────────────────────────────────────────────────

    def _storage_get(self, path):
        url = f"{self._url}/storage/v1/object/{BUCKET}/{path}"
        r = requests.get(url, headers=self._auth, timeout=15)
        if r.status_code == 404:
            raise FileNotFoundError(f"Storage object not found: {path}")
        if not r.ok:
            raise RuntimeError(f"Storage GET {path} → {r.status_code}: {r.text[:300]}")
        return r.json()

    def _storage_put(self, path, obj):
        url = f"{self._url}/storage/v1/object/{BUCKET}/{path}"
        headers = {**self._auth,
                   "Content-Type": "application/json",
                   "x-upsert": "true"}
        r = requests.post(url, headers=headers, data=json.dumps(obj), timeout=15)
        if not r.ok:
            raise RuntimeError(f"Storage PUT {path} → {r.status_code}: {r.text[:300]}")

    def _rest_get(self, table, params):
        url = f"{self._url}/rest/v1/{table}"
        headers = {**self._auth, "Accept": "application/json"}
        r = requests.get(url, headers=headers, params=params, timeout=15)
        if not r.ok:
            raise RuntimeError(f"REST GET {table} → {r.status_code}: {r.text[:300]}")
        return r.json()

    def _rest_patch(self, table, params, body):
        url = f"{self._url}/rest/v1/{table}"
        headers = {**self._auth,
                   "Content-Type": "application/json",
                   "Prefer": "return=minimal"}
        r = requests.patch(url, headers=headers, params=params, json=body, timeout=15)
        if not r.ok:
            raise RuntimeError(f"REST PATCH {table} → {r.status_code}: {r.text[:300]}")

    # ── public API ────────────────────────────────────────────────────────────

    def list_promotable(self, machine_id):
        """
        Return conversation_ids of resolved, unpromoted sessions.

        Bucket: queries vault — status=resolved AND promoted_at IS NULL.
        Local:  scans local_runtime_dir for blobs where status in
                ("green","resolved"). No promoted_at concept locally.
        """
        if self.source == "local":
            if not self._local_rt:
                return []
            out = []
            for fp in sorted(glob.glob(os.path.join(self._local_rt, "*.json"))):
                try:
                    d = json.loads(Path(fp).read_text())
                    if d.get("status") in RESOLVED_STATUSES:
                        out.append(os.path.splitext(os.path.basename(fp))[0])
                except Exception as exc:
                    print(f"  [warn] skipping {fp}: {exc}")
            return out

        rows = self._rest_get("vault", {
            "machine_id":  f"eq.{machine_id}",
            "status":      "eq.resolved",
            "promoted_at": "is.null",
            "select":      "conversation_id",
        })
        return [row["conversation_id"] for row in rows]

    def get_runtime(self, machine_id, conv_id):
        """Fetch and parse a runtime blob."""
        if self.source == "local":
            fp = os.path.join(self._local_rt, f"{conv_id}.json")
            if not os.path.exists(fp):
                raise FileNotFoundError(f"Local runtime not found: {fp}")
            return json.loads(Path(fp).read_text())
        return self._storage_get(f"runtime/{machine_id}/{conv_id}.json")

    def get_knowledge(self, machine_id):
        """Fetch the current knowledge.json for a machine."""
        if self.source == "local":
            fp = os.path.join(self._local_kb, f"knowledge-{machine_id}.json")
            if not os.path.exists(fp):
                raise FileNotFoundError(f"Local knowledge not found: {fp}")
            return json.loads(Path(fp).read_text())
        return self._storage_get(f"knowledge/{machine_id}.json")

    def put_knowledge(self, machine_id, obj):
        """Write (upsert) knowledge.json for a machine."""
        if self.source == "local":
            if not self._local_kb:
                raise RuntimeError("local_knowledge_dir not set")
            fp = os.path.join(self._local_kb, f"knowledge-{machine_id}.json")
            os.makedirs(self._local_kb, exist_ok=True)
            Path(fp).write_text(json.dumps(obj, indent=2))
            return
        self._storage_put(f"knowledge/{machine_id}.json", obj)

    def mark_promoted(self, conv_ids, version):
        """
        Stamp vault rows: promoted_at = now(), promoted_into_version = version.
        No-op in local mode (smoke tests don't need the ledger stamp).
        Not yet wired into promote.py --apply — that's the next step.
        """
        if self.source == "local":
            return
        if not conv_ids:
            return
        csv = ",".join(conv_ids)
        self._rest_patch(
            "vault",
            params={"conversation_id": f"in.({csv})"},
            body={"promoted_at": "now()", "promoted_into_version": version},
        )


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="storage.py smoke — list promotable sessions")
    ap.add_argument("--machine-id", default="DMC80FD-01")
    ap.add_argument("--env-file", default=None)
    a = ap.parse_args()

    client = StorageClient(source="bucket", env_file=a.env_file)
    print(f"list_promotable({a.machine_id!r}) ...")
    ids = client.list_promotable(a.machine_id)
    print(f"  → {len(ids)} promotable conversation(s):")
    for c in ids:
        print(f"    {c}")
    if not ids:
        print("  (none — vault table may be empty or all sessions already promoted)")
