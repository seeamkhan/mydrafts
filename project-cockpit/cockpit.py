#!/usr/bin/env python3
"""project-cockpit: docs, plans, decisions, an action board, a system map,
logs and one dashboard, for any repository.

Drop it next to (or inside) a project and run:

    python3 cockpit.py init   --root /path/to/repo     # detect + scaffold, never overwrites
    python3 cockpit.py build  --root /path/to/repo     # static dashboard in .cockpit/site/
    python3 cockpit.py serve  --root /path/to/repo     # build, then serve it on localhost
    python3 cockpit.py check  --root /path/to/repo     # every validator, exit 1 on a problem

Everything else:

    detect                      what the repo has (languages, services, jobs, logs, docs)
    index                       rewrite the agent context map (.cockpit/index.md)
    status [--json]             each doc's status, and any label/doc drift
    board list|add|did|done|back|check
    system check|probe          validate the system map, or probe every component
    logs [ID] [-n N] [--grep X] tail the logs the system map points at
    adr new "Title"             next numbered decision record from the template
    plan new TOPIC | context new TOPIC
    lint FILE                   check a plan or context file has its required sections
    vendor                      copy this kit into the repo (.cockpit/kit/) so it travels

Standard library only (Python 3.9+). If the `markdown` package is installed it
is used for nicer HTML; otherwise a small built-in renderer takes over.
"""
from __future__ import annotations

import argparse
import datetime as dt
import fnmatch
import hashlib
import html
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import urllib.request
from pathlib import Path

VERSION = "1.0.0"
KIT_DIR = Path(__file__).resolve().parent
TEMPLATES = KIT_DIR / "templates"

STATUSES = ("done", "started", "todo", "blocked", "cancel", "living")
STATUS_ICON = {"done": "✅", "started": "🟡", "todo": "⬜", "blocked": "⛔", "cancel": "❌", "living": "📘"}
# Docs that are never "finished" (README, CHANGELOG, MANUAL, agent rules,
# templates) default to "living" instead of "started".
LIVING_KINDS = ("readme", "changelog", "manual", "agents", "template")
KIND_LABEL = {"agents": "Agent instructions", "readme": "Readmes", "manual": "Manual",
              "context": "Context files", "plan": "Plans", "adr": "Decisions (ADRs)",
              "changelog": "Changelog", "doc": "Other docs", "template": "Templates"}
PRIORITIES = ("P1", "P2", "P3", "P4", "P5")
BOARD_STATES = ("open", "review", "done")
BOARD_REQUIRED = ("id", "priority", "task", "what", "why", "steps", "dod")
SYSTEM_REQUIRED = ("id", "name", "what", "group")
PROBE_TYPES = ("http", "tcp", "file", "process", "command", "none")
DRAFT_MARK = "REPLACE ME"

DEFAULT_CONFIG = {
    "project": "",
    "docs_exclude": ["node_modules/", "vendor/", "dist/", "build/", "target/", ".venv/",
                     "venv/", ".git/", ".cockpit/", ".claude/", "site-packages/",
                     ".tox/", "__pycache__/"],
    "default_status": "started",
    "adr_dir": "docs/adr",
    "plans_dir": "plans",
    "site_out": ".cockpit/site",
    "logs_in_site": True,
    "log_tail_lines": 200,
    "renderer": "auto",
}


# --------------------------------------------------------------------------
# repo + config
# --------------------------------------------------------------------------

class Repo:
    def __init__(self, root: str | os.PathLike):
        self.root = Path(root).resolve()
        self.dir = self.root / ".cockpit"
        self.config = dict(DEFAULT_CONFIG)
        cfg = self.dir / "config.json"
        if cfg.exists():
            user = json.loads(cfg.read_text(encoding="utf-8"))
            extra = user.pop("docs_exclude", []) or []
            self.config.update(user)
            # Built-in exclusions always apply; the config only adds to them.
            self.config["docs_exclude"] = DEFAULT_CONFIG["docs_exclude"] + [
                x for x in extra if x not in DEFAULT_CONFIG["docs_exclude"]]
        if not self.config["project"]:
            self.config["project"] = self.root.name

    def path(self, rel: str) -> Path:
        return self.root / rel

    @property
    def board_file(self) -> Path:
        return self.dir / "board.json"

    @property
    def system_file(self) -> Path:
        return self.dir / "system-map.json"

    @property
    def status_file(self) -> Path:
        return self.dir / "status.json"

    @property
    def state_dir(self) -> Path:
        d = self.dir / "state"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def is_git(self) -> bool:
        return (self.root / ".git").exists()

    def git(self, *args: str) -> str:
        try:
            return subprocess.run(["git", *args], cwd=self.root, capture_output=True,
                                  text=True, timeout=30).stdout
        except (OSError, subprocess.TimeoutExpired):
            return ""


def read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def today() -> str:
    return dt.date.today().isoformat()


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "item"


# --------------------------------------------------------------------------
# docs: discovery, status, metadata
# --------------------------------------------------------------------------

def _excluded(rel: str, patterns: list[str]) -> bool:
    for p in patterns:
        if p.endswith("/"):
            if rel.startswith(p) or f"/{p}" in f"/{rel}":
                return True
        elif fnmatch.fnmatch(rel, p):
            return True
    return False


def list_docs(repo: Repo) -> list[str]:
    """Every markdown file worth showing. Git-tracked files when this is a git
    repo (so scratch and secrets that are gitignored never show), else a walk."""
    found: set[str] = set()
    if repo.is_git():
        out = repo.git("ls-files", "-z", "--cached", "--others", "--exclude-standard", "--", "*.md")
        found = {f for f in out.split("\0") if f}
    if not found:
        for dirpath, dirnames, filenames in os.walk(repo.root):
            dirnames[:] = [d for d in dirnames if not d.startswith(".") or d in (".cockpit", ".github")]
            for fn in filenames:
                if fn.endswith(".md"):
                    found.add(os.path.relpath(os.path.join(dirpath, fn), repo.root).replace(os.sep, "/"))
    return sorted(f for f in found
                  if not _excluded(f, repo.config["docs_exclude"]) and (repo.root / f).is_file())


_STATUS_LINE = re.compile(
    r"^\s*(?:#+\s*)?(?:\*\*|__)?\s*status\b\s*(?:\([^)]*\))?\s*(?:\*\*|__)?\s*:\s*(?:\*\*|__)?\s*(.+)$", re.I)
_STATUS_RULES = [
    ("cancel", re.compile(r"\b(cancel+ed|cancel|parked|retired|abandoned|superseded|dropped|rejected|deprecated)\b", re.I)),
    ("todo", re.compile(r"\b(not started|build not started|not built|to ?do|queued|planned|backlog)\b", re.I)),
    ("blocked", re.compile(r"\b(blocked|on hold)\b", re.I)),
    ("done", re.compile(r"^(all )?(done|complete|completed|finished|accepted|closed|resolved|delivered|shipped|released|live)\b", re.I)),
    ("done", re.compile(r"^all\b[^.;:]{0,40}\bdone\b", re.I)),
    ("started", re.compile(r"\b(in progress|ongoing|wip|started|proposed|draft|in review|not done)\b", re.I)),
]
HEAD_LINES = 40


def classify_status(text: str) -> str | None:
    """One status phrase -> a status, or None when it is not clear. Only the
    first sentence counts: later sentences are history."""
    t = re.sub(r"[*_`]", "", text).strip()
    t = re.sub(r"^\(?\d{4}-\d{2}-\d{2}[^)]*\)?\s*[:,-]?\s*", "", t)
    t = re.split(r"(?<=[a-z0-9)])[.!]\s", t, maxsplit=1, flags=re.I)[0]
    for status, rx in _STATUS_RULES:
        if rx.search(t):
            return status
    return None


def own_status(markdown: str) -> tuple[str | None, str]:
    """(status, line) from the first Status line in the top 40 lines. A bare
    `## Status` heading reads the first non-empty line under it."""
    lines = markdown.split("\n")[:HEAD_LINES]
    fenced = False
    for i, line in enumerate(lines):
        if line.lstrip().startswith(("```", "~~~")):
            fenced = not fenced
        if fenced:
            continue
        m = _STATUS_LINE.match(line)
        if m:
            return classify_status(m.group(1)), line.strip()
        if re.match(r"^\s*#+\s*status\s*$", line, re.I):
            for nxt in lines[i + 1:]:
                if nxt.strip():
                    return classify_status(nxt), nxt.strip()
            return None, line.strip()
    return None, ""


def status_overrides(repo: Repo) -> dict[str, str]:
    raw = read_json(repo.status_file, {})
    return {k: v for k, v in raw.items() if not k.startswith("_")}


def doc_label(rel: str, markdown: str, overrides: dict[str, str], default: str) -> tuple[str, str]:
    """(status, source). First match wins:
    1. .cockpit/status.json exact file   (a person decided)
    2. the doc's own Status line         (whoever did the work wrote it)
    3. .cockpit/status.json folder key   (a guess for a folder)
    4. the default"""
    if rel in overrides:
        return overrides[rel], "status.json"
    own, _ = own_status(markdown)
    if own:
        return own, "doc"
    folders = [k for k in overrides if k.endswith("/") and rel.startswith(k)]
    if folders:
        return overrides[max(folders, key=len)], "status.json folder"
    return default, "default"


def frontmatter(text: str) -> tuple[dict, str]:
    fm: dict[str, str] = {}
    if text.startswith("---\n"):
        end = text.find("\n---", 4)
        if end != -1:
            for ln in text[4:end].splitlines():
                m = re.match(r"\s*([A-Za-z0-9_-]+)\s*:\s*(.*?)\s*$", ln)
                if m:
                    fm[m.group(1).lower()] = m.group(2).strip().strip('"')
            return fm, text[end + 4:].lstrip("\n")
    return fm, text


def doc_kind(rel: str, fm: dict, adr_dir: str, plans_dir: str) -> str:
    name = rel.rsplit("/", 1)[-1].lower()
    if fm.get("doc-type"):
        return fm["doc-type"].lower()
    if "template" in name:
        return "template"
    if rel.startswith(adr_dir.rstrip("/") + "/") and re.match(r"\d{4}-", name):
        return "adr"
    if name.endswith("-context.md") or name.endswith("-context-memory.md"):
        return "context"
    if name.endswith("-plan.md") or name == "plan.md":
        return "plan"
    if name == "changelog.md":
        return "changelog"
    if name == "manual.md":
        return "manual"
    if name == "readme.md":
        return "readme"
    if name in ("agents.md", "claude.md", "gemini.md", "copilot-instructions.md"):
        return "agents"
    return "doc"


class Doc:
    def __init__(self, repo: Repo, rel: str, overrides: dict[str, str], dates: dict[str, str]):
        self.rel = rel
        self.raw = (repo.root / rel).read_text(encoding="utf-8", errors="replace")
        self.fm, self.body = frontmatter(self.raw)
        m = re.search(r"^#\s+(.+?)\s*#*\s*$", self.body, re.M)
        self.title = m.group(1).strip() if m else rel.rsplit("/", 1)[-1][:-3]
        self.kind = doc_kind(rel, self.fm, repo.config["adr_dir"], repo.config["plans_dir"])
        default = "living" if self.kind in LIVING_KINDS else repo.config["default_status"]
        self.status, self.status_from = doc_label(rel, self.body, overrides, default)
        self.own_status, self.own_line = own_status(self.body)
        if self.kind == "template":   # a template's Status line is a placeholder
            self.status, self.status_from, self.own_status = "living", "template", None
        lf = self.fm.get("load-for") or ""
        if not lf:
            m = re.search(r"\*\*Load for:\*\*\s*(.+)", self.body)
            lf = m.group(1).strip() if m else ""
        self.load_for = lf
        m = re.search(r"\*\*Owner:\*\*\s*([^|\n]+)", self.body)
        self.owner = m.group(1).strip() if m else ""
        self.updated = dates.get(rel) or dt.date.fromtimestamp(
            (repo.root / rel).stat().st_mtime).isoformat()

    @property
    def folder(self) -> str:
        return self.rel.rsplit("/", 1)[0] if "/" in self.rel else "(root)"


def git_dates(repo: Repo) -> dict[str, str]:
    """Last commit date per file, from one git log call."""
    if not repo.is_git():
        return {}
    out = repo.git("log", "--name-only", "--format=@@%cs", "--", "*.md")
    dates: dict[str, str] = {}
    current = ""
    for line in out.splitlines():
        if line.startswith("@@"):
            current = line[2:]
        elif line.strip() and line not in dates:
            dates[line] = current
    return dates


def load_docs(repo: Repo) -> list[Doc]:
    overrides = status_overrides(repo)
    dates = git_dates(repo)
    return [Doc(repo, rel, overrides, dates) for rel in list_docs(repo)]


def drift(docs: list[Doc]) -> list[Doc]:
    """Docs whose label comes from status.json but whose own text clearly
    says something else."""
    return [d for d in docs if d.own_status and d.status_from != "doc" and d.status != d.own_status]


# --------------------------------------------------------------------------
# detection (init uses this to pre-fill the system map)
# --------------------------------------------------------------------------

LANG_MARKERS = {
    "package.json": "JavaScript/TypeScript", "pyproject.toml": "Python", "requirements.txt": "Python",
    "setup.py": "Python", "go.mod": "Go", "Cargo.toml": "Rust", "pom.xml": "Java",
    "build.gradle": "Java/Kotlin", "build.gradle.kts": "Kotlin", "Gemfile": "Ruby",
    "composer.json": "PHP", "mix.exs": "Elixir", "Package.swift": "Swift",
}
SKIP_WALK = {".git", "node_modules", "vendor", "dist", "build", "target", ".venv", "venv",
             "__pycache__", ".cockpit", ".tox", ".idea", ".vscode"}


def _walk(root: Path, max_depth: int = 4):
    root_depth = len(root.parts)
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_WALK]
        if len(Path(dirpath).parts) - root_depth >= max_depth:
            dirnames[:] = []
        for fn in filenames:
            yield Path(dirpath) / fn


def _yaml_top_keys(text: str, section: str) -> list[tuple[str, str]]:
    """Children of a top-level YAML key, with their raw block. Enough for
    docker-compose services and workflow jobs; not a YAML parser."""
    out, inside, indent, name, block = [], False, None, None, []
    for line in text.splitlines():
        if re.match(rf"^{section}\s*:\s*$", line):
            inside = True
            continue
        if inside:
            if line and not line[0].isspace() and not line.startswith("#"):
                break
            m = re.match(r"^(\s+)([A-Za-z0-9_.-]+)\s*:\s*$", line)
            if m and (indent is None or len(m.group(1)) == indent):
                indent = len(m.group(1))
                if name:
                    out.append((name, "\n".join(block)))
                name, block = m.group(2), []
            elif name:
                block.append(line)
    if name:
        out.append((name, "\n".join(block)))
    return out


def detect(repo: Repo) -> dict:
    root = repo.root
    found = {"languages": [], "components": [], "logs": [], "docs": {}, "agents": [], "ci": []}
    files = list(_walk(root))
    rels = [f.relative_to(root).as_posix() for f in files]
    names = {f.name for f in files}

    found["languages"] = sorted({lang for marker, lang in LANG_MARKERS.items() if marker in names})
    for r in ("README.md", "CHANGELOG.md", "MANUAL.md", "AGENTS.md", "CLAUDE.md", "mkdocs.yml"):
        if (root / r).exists():
            found["docs"][r] = True
    for d in ("docs/adr", "doc/adr", "adr", "docs/decisions", "docs/architecture/decisions"):
        if (root / d).is_dir():
            found["docs"]["adr_dir"] = d
            break
    for a in ("AGENTS.md", "CLAUDE.md", ".cursorrules", ".github/copilot-instructions.md",
              ".windsurfrules", "GEMINI.md"):
        if (root / a).exists():
            found["agents"].append(a)

    comps = found["components"]

    def add(cid, name, what, group, host, code, probe=None, logs=None):
        if any(c["id"] == cid for c in comps):
            return
        row = {"id": cid, "name": name, "what": what, "group": group, "host": host, "code": code,
               "talksTo": [], "probe": probe or {"type": "none"}}
        if logs:
            row["logs"] = logs
        comps.append(row)

    for rel in rels:
        base = rel.rsplit("/", 1)[-1]
        if base in ("docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"):
            text = (root / rel).read_text(errors="replace")
            for svc, block in _yaml_top_keys(text, "services"):
                port = re.search(r"[\"']?(\d{2,5}):(\d{2,5})", block)
                probe = {"type": "tcp", "host": "127.0.0.1", "port": int(port.group(1))} if port else None
                add(slug(svc), svc, f"{DRAFT_MARK}: what the '{svc}' service does, in one plain sentence."
                    + (f" (compose port {port.group(1)})" if port else ""),
                    "services", f"docker compose ({rel})", rel, probe)
        elif base == "Dockerfile" or base.startswith("Dockerfile."):
            text = (root / rel).read_text(errors="replace")
            port = re.search(r"^EXPOSE\s+(\d+)", text, re.M)
            folder = rel.rsplit("/", 1)[0] if "/" in rel else repo.config["project"]
            add(slug(folder) + "-container", f"{folder} container",
                f"{DRAFT_MARK}: what this container runs, in one plain sentence.", "services",
                f"container ({rel})", rel,
                {"type": "tcp", "host": "127.0.0.1", "port": int(port.group(1))} if port else None)
        elif base == "Procfile":
            for line in (root / rel).read_text(errors="replace").splitlines():
                m = re.match(r"^([A-Za-z0-9_-]+):\s*(.+)$", line)
                if m:
                    add(slug(m.group(1)), m.group(1), f"{DRAFT_MARK}: what the '{m.group(1)}' process does."
                        f" Runs: {m.group(2)[:80]}", "services", "Procfile", rel)
        elif base == "package.json":
            data = read_json(root / rel, {})
            for script in ("start", "serve", "dev"):
                if script in (data.get("scripts") or {}):
                    port = re.search(r"(?:PORT=|--port[ =]|-p )(\d{2,5})", data["scripts"][script])
                    add(slug((data.get("name") or rel.rsplit("/", 1)[0] or "app")) + "-app",
                        data.get("name") or "app",
                        f"{DRAFT_MARK}: what this app does for its users. Started with `npm run {script}`.",
                        "services", "node", rel,
                        {"type": "tcp", "host": "127.0.0.1", "port": int(port.group(1))} if port else None)
                    break
        elif base.endswith(".service") and "[Service]" in (root / rel).read_text(errors="replace")[:4000]:
            add(slug(base[:-8]), base[:-8], f"{DRAFT_MARK}: what this systemd unit does.",
                "services", "systemd", rel, {"type": "command", "run": f"systemctl is-active {base}"})
        elif base.endswith(".plist") and "Label" in (root / rel).read_text(errors="replace")[:4000]:
            label = re.search(r"<key>Label</key>\s*<string>([^<]+)</string>", (root / rel).read_text(errors="replace"))
            if label:
                add(slug(label.group(1)), label.group(1), f"{DRAFT_MARK}: what this launchd job does and when.",
                    "jobs", "launchd", rel, {"type": "command", "run": f"launchctl list {label.group(1)}"})
        elif rel.startswith(".github/workflows/") and base.endswith((".yml", ".yaml")):
            text = (root / rel).read_text(errors="replace")
            wname = re.search(r"^name:\s*(.+)$", text, re.M)
            title = (wname.group(1).strip().strip("'\"") if wname else base.rsplit(".", 1)[0])
            found["ci"].append(rel)
            if re.search(r"^\s*schedule\s*:", text, re.M):
                cron = re.search(r"cron:\s*['\"]?([^'\"\n]+)", text)
                add(slug(title) + "-schedule", f"{title} (scheduled)",
                    f"{DRAFT_MARK}: what this scheduled workflow does."
                    + (f" Cron: {cron.group(1).strip()}" if cron else ""), "jobs", "GitHub Actions", rel)
        elif re.search(r"(^|/)k8s/|(^|/)kubernetes/|(^|/)helm/", rel) and base.endswith((".yml", ".yaml")):
            text = (root / rel).read_text(errors="replace")
            for kind, name in re.findall(r"kind:\s*(Deployment|StatefulSet|CronJob|DaemonSet)\s*\n(?:.*\n){0,6}?\s*name:\s*([A-Za-z0-9_.-]+)", text):
                add(slug(name), name, f"{DRAFT_MARK}: what this {kind} does.",
                    "jobs" if kind == "CronJob" else "services", f"Kubernetes {kind}", rel)
        elif base in ("crontab", "cron.txt") or base.endswith(".cron"):
            for line in (root / rel).read_text(errors="replace").splitlines():
                if line.strip() and not line.startswith("#") and len(line.split()) > 5:
                    cmd = " ".join(line.split()[5:])
                    add(slug(cmd.split()[0].rsplit("/", 1)[-1]), cmd.split()[0].rsplit("/", 1)[-1],
                        f"{DRAFT_MARK}: what this cron job does. Schedule: {' '.join(line.split()[:5])}",
                        "jobs", "cron", rel)

    for f in files:
        rel = f.relative_to(root).as_posix()
        if f.suffix == ".log" or (f.parent.name in ("logs", "log") and f.is_file() and f.suffix in ("", ".txt", ".out", ".err")):
            found["logs"].append(rel)
    for d in ("logs", "log", "var/log"):
        if (root / d).is_dir() and d + "/" not in found["logs"]:
            found["logs"].append(d + "/")
    found["logs"] = sorted(set(found["logs"]))[:50]
    return found


# --------------------------------------------------------------------------
# init: scaffold, never overwrite
# --------------------------------------------------------------------------

BLOCK_START, BLOCK_END = "<!-- cockpit:start -->", "<!-- cockpit:end -->"


def render_template(text: str, values: dict) -> str:
    return re.sub(r"\{\{(\w+)\}\}", lambda m: str(values.get(m.group(1), m.group(0))), text)


def init(repo: Repo, *, dry_run: bool = False, skills: bool = True, hooks: bool = True,
         ci: bool = False) -> list[str]:
    report: list[str] = []
    found = detect(repo)
    adr_dir = found["docs"].get("adr_dir") or repo.config["adr_dir"]
    values = {"PROJECT": repo.config["project"], "DATE": today(), "ADR_DIR": adr_dir,
              "PLANS_DIR": repo.config["plans_dir"], "VERSION": VERSION}

    def put(rel: str, content: str, mode: int | None = None):
        target = repo.root / rel
        if target.exists():
            report.append(f"kept     {rel} (already there)")
            return
        report.append(f"created  {rel}")
        if not dry_run:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            if mode:
                target.chmod(mode)

    def merge_block(rel: str, block: str):
        target = repo.root / rel
        if not target.exists():
            put(rel, block + "\n")
            return
        text = target.read_text(encoding="utf-8")
        if BLOCK_START in text:
            report.append(f"kept     {rel} (cockpit section already there)")
            return
        report.append(f"appended {rel} (cockpit section, between markers)")
        if not dry_run:
            target.write_text(text.rstrip("\n") + "\n\n" + block + "\n", encoding="utf-8")

    config = {k: v for k, v in DEFAULT_CONFIG.items() if k != "docs_exclude"}
    config.update({"project": repo.config["project"], "adr_dir": adr_dir,
                   "docs_exclude": [], "_docs_exclude": "extra paths to hide, added to the built-in list"})
    put(".cockpit/config.json", json.dumps(config, indent=2) + "\n")

    agents_block = render_template((TEMPLATES / "AGENTS.block.md").read_text(), values)
    merge_block("AGENTS.md", f"{BLOCK_START}\n{agents_block.strip()}\n{BLOCK_END}")
    claude = repo.root / "CLAUDE.md"
    if not claude.exists():
        put("CLAUDE.md", "@AGENTS.md\n")
    elif "AGENTS.md" not in claude.read_text(encoding="utf-8"):
        merge_block("CLAUDE.md", f"{BLOCK_START}\n@AGENTS.md\n{BLOCK_END}")
    else:
        report.append("kept     CLAUDE.md (already points at AGENTS.md)")

    for src, dest in (("CHANGELOG.md", "CHANGELOG.md"), ("MANUAL.md", "MANUAL.md"),
                      ("adr/README.md", f"{adr_dir}/README.md"),
                      ("plans/README.md", f"{repo.config['plans_dir']}/README.md")):
        put(dest, render_template((TEMPLATES / src).read_text(), values))
    put(f"{adr_dir}/0000-template.md", (TEMPLATES / "adr/0000-template.md").read_text())
    adr_root = repo.root / adr_dir
    if not (adr_root.is_dir() and any(re.match(r"\d{4}-(?!template)", p.name) for p in adr_root.iterdir())):
        put(f"{adr_dir}/0001-record-decisions-as-adrs.md",
            render_template((TEMPLATES / "adr/0001-record-decisions-as-adrs.md").read_text(), values))

    for t in ("plan.md", "context.md"):
        put(f".cockpit/templates/{t}", (TEMPLATES / "docs" / t).read_text())

    put(".cockpit/board.json", json.dumps({"_how": (
        "Action board. One row per thing a person must decide or do. Required: id, priority "
        "(P1-P5), task, what (refreshes memory cold, months later), why (what breaks if it never "
        "gets done), steps, dod (definition of done). status: open -> review (the person says "
        "they did it) -> done (an agent or owner checks and closes). Edit with `cockpit board`."),
        "items": [{
            "id": "cockpit-first-look", "priority": "P3", "status": "open", "created": today(),
            "owner": "Project owner", "deadline": None,
            "task": "Fill in the system map's plain-English lines",
            "what": "project-cockpit was added to this repo and guessed the services, jobs and logs "
                    "from the files it found. Each guessed row in .cockpit/system-map.json says "
                    f"'{DRAFT_MARK}' where a person has to write what the thing does.",
            "why": "A component nobody can describe cold is one nobody notices when it dies. The "
                   "dashboard shows these rows as drafts until they are filled.",
            "steps": ["Open .cockpit/system-map.json",
                      f"Replace every '{DRAFT_MARK}' line with one plain sentence",
                      "Add a probe and a log path where they exist",
                      "Run `cockpit system check`"],
            "dod": "`cockpit system check` reports no drafts and no errors."}]}, indent=2) + "\n")

    groups = [{"id": "services", "name": "Always running", "note": ""},
              {"id": "jobs", "name": "Jobs on a clock", "note": "the ones that die quietly"},
              {"id": "outside", "name": "Outside services", "note": "APIs and accounts this depends on"}]
    comps = found["components"]
    log_dirs = [lg for lg in found["logs"] if lg.endswith("/")]
    if found["logs"] and not any(c.get("logs") for c in comps):
        comps.append({"id": "app-logs", "name": "Log files", "group": "services",
                      "what": f"{DRAFT_MARK}: which program writes these logs.", "host": "local",
                      "code": "", "talksTo": [], "probe": {"type": "none"},
                      "logs": (log_dirs or found["logs"])[:10]})
    put(".cockpit/system-map.json", json.dumps({
        "_how": ("The only inventory of everything that runs. Anything that runs (service, job, "
                 "worker, cron, device) gets a row, or it is invisible when it dies. Required: id, "
                 "name, what (one plain sentence a newcomer understands), group. Optional: host, "
                 "code, talksTo (ids), probe {type: http|tcp|file|process|command|none}, logs "
                 "(paths), offSwitch, owner."),
        "updated": today(), "groups": groups, "components": comps}, indent=2) + "\n")
    put(".cockpit/status.json", json.dumps({"_how": (
        "Optional status overrides for the dashboard. Key: a repo path of a .md file, or a "
        "folder ending in '/'. Value: done | started | todo | blocked | cancel. An exact file "
        "beats the doc's own Status line; the doc's line beats a folder key. Usually leave "
        "this empty and keep each doc's Status line true.")}, indent=2) + "\n")

    if skills:
        for skill_dir in sorted((TEMPLATES / "skills").iterdir()):
            for f in sorted(skill_dir.rglob("*")):
                if f.is_file():
                    rel = f.relative_to(TEMPLATES / "skills").as_posix()
                    put(f".claude/skills/{rel}", render_template(f.read_text(), values))
    if hooks:
        put(".githooks/pre-commit", (TEMPLATES / "githooks/pre-commit").read_text(), 0o755)
        if repo.is_git() and not dry_run and not repo.git("config", "core.hooksPath").strip():
            repo.git("config", "core.hooksPath", ".githooks")
            report.append("set      git core.hooksPath = .githooks (this clone only)")
    if ci:
        put(".github/workflows/cockpit.yml", (TEMPLATES / "github/cockpit.yml").read_text())

    gi = repo.root / ".gitignore"
    want = [".cockpit/state/", ".cockpit/site/"]
    have = gi.read_text(encoding="utf-8").splitlines() if gi.exists() else []
    missing = [w for w in want if w not in have]
    if missing:
        report.append(f"appended .gitignore ({', '.join(missing)})")
        if not dry_run:
            gi.write_text(("\n".join(have) + "\n" if have else "") + "\n".join(missing) + "\n", encoding="utf-8")

    if not dry_run and write_index(repo):
        report.append("wrote    .cockpit/index.md (context map)")
    report.append("")
    report.append(f"detected languages: {', '.join(found['languages']) or 'none'}")
    report.append(f"detected components: {len(found['components'])}   logs: {len(found['logs'])}"
                  f"   CI workflows: {len(found['ci'])}   agent files: {', '.join(found['agents']) or 'none'}")
    return report


def vendor(repo: Repo) -> str:
    dest = repo.dir / "kit"
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    shutil.copy2(KIT_DIR / "cockpit.py", dest / "cockpit.py")
    shutil.copytree(TEMPLATES, dest / "templates")
    if (KIT_DIR / "README.md").exists():
        shutil.copy2(KIT_DIR / "README.md", dest / "README.md")
    return f"copied the kit to {dest.relative_to(repo.root)}; run it as: python3 .cockpit/kit/cockpit.py <command>"


# --------------------------------------------------------------------------
# context map (the agent's "load this first" file)
# --------------------------------------------------------------------------

def build_index(repo: Repo, docs: list[Doc] | None = None) -> str:
    docs = load_docs(repo) if docs is None else docs
    order = {"agents": 0, "readme": 1, "manual": 2, "context": 3, "plan": 4, "adr": 5,
             "changelog": 6, "doc": 7, "template": 8}
    lines = ["# Context map", "",
             f"Generated by project-cockpit for **{repo.config['project']}**. Do not edit by hand:"
             " `cockpit index` rewrites it (the pre-commit hook does too).",
             "", "Agents: load the files whose keywords match the task, and only those.", ""]
    groups: dict[str, list[Doc]] = {}
    for d in docs:
        if d.rel.startswith((".cockpit/", ".claude/")) or d.kind == "template":
            continue
        groups.setdefault(d.kind, []).append(d)
    for kind in sorted(groups, key=lambda k: (order.get(k, 9), k)):
        lines.append(f"## {KIND_LABEL.get(kind, kind.capitalize())}")
        lines.append("")
        for d in sorted(groups[kind], key=lambda x: x.rel):
            keys = d.load_for or d.title
            lines.append(f"- `{d.rel}` | {d.status} | {keys}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_index(repo: Repo) -> bool:
    text = build_index(repo)
    path = repo.dir / "index.md"
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return True


# --------------------------------------------------------------------------
# board
# --------------------------------------------------------------------------

def board_load(repo: Repo) -> dict:
    data = read_json(repo.board_file, {"items": []})
    data.setdefault("items", [])
    return data


def board_validate(items: list[dict]) -> list[str]:
    problems = []
    seen = set()
    for i, it in enumerate(items):
        who = it.get("id") or f"row {i + 1}"
        for f in BOARD_REQUIRED:
            v = it.get(f)
            if v is None or (isinstance(v, (str, list)) and not v):
                problems.append(f"{who}: '{f}' is empty")
        if it.get("priority") and it["priority"] not in PRIORITIES:
            problems.append(f"{who}: priority must be one of {', '.join(PRIORITIES)}")
        if it.get("status", "open") not in BOARD_STATES:
            problems.append(f"{who}: status must be one of {', '.join(BOARD_STATES)}")
        if it.get("id") in seen:
            problems.append(f"{who}: duplicate id")
        seen.add(it.get("id"))
    return problems


def board_move(repo: Repo, item_id: str, status: str, note: str = "", by: str = "") -> str:
    data = board_load(repo)
    allowed = {("open", "review"), ("review", "done"), ("review", "open"), ("open", "done"), ("done", "open")}
    for it in data["items"]:
        if it.get("id") == item_id:
            was = it.get("status", "open")
            if (was, status) not in allowed:
                return f"cannot go from {was} to {status}"
            it["status"] = status
            it.setdefault("history", []).append({"at": dt.datetime.now().isoformat(timespec="seconds"),
                                                 "from": was, "to": status, "note": note, "by": by})
            write_json(repo.board_file, data)
            return f"{item_id}: {was} -> {status}"
    return f"no item {item_id}"


def board_add(repo: Repo, args) -> str:
    data = board_load(repo)
    item = {"id": args.id or slug(args.task)[:40], "priority": args.priority, "status": "open",
            "created": today(), "owner": args.owner or "", "deadline": args.deadline,
            "task": args.task, "what": args.what or "", "why": args.why or "",
            "steps": args.step or [], "dod": args.dod or ""}
    problems = board_validate([item])
    if problems:
        return "not added:\n  " + "\n  ".join(problems)
    if any(i.get("id") == item["id"] for i in data["items"]):
        return f"not added: id {item['id']} already exists"
    data["items"].append(item)
    write_json(repo.board_file, data)
    return f"added {item['id']}"


# --------------------------------------------------------------------------
# system map + probes + logs
# --------------------------------------------------------------------------

def system_load(repo: Repo) -> dict:
    data = read_json(repo.system_file, {"groups": [], "components": []})
    data.setdefault("groups", [])
    data.setdefault("components", [])
    return data


def system_validate(data: dict) -> tuple[list[str], list[str]]:
    errors, drafts = [], []
    ids = {c.get("id") for c in data["components"]}
    groups = {g.get("id") for g in data["groups"]}
    seen = set()
    for i, c in enumerate(data["components"]):
        who = c.get("id") or f"component {i + 1}"
        for f in SYSTEM_REQUIRED:
            if not c.get(f):
                errors.append(f"{who}: '{f}' is empty")
        if c.get("id") in seen:
            errors.append(f"{who}: duplicate id")
        seen.add(c.get("id"))
        if groups and c.get("group") and c["group"] not in groups:
            errors.append(f"{who}: group '{c['group']}' is not in groups")
        for t in c.get("talksTo") or []:
            if t not in ids:
                errors.append(f"{who}: talksTo '{t}' is not a component id")
        ptype = (c.get("probe") or {}).get("type", "none")
        if ptype not in PROBE_TYPES:
            errors.append(f"{who}: probe type must be one of {', '.join(PROBE_TYPES)}")
        if DRAFT_MARK in (c.get("what") or ""):
            drafts.append(who)
    return errors, drafts


def _age_hours(path: Path) -> float:
    return (dt.datetime.now().timestamp() - path.stat().st_mtime) / 3600


def _parse_every(text: str) -> float:
    m = re.match(r"^\s*(\d+(?:\.\d+)?)\s*([mhd])\s*$", str(text or ""))
    if not m:
        return 0
    n, unit = float(m.group(1)), m.group(2)
    return n / 60 if unit == "m" else n * 24 if unit == "d" else n


def probe(repo: Repo, comp: dict) -> dict:
    """{state: up|down|unknown, detail}. Never raises, never waits long."""
    p = comp.get("probe") or {}
    kind = p.get("type", "none")
    timeout = float(p.get("timeout", 3))
    try:
        if kind == "http":
            req = urllib.request.Request(p["url"], headers={"User-Agent": "project-cockpit"})
            with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 (user-configured URL)
                ok = r.status < 400
                return {"state": "up" if ok else "down", "detail": f"HTTP {r.status}"}
        if kind == "tcp":
            with socket.create_connection((p.get("host", "127.0.0.1"), int(p["port"])), timeout=timeout):
                return {"state": "up", "detail": f"port {p['port']} open"}
        if kind == "file":
            path = repo.root / p["path"] if not os.path.isabs(p["path"]) else Path(p["path"])
            if not path.exists():
                return {"state": "down", "detail": f"{p['path']} missing"}
            limit = _parse_every(p.get("expectedEvery", ""))
            age = _age_hours(path)
            if limit and age > limit:
                return {"state": "down", "detail": f"last written {age:.1f}h ago (expected every {p['expectedEvery']})"}
            return {"state": "up", "detail": f"last written {age:.1f}h ago"}
        if kind == "process":
            out = subprocess.run(["pgrep", "-f", p["match"]], capture_output=True, text=True, timeout=timeout)
            return {"state": "up" if out.returncode == 0 else "down",
                    "detail": f"pgrep -f {p['match']}: {'found' if out.returncode == 0 else 'not running'}"}
        if kind == "command":
            out = subprocess.run(p["run"], shell=True, capture_output=True, text=True,  # noqa: S602 (user-configured)
                                 timeout=max(timeout, 5), cwd=repo.root)
            return {"state": "up" if out.returncode == 0 else "down",
                    "detail": (out.stdout or out.stderr).strip().splitlines()[-1][:120] if (out.stdout or out.stderr).strip() else f"exit {out.returncode}"}
    except Exception as exc:  # noqa: BLE001
        return {"state": "down", "detail": f"{type(exc).__name__}: {exc}"[:160]}
    return {"state": "unknown", "detail": "no probe"}


def probe_all(repo: Repo) -> dict:
    data = system_load(repo)
    results = {"at": dt.datetime.now().isoformat(timespec="seconds"), "components": {}}
    for c in data["components"]:
        results["components"][c["id"]] = probe(repo, c)
    write_json(repo.state_dir / "probes.json", results)
    return results


SECRET_RX = re.compile(
    r"(?i)((?:password|passwd|pwd|secret|token|api[_-]?key|authorization|bearer)\s*[=:]\s*)(\"?)[^\s\"',;]+")


def redact(line: str) -> str:
    line = SECRET_RX.sub(lambda m: m.group(1) + m.group(2) + "[redacted]", line)
    return re.sub(r"\b(?:sk|ghp|gho|xox[abp])[-_][A-Za-z0-9_-]{10,}", "[redacted]", line)


def log_files(repo: Repo, comp: dict | None = None) -> list[tuple[str, str, Path]]:
    """(component id, display path, file) for every log the map points at.
    A path ending in '/' means every *.log / *.txt file in that folder."""
    data = system_load(repo)
    out = []
    for c in ([comp] if comp else data["components"]):
        for lp in c.get("logs") or []:
            base = repo.root / lp if not os.path.isabs(lp) else Path(lp)
            if lp.endswith("/") and base.is_dir():
                for f in sorted(base.iterdir()):
                    if f.is_file() and f.suffix in (".log", ".txt", ".out", ".err", ""):
                        out.append((c["id"], f"{lp}{f.name}", f))
            elif base.is_file():
                out.append((c["id"], lp, base))
    return out


def tail(path: Path, n: int) -> list[str]:
    try:
        with path.open("rb") as fh:
            fh.seek(0, 2)
            size = fh.tell()
            fh.seek(max(0, size - 256 * 1024))
            data = fh.read().decode("utf-8", errors="replace")
    except OSError as exc:
        return [f"(cannot read: {exc})"]
    return [redact(x) for x in data.splitlines()[-n:]]


# --------------------------------------------------------------------------
# markdown -> html (uses `markdown` when installed, else a small renderer)
# --------------------------------------------------------------------------

def _inline(text: str) -> str:
    codes: list[str] = []

    def keep(m):
        codes.append(f"<code>{html.escape(m.group(1))}</code>")
        return f"\x00{len(codes) - 1}\x00"
    text = re.sub(r"`([^`]+)`", keep, text)
    text = html.escape(text, quote=False)
    text = re.sub(r"!\[([^\]]*)\]\(([^)\s]+)\)", r'<img alt="\1" src="\2">', text)
    text = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", r'<a href="\2">\1</a>', text)
    text = re.sub(r"(?<![\"=>])\b(https?://[^\s<]+)", r'<a href="\1">\1</a>', text)
    text = re.sub(r"\*\*(.+?)\*\*|__(.+?)__", lambda m: f"<strong>{m.group(1) or m.group(2)}</strong>", text)
    text = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<em>\1</em>", text)
    text = re.sub(r"~~(.+?)~~", r"<del>\1</del>", text)
    return re.sub(r"\x00(\d+)\x00", lambda m: codes[int(m.group(1))], text)


def _heading_id(text: str, used: dict) -> str:
    base = re.sub(r"[^\w\- ]", "", re.sub(r"<[^>]+>", "", text)).strip().lower().replace(" ", "-") or "section"
    n = used.get(base, 0)
    used[base] = n + 1
    return base if n == 0 else f"{base}_{n}"


def mini_markdown(md: str) -> str:
    lines = md.split("\n")
    out: list[str] = []
    used: dict = {}
    i = 0
    para: list[str] = []

    def flush():
        if para:
            out.append("<p>" + _inline(" ".join(s.strip() for s in para)) + "</p>")
            para.clear()

    while i < len(lines):
        line = lines[i]
        fence = re.match(r"^\s*(```|~~~)\s*([\w+-]*)", line)
        if fence:
            flush()
            lang = fence.group(2)
            body = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith(fence.group(1)):
                body.append(lines[i])
                i += 1
            out.append(f'<pre><code class="language-{lang}">' + html.escape("\n".join(body)) + "</code></pre>")
            i += 1
            continue
        h = re.match(r"^(#{1,6})\s+(.+?)\s*#*\s*$", line)
        if h:
            flush()
            lvl, txt = len(h.group(1)), _inline(h.group(2))
            out.append(f'<h{lvl} id="{_heading_id(txt, used)}">{txt}</h{lvl}>')
            i += 1
            continue
        if re.match(r"^\s*([-*_])(\s*\1){2,}\s*$", line):
            flush()
            out.append("<hr>")
            i += 1
            continue
        if line.lstrip().startswith(">"):
            flush()
            body = []
            while i < len(lines) and lines[i].lstrip().startswith(">"):
                body.append(re.sub(r"^\s*>\s?", "", lines[i]))
                i += 1
            out.append("<blockquote>" + mini_markdown("\n".join(body)) + "</blockquote>")
            continue
        if "|" in line and i + 1 < len(lines) and re.match(r"^\s*\|?\s*:?-{2,}", lines[i + 1]):
            flush()

            def cells(s):
                s = s.strip()
                s = s[1:] if s.startswith("|") else s
                s = s[:-1] if s.endswith("|") else s
                return [c.strip() for c in re.split(r"(?<!\\)\|", s)]
            head = cells(line)
            i += 2
            rows = []
            while i < len(lines) and "|" in lines[i] and lines[i].strip():
                rows.append(cells(lines[i]))
                i += 1
            out.append("<table><thead><tr>" + "".join(f"<th>{_inline(c)}</th>" for c in head)
                       + "</tr></thead><tbody>"
                       + "".join("<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in r) + "</tr>" for r in rows)
                       + "</tbody></table>")
            continue
        lm = re.match(r"^(\s*)([-*+]|\d+[.)])\s+", line)
        if lm:
            flush()
            block = []
            while i < len(lines) and (re.match(r"^(\s*)([-*+]|\d+[.)])\s+", lines[i])
                                      or (lines[i].startswith("  ") and lines[i].strip())):
                block.append(lines[i])
                i += 1
            out.append(_list_html(block))
            continue
        if not line.strip():
            flush()
            i += 1
            continue
        para.append(line)
        i += 1
    flush()
    return "\n".join(out)


def _list_html(block: list[str]) -> str:
    first = re.match(r"^(\s*)([-*+]|\d+[.)])\s+", block[0])
    indent = len(first.group(1))
    tag = "ol" if first.group(2)[0].isdigit() else "ul"
    items: list[list[str]] = []
    for line in block:
        m = re.match(r"^(\s*)([-*+]|\d+[.)])\s+(.*)$", line)
        if m and len(m.group(1)) <= indent:
            items.append([m.group(3)])
        elif items:
            items[-1].append(line[indent + 2:] if line.startswith(" " * (indent + 2)) else line.strip())
    parts = []
    for it in items:
        head, rest = it[0], it[1:]
        box = re.match(r"^\[([ xX])\]\s+(.*)$", head)
        if box:
            head = ("✅ " if box.group(1).lower() == "x" else "⬜ ") + box.group(2)
        j = next((k for k, r in enumerate(rest) if re.match(r"^\s*([-*+]|\d+[.)])\s+", r)), len(rest))
        cont, sub = rest[:j], rest[j:]
        body = _inline(" ".join([head] + [c.strip() for c in cont if c.strip()]))
        nested = _list_html(sub) if sub else ""
        parts.append(f"<li>{body}{nested}</li>")
    return f"<{tag}>" + "".join(parts) + f"</{tag}>"


def md_to_html(md: str, renderer: str = "auto") -> str:
    """renderer: "auto" uses the `markdown` package when installed, "builtin"
    always uses the small renderer above (same output on every machine)."""
    if renderer != "builtin":
        try:
            import markdown  # type: ignore
            # The package wants 4-space nesting; most people write 2.
            md = re.sub(r"^((?:  )+)(?=([-*+]|\d+[.)])\s)", lambda m: m.group(1) * 2, md, flags=re.M)
            out = markdown.markdown(md, extensions=["tables", "fenced_code", "sane_lists", "toc"])
            out = re.sub(r"<li>(<p>)?\[[xX]\]\s", r"<li>\1✅ ", out)
            return re.sub(r"<li>(<p>)?\[ \]\s", r"<li>\1⬜ ", out)
        except ImportError:
            pass
    return mini_markdown(md)


# --------------------------------------------------------------------------
# site build
# --------------------------------------------------------------------------

CSS = """
:root{--bg:#f7f7f5;--panel:#fff;--ink:#1d1d1f;--muted:#6b6b70;--line:#e3e3e0;--accent:#2f6fde;
--ok:#1f8a4c;--bad:#c4372f;--warn:#b7791f;--code:#f0f0ec}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#151517;--panel:#1e1e21;--ink:#ececee;
--muted:#9a9aa2;--line:#2e2e33;--accent:#7aa7ff;--ok:#4cc38a;--bad:#ff7b72;--warn:#e3b341;--code:#26262a}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);
font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
a{color:var(--accent);text-decoration:none}a:hover{text-decoration:underline}
.wrap{display:flex;min-height:100vh}nav{width:270px;flex:none;border-right:1px solid var(--line);
padding:16px;background:var(--panel);position:sticky;top:0;height:100vh;overflow:auto}
nav h1{font-size:17px;margin:0 0 10px}nav .sec{font-size:12px;text-transform:uppercase;color:var(--muted);
margin:14px 0 4px;letter-spacing:.04em}nav a{display:block;padding:2px 0;font-size:14px;overflow:hidden;
text-overflow:ellipsis;white-space:nowrap}nav a.on{font-weight:600}
nav input{width:100%;padding:6px 8px;border:1px solid var(--line);border-radius:6px;background:var(--bg);color:var(--ink)}
main{flex:1;min-width:0;padding:24px 32px;max-width:1100px}
.meta{color:var(--muted);font-size:13px;margin:-6px 0 18px}
.badge{display:inline-block;padding:1px 8px;border-radius:10px;font-size:12px;border:1px solid var(--line);
background:var(--panel);margin-right:4px;white-space:nowrap}
.up{color:var(--ok)}.down{color:var(--bad)}.unknown{color:var(--muted)}.draft{color:var(--warn)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:12px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:12px 14px}
.card h3{margin:0 0 6px;font-size:15px}.card p{margin:4px 0}.num{font-size:28px;font-weight:700}
.missing{color:var(--bad);font-weight:600}
table{border-collapse:collapse;width:100%;margin:10px 0;font-size:14px}
th,td{border:1px solid var(--line);padding:6px 8px;text-align:left;vertical-align:top}th{background:var(--code)}
pre{background:var(--code);padding:10px 12px;border-radius:8px;overflow:auto;font-size:13px}
code{background:var(--code);padding:1px 4px;border-radius:4px;font-size:.92em}pre code{padding:0;background:none}
blockquote{border-left:3px solid var(--line);margin:8px 0;padding:2px 12px;color:var(--muted)}
.log{white-space:pre-wrap;font:12px/1.45 ui-monospace,Menlo,monospace;max-height:420px;overflow:auto}
.cols{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}
@media (max-width:820px){.wrap{display:block}nav{width:auto;height:auto;position:static;border-right:0;
border-bottom:1px solid var(--line)}main{padding:16px}.cols{grid-template-columns:1fr}}
"""

SEARCH_JS = """
function cockpitFilter(q){q=q.toLowerCase();document.querySelectorAll('[data-find]').forEach(function(el){
el.style.display=el.getAttribute('data-find').indexOf(q)>=0?'':'none'})}
"""


class Site:
    def __init__(self, repo: Repo, out: Path, probe_now: bool = False):
        self.repo = repo
        self.out = out
        self.docs = load_docs(repo)
        self.by_rel = {d.rel: d for d in self.docs}
        self.board = board_load(repo)
        self.system = system_load(repo)
        if probe_now:
            self.probes = probe_all(repo)
        else:
            self.probes = read_json(repo.dir / "state" / "probes.json", {"components": {}})
        self.title = repo.config["project"]

    # -- helpers
    def doc_href(self, rel: str) -> str:
        return "docs/" + rel[:-3] + ".html"

    def rel_prefix(self, page: str) -> str:
        return "../" * page.count("/")

    def nav(self, page: str) -> str:
        pre = self.rel_prefix(page)
        e = html.escape
        top = [("index.html", "Overview"), ("board.html", "Action board"), ("system.html", "System"),
               ("logs.html", "Logs"), ("decisions.html", "Decisions"), ("plans.html", "Plans and context"),
               ("docs.html", "All docs")]
        parts = [f"<h1>{e(self.title)}</h1>",
                 '<input placeholder="Filter docs" oninput="cockpitFilter(this.value)">']
        parts.append('<div class="sec">Cockpit</div>')
        for href, label in top:
            parts.append(f'<a class="{"on" if page == href else ""}" href="{pre}{href}">{label}</a>')
        folders: dict[str, list[Doc]] = {}
        for d in self.docs:
            folders.setdefault(d.folder, []).append(d)
        for folder in sorted(folders, key=lambda f: (f != "(root)", f)):
            parts.append(f'<div class="sec">{e(folder)}</div>')
            for d in sorted(folders[folder], key=lambda x: x.rel):
                href = self.doc_href(d.rel)
                find = e((d.title + " " + d.rel).lower(), quote=True)
                parts.append(f'<a data-find="{find}" class="{"on" if page == href else ""}" '
                             f'href="{pre}{href}" title="{e(d.rel)}">{STATUS_ICON[d.status]} {e(d.title)}</a>')
        return "\n".join(parts)

    def page(self, page: str, title: str, body: str) -> None:
        path = self.out / page
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)} | {html.escape(self.title)}</title><style>{CSS}</style></head>
<body><div class="wrap"><nav>{self.nav(page)}</nav><main>{body}
<p class="meta" style="margin-top:40px">Built {dt.datetime.now().strftime('%Y-%m-%d %H:%M')} by project-cockpit {VERSION}</p>
</main></div><script>{SEARCH_JS}</script></body></html>""", encoding="utf-8")

    def link_doc(self, d: Doc, page: str) -> str:
        return (f'<a href="{self.rel_prefix(page)}{self.doc_href(d.rel)}">{STATUS_ICON[d.status]} '
                f'{html.escape(d.title)}</a>')

    def rewrite_links(self, body_html: str, d: Doc, page: str) -> str:
        """Relative links to other .md files point at their built page."""
        base = Path(d.rel).parent

        def fix(m):
            href = html.unescape(m.group(1))
            if re.match(r"^[a-z]+:|^#|^/", href):
                return m.group(0)
            target, _, anchor = href.partition("#")
            try:
                rel = os.path.normpath(str(base / target)).replace(os.sep, "/")
            except ValueError:
                return m.group(0)
            if rel in self.by_rel:
                new = os.path.relpath(self.doc_href(rel), Path(page).parent.as_posix() or ".").replace(os.sep, "/")
                return f'href="{html.escape(new)}{("#" + anchor) if anchor else ""}"'
            return m.group(0)
        return re.sub(r'href="([^"]+)"', fix, body_html)

    # -- pages
    def build(self) -> int:
        if self.out.exists():
            shutil.rmtree(self.out)
        self.out.mkdir(parents=True)
        for d in self.docs:
            page = self.doc_href(d.rel)
            body = md_to_html(d.body, self.repo.config.get("renderer", "auto"))
            body = self.rewrite_links(body, d, page)
            meta = (f'<span class="badge">{STATUS_ICON[d.status]} {d.status}</span>'
                    f'<span class="badge">{d.kind}</span>'
                    f'<span class="badge">updated {d.updated}</span>'
                    f'<span class="badge"><code>{html.escape(d.rel)}</code></span>')
            if d.status_from != "doc" and d.own_status and d.own_status != d.status:
                meta += f'<span class="badge missing">drift: the doc says {d.own_status}</span>'
            self.page(page, d.title, f'<div class="meta">{meta}</div>{body}')
        self.overview()
        self.board_page()
        self.system_page()
        self.logs_page()
        self.list_page("decisions.html", "Decisions", [d for d in self.docs if d.kind == "adr"],
                       "Architecture decision records. Read these before changing a design.")
        self.list_page("plans.html", "Plans and context",
                       [d for d in self.docs if d.kind in ("plan", "context")],
                       "Plans are the human checklist; context files are the dense state an agent resumes from.")
        self.list_page("docs.html", "All docs", self.docs, "Every markdown file in the repo.")
        write_json(self.out / "cockpit.json", self.summary())
        return len(self.docs)

    def summary(self) -> dict:
        items = self.board["items"]
        comps = self.system["components"]
        probes = self.probes.get("components", {})
        return {
            "project": self.title, "built": dt.datetime.now().isoformat(timespec="seconds"),
            "docs": {s: sum(1 for d in self.docs if d.status == s) for s in STATUSES},
            "drift": [d.rel for d in drift(self.docs)],
            "board": {s: sum(1 for i in items if i.get("status", "open") == s) for s in BOARD_STATES},
            "board_problems": board_validate(items),
            "system": {s: sum(1 for c in comps if probes.get(c["id"], {}).get("state", "unknown") == s)
                       for s in ("up", "down", "unknown")},
            "system_drafts": system_validate(self.system)[1],
        }

    def overview(self) -> None:
        s = self.summary()
        e = html.escape
        cards = [
            ("Docs", sum(s["docs"].values()), " ".join(f"{STATUS_ICON[k]} {v}" for k, v in s["docs"].items() if v)),
            ("Open actions", s["board"]["open"], f"{s['board']['review']} waiting for review"),
            ("System", f"{s['system']['up']}/{len(self.system['components'])}",
             f"{s['system']['down']} down, {s['system']['unknown']} not probed"),
            ("Decisions", sum(1 for d in self.docs if d.kind == "adr"), "architecture decision records"),
        ]
        body = [f"<h1>{e(self.title)}</h1>", '<div class="grid">']
        for label, num, note in cards:
            body.append(f'<div class="card"><h3>{label}</h3><div class="num">{num}</div><p class="meta">{note}</p></div>')
        body.append("</div>")
        warn = []
        if s["drift"]:
            warn.append(f"{len(s['drift'])} doc(s) show a different status than they say inside: "
                        + ", ".join(f"<code>{e(r)}</code>" for r in s["drift"]))
        if s["board_problems"]:
            warn.append(f"{len(s['board_problems'])} board problem(s): " + e("; ".join(s["board_problems"][:5])))
        if s["system_drafts"]:
            warn.append(f"{len(s['system_drafts'])} system map row(s) still say {DRAFT_MARK}")
        if warn:
            body.append("<h2>Needs attention</h2><ul>" + "".join(f'<li class="draft">{w}</li>' for w in warn) + "</ul>")
        open_items = sorted((i for i in self.board["items"] if i.get("status", "open") != "done"),
                            key=lambda i: (i.get("priority", "P9"), i.get("deadline") or "9999"))[:8]
        if open_items:
            body.append('<h2>Next actions</h2><table><tr><th>Priority</th><th>Task</th><th>Owner</th><th>Status</th></tr>')
            for i in open_items:
                body.append(f"<tr><td>{e(i.get('priority', ''))}</td><td>{e(i.get('task', ''))}</td>"
                            f"<td>{e(i.get('owner', ''))}</td><td>{e(i.get('status', 'open'))}</td></tr>")
            body.append("</table>")
        start = [d for d in self.docs if d.kind in ("readme", "manual", "agents")]
        if start:
            body.append("<h2>Start here</h2><ul>" + "".join(f"<li>{self.link_doc(d, 'index.html')}</li>" for d in start) + "</ul>")
        recent = sorted(self.docs, key=lambda d: d.updated, reverse=True)[:10]
        body.append("<h2>Recently changed</h2><ul>" + "".join(
            f'<li>{self.link_doc(d, "index.html")} <span class="meta">{d.updated}</span></li>' for d in recent) + "</ul>")
        cl = next((d for d in self.docs if d.kind == "changelog"), None)
        if cl:
            entries = [ln for ln in cl.body.splitlines() if ln.startswith(("- ", "## "))][:12]
            body.append(f'<h2>Changelog</h2><div class="card">{md_to_html(chr(10).join(entries))}'
                        f'<p>{self.link_doc(cl, "index.html")}</p></div>')
        self.page("index.html", "Overview", "\n".join(body))

    def board_page(self) -> None:
        e = html.escape
        items = self.board["items"]
        body = ["<h1>Action board</h1>",
                '<p class="meta">Things a person must decide or do. Open, then review (they say it is done), '
                "then done (someone checked). Edit with <code>cockpit board</code>.</p>"]
        problems = board_validate(items)
        if problems:
            body.append('<p class="missing">' + e("; ".join(problems)) + "</p>")
        body.append('<div class="cols">')
        for state in BOARD_STATES:
            col = sorted((i for i in items if i.get("status", "open") == state),
                         key=lambda i: (i.get("priority", "P9"), i.get("deadline") or "9999"))
            if state == "done":
                col = col[-15:]
            body.append(f"<div><h2>{state.capitalize()} ({len(col)})</h2>")
            for it in col:
                def field(name, label):
                    v = it.get(name)
                    if isinstance(v, list):
                        v = "<ol>" + "".join(f"<li>{_inline(str(x))}</li>" for x in v) + "</ol>" if v else ""
                    else:
                        v = _inline(str(v)) if v else ""
                    return f"<p><b>{label}:</b> {v}</p>" if v else f'<p class="missing">{label}: missing</p>'
                dl = f' · due {e(str(it["deadline"]))}' if it.get("deadline") else ""
                body.append(f'<div class="card"><h3>{e(it.get("priority", "?"))} · {e(it.get("task", "(no task)"))}</h3>'
                            f'<p class="meta">{e(it.get("owner", ""))}{dl} · <code>{e(str(it.get("id", "")))}</code></p>'
                            + field("what", "What") + field("why", "Why") + field("steps", "Steps") + field("dod", "Done when")
                            + "</div>")
            body.append("</div>")
        body.append("</div>")
        self.page("board.html", "Action board", "\n".join(body))

    def system_page(self) -> None:
        e = html.escape
        probes = self.probes.get("components", {})
        errors, drafts = system_validate(self.system)
        body = ["<h1>System</h1>",
                f'<p class="meta">Everything that runs. Probes as of {e(self.probes.get("at", "never"))} '
                "(<code>cockpit system probe</code>, or <code>cockpit build --probe</code>).</p>"]
        if errors:
            body.append('<p class="missing">' + e("; ".join(errors)) + "</p>")
        names = {c["id"]: c.get("name", c["id"]) for c in self.system["components"]}
        groups = self.system["groups"] or [{"id": None, "name": "Components"}]
        known = {g.get("id") for g in groups}
        for g in groups + [{"id": "__other", "name": "Other"}]:
            comps = [c for c in self.system["components"]
                     if c.get("group") == g["id"] or (g["id"] == "__other" and c.get("group") not in known)]
            if not comps:
                continue
            body.append(f"<h2>{e(g['name'])}</h2>" + (f'<p class="meta">{e(g.get("note", ""))}</p>' if g.get("note") else ""))
            body.append('<div class="grid">')
            for c in comps:
                pr = probes.get(c["id"], {"state": "unknown", "detail": "not probed yet"})
                if (c.get("probe") or {}).get("type", "none") == "none":
                    pr = {"state": "unknown", "detail": "no probe set"}
                what = e(c.get("what", ""))
                cls = "draft" if c["id"] in drafts else ""
                extra = []
                if c.get("host"):
                    extra.append(f"<b>Runs on:</b> {e(c['host'])}")
                if c.get("code"):
                    extra.append(f"<b>Code:</b> <code>{e(c['code'])}</code>")
                if c.get("talksTo"):
                    extra.append("<b>Talks to:</b> " + ", ".join(e(names.get(t, t)) for t in c["talksTo"]))
                if c.get("logs"):
                    extra.append(f'<b>Logs:</b> <a href="logs.html#{e(c["id"])}">{len(c["logs"])} path(s)</a>')
                if c.get("offSwitch"):
                    extra.append(f"<b>Off switch:</b> <code>{e(c['offSwitch'])}</code>")
                if c.get("owner"):
                    extra.append(f"<b>Owner:</b> {e(c['owner'])}")
                body.append(f'<div class="card"><h3><span class="{pr["state"]}">●</span> {e(c.get("name", c["id"]))}</h3>'
                            f'<p class="{cls}">{what}</p>' + "".join(f"<p>{x}</p>" for x in extra)
                            + f'<p class="meta {pr["state"]}">{e(pr["state"])}: {e(pr.get("detail", ""))}</p></div>')
            body.append("</div>")
        if not self.system["components"]:
            body.append("<p>No components yet. Add rows to <code>.cockpit/system-map.json</code>.</p>")
        self.page("system.html", "System", "\n".join(body))

    def logs_page(self) -> None:
        e = html.escape
        body = ["<h1>Logs</h1>"]
        if not self.repo.config.get("logs_in_site", True):
            body.append("<p>Logs are switched off for the site (<code>logs_in_site</code> in .cockpit/config.json). "
                        "Use <code>cockpit logs</code> in a terminal.</p>")
        else:
            files = log_files(self.repo)
            n = int(self.repo.config.get("log_tail_lines", 200))
            body.append(f'<p class="meta">Last {n} lines of each log the system map points at, newest last. '
                        "Lines that look like passwords, tokens or keys are redacted. "
                        'Filter: <input oninput="cockpitLog(this.value)"></p>')
            if not files:
                body.append("<p>No log files found. Add <code>logs</code> paths to components in the system map.</p>")
            for cid, disp, f in files:
                lines = tail(f, n)
                body.append(f'<h2 id="{e(cid)}">{e(disp)}</h2><div class="card log">'
                            + "\n".join(f'<div data-log="{e(x.lower(), quote=True)}">{e(x)}</div>' for x in lines)
                            + "</div>")
            body.append("<script>function cockpitLog(q){q=q.toLowerCase();document.querySelectorAll('[data-log]')"
                        ".forEach(function(el){el.style.display=el.getAttribute('data-log').indexOf(q)>=0?'':'none'})}</script>")
        self.page("logs.html", "Logs", "\n".join(body))

    def list_page(self, page: str, title: str, docs: list[Doc], intro: str) -> None:
        e = html.escape
        body = [f"<h1>{title}</h1>", f'<p class="meta">{intro}</p>']
        if not docs:
            body.append("<p>None yet.</p>")
        else:
            body.append("<table><tr><th>Status</th><th>Doc</th><th>Kind</th><th>Owner</th><th>Updated</th></tr>")
            for d in sorted(docs, key=lambda x: x.rel):
                body.append(f"<tr><td>{STATUS_ICON[d.status]} {d.status}</td><td>{self.link_doc(d, page)}"
                            f'<br><span class="meta">{e(d.rel)}</span></td><td>{d.kind}</td>'
                            f"<td>{e(d.owner)}</td><td>{d.updated}</td></tr>")
            body.append("</table>")
        self.page(page, title, "\n".join(body))


# --------------------------------------------------------------------------
# new docs from templates + lint
# --------------------------------------------------------------------------

def template_text(repo: Repo, name: str) -> str:
    local = repo.dir / "templates" / name
    return local.read_text() if local.exists() else (TEMPLATES / "docs" / name).read_text()


def new_adr(repo: Repo, title: str) -> Path:
    d = repo.root / repo.config["adr_dir"]
    d.mkdir(parents=True, exist_ok=True)
    nums = [int(m.group(1)) for p in d.iterdir() if (m := re.match(r"(\d{4})-", p.name))]
    n = max(nums, default=0) + 1
    path = d / f"{n:04d}-{slug(title)}.md"
    tpl = d / "0000-template.md"
    text = tpl.read_text() if tpl.exists() else (TEMPLATES / "adr/0000-template.md").read_text()
    text = text.replace("ADR-0000", f"ADR-{n:04d}").replace("{{TITLE}}", title).replace("{{DATE}}", today())
    text = re.sub(r"^# ADR-\d{4}: .*$", f"# ADR-{n:04d}: {title}", text, count=1, flags=re.M)
    path.write_text(text, encoding="utf-8")
    return path


def new_doc(repo: Repo, kind: str, topic: str) -> Path:
    d = repo.root / repo.config["plans_dir"]
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{slug(topic)}-{kind}.md"
    if path.exists():
        raise SystemExit(f"{path.relative_to(repo.root)} already exists")
    text = template_text(repo, f"{kind}.md")
    text = text.replace("{{TOPIC}}", topic).replace("{{DATE}}", today()).replace("{{SLUG}}", slug(topic))
    path.write_text(text, encoding="utf-8")
    return path


LINT_SECTIONS = {
    "plan": ["Goal", "What today requires", "Action checklist", "Detail", "Handover prompt"],
    "context": ["State now", "Facts and decisions", "Open questions and risks", "Key resources",
                "Next actions", "Handover prompt"],
}


def lint(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    fm, body = frontmatter(text)
    kind = fm.get("doc-type") or ("context" if path.name.endswith("-context.md") else
                                  "plan" if path.name.endswith("-plan.md") else "")
    if kind not in LINT_SECTIONS:
        return [f"{path.name}: not a plan or context file (name it *-plan.md or *-context.md, or set doc-type)"]
    problems = []
    heads = [h.strip().lower() for h in re.findall(r"^#{2,3}\s+(.+)$", body, re.M)]
    for sec in LINT_SECTIONS[kind]:
        if not any(h.startswith(sec.lower()) for h in heads):
            problems.append(f"missing section: ## {sec}")
    if not re.search(r"^#\s+\S", body, re.M):
        problems.append("missing the H1 title")
    if own_status(body)[0] is None:
        problems.append("missing a clear **Status:** line near the top (done, in progress, todo, blocked, cancelled)")
    if not fm.get("load-for") and "**Load for:**" not in body:
        problems.append("missing load-for keywords (frontmatter `load-for:` or a **Load for:** line)")
    m = re.search(r"^##\s+Handover prompt\s*$(.*)", body, re.M | re.I | re.S)
    if m and "```" not in m.group(1):
        problems.append("the Handover prompt must be a fenced code block")
    if kind == "plan":
        m = re.search(r"^##\s+What today requires\s*$(.*?)^##\s", body, re.M | re.I | re.S)
        if m and re.search(r"^\s*[-*]\s+\[[xX]\]", m.group(1), re.M):
            problems.append("'What today requires' lists done items; keep the top forward-looking")
    if "—" in body:
        problems.append("contains an em dash; use a comma, a colon or a new sentence")
    return problems


# --------------------------------------------------------------------------
# check (everything, CI friendly)
# --------------------------------------------------------------------------

def check(repo: Repo, strict: bool = False) -> tuple[list[str], list[str]]:
    errors, warnings = [], []
    for k, v in status_overrides(repo).items():
        if v not in STATUSES:
            errors.append(f"status.json: '{k}' has unknown status '{v}' (use {', '.join(STATUSES)})")
    docs = load_docs(repo)
    for d in drift(docs):
        errors.append(f"status drift: {d.rel} shows '{d.status}' ({d.status_from}) but says '{d.own_status}' inside")
    errors += [f"board: {p}" for p in board_validate(board_load(repo)["items"])]
    sys_errors, drafts = system_validate(system_load(repo))
    errors += [f"system: {p}" for p in sys_errors]
    if drafts:
        warnings.append(f"system: {len(drafts)} row(s) still say {DRAFT_MARK}: {', '.join(drafts)}")
    for d in docs:
        if d.kind == "adr" and not d.own_line and not d.rel.endswith("0000-template.md"):
            warnings.append(f"adr: {d.rel} has no Status line")
        if d.kind in ("plan", "context"):
            for p in lint(repo.root / d.rel):
                warnings.append(f"lint {d.rel}: {p}")
    idx = repo.dir / "index.md"
    if idx.exists() and idx.read_text(encoding="utf-8") != build_index(repo, docs):
        warnings.append("index: .cockpit/index.md is stale; run `cockpit index`")
    if strict:
        errors, warnings = errors + warnings, []
    return errors, warnings


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def _print_status(repo: Repo, as_json: bool) -> int:
    docs = load_docs(repo)
    rows = drift(docs)
    if as_json:
        print(json.dumps({"docs": [{"doc": d.rel, "status": d.status, "from": d.status_from,
                                    "doc_says": d.own_status} for d in docs],
                          "drift": [d.rel for d in rows]}, indent=1))
        return 1 if rows else 0
    for s in STATUSES:
        group = [d for d in docs if d.status == s]
        if group:
            print(f"{STATUS_ICON[s]} {s} ({len(group)})")
            for d in group:
                print(f"    {d.rel}   [{d.status_from}]")
    if rows:
        print(f"\nDRIFT: {len(rows)} doc(s) where the label and the doc disagree")
        for d in rows:
            print(f"  {d.rel}: label {d.status} ({d.status_from}), doc says {d.own_status}: {d.own_line[:100]}")
        print("Fix the wrong side: the row in .cockpit/status.json, or the doc's Status line.")
        return 1
    print("\nno drift")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="cockpit", description=__doc__.split("\n\n")[0])
    p.add_argument("--root", default=".", help="the repository to work on (default: current folder)")
    p.add_argument("--version", action="version", version=VERSION)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("init", help="detect what the repo has and scaffold what is missing")
    s.add_argument("--dry-run", action="store_true")
    s.add_argument("--no-skills", action="store_true", help="do not add .claude/skills")
    s.add_argument("--no-hooks", action="store_true", help="do not add the git pre-commit hook")
    s.add_argument("--ci", action="store_true", help="add a GitHub Actions workflow that runs check + build")
    sub.add_parser("detect", help="print what the repo has")
    sub.add_parser("index", help="rewrite .cockpit/index.md")
    s = sub.add_parser("status", help="doc statuses and drift")
    s.add_argument("--json", action="store_true")
    s = sub.add_parser("build", help="build the static dashboard")
    s.add_argument("--out")
    s.add_argument("--probe", action="store_true", help="probe every component first")
    s = sub.add_parser("serve", help="build, then serve the dashboard")
    s.add_argument("--port", type=int, default=8765)
    s.add_argument("--probe", action="store_true")
    s.add_argument("--rebuild-every", type=int, default=0, help="seconds; 0 = build once")
    s = sub.add_parser("check", help="all validators; exit 1 on errors")
    s.add_argument("--strict", action="store_true", help="warnings count as errors")
    sub.add_parser("vendor", help="copy this kit into the repo")

    b = sub.add_parser("board", help="the action board")
    bs = b.add_subparsers(dest="bcmd", required=True)
    bl = bs.add_parser("list")
    bl.add_argument("--all", action="store_true")
    ba = bs.add_parser("add")
    ba.add_argument("task")
    ba.add_argument("--priority", default="P3", choices=PRIORITIES)
    ba.add_argument("--what")
    ba.add_argument("--why")
    ba.add_argument("--step", action="append", help="repeat for each step")
    ba.add_argument("--dod")
    ba.add_argument("--owner")
    ba.add_argument("--deadline")
    ba.add_argument("--id")
    for name in ("did", "done", "back"):
        m = bs.add_parser(name)
        m.add_argument("id")
        m.add_argument("note", nargs="?", default="")
    bs.add_parser("check")

    sy = sub.add_parser("system", help="the system map")
    sys_sub = sy.add_subparsers(dest="scmd", required=True)
    sys_sub.add_parser("check")
    sys_sub.add_parser("probe")
    lg = sub.add_parser("logs", help="tail logs from the system map")
    lg.add_argument("id", nargs="?")
    lg.add_argument("-n", type=int, default=40)
    lg.add_argument("--grep")
    a = sub.add_parser("adr", help="decision records")
    a.add_argument("action", choices=["new"])
    a.add_argument("title")
    for kind in ("plan", "context"):
        k = sub.add_parser(kind, help=f"new {kind} file from the template")
        k.add_argument("action", choices=["new"])
        k.add_argument("topic")
    li = sub.add_parser("lint", help="check a plan or context file")
    li.add_argument("files", nargs="+")

    args = p.parse_args(argv)
    repo = Repo(args.root)

    if args.cmd == "init":
        for line in init(repo, dry_run=args.dry_run, skills=not args.no_skills,
                         hooks=not args.no_hooks, ci=args.ci):
            print(line)
        if not args.dry_run:
            print("\nnext: fill the REPLACE ME lines in .cockpit/system-map.json, then "
                  f"`python3 {Path(sys.argv[0]).name} build --root {args.root}`")
        return 0
    if args.cmd == "detect":
        print(json.dumps(detect(repo), indent=2))
        return 0
    if args.cmd == "index":
        print("index rewritten" if write_index(repo) else "index already up to date")
        return 0
    if args.cmd == "status":
        return _print_status(repo, args.json)
    if args.cmd in ("build", "serve"):
        out = Path(getattr(args, "out", None) or repo.root / repo.config["site_out"])
        n = Site(repo, out, probe_now=args.probe).build()
        print(f"built {n} docs + dashboard into {out}/index.html")
        if args.cmd == "build":
            return 0
        import functools
        import http.server
        import threading
        import time
        if args.rebuild_every:
            def loop():
                while True:
                    time.sleep(args.rebuild_every)
                    try:
                        Site(Repo(args.root), out, probe_now=args.probe).build()
                    except Exception as exc:  # noqa: BLE001
                        print(f"rebuild failed: {exc}", file=sys.stderr)
            threading.Thread(target=loop, daemon=True).start()
        handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(out))
        print(f"serving on http://127.0.0.1:{args.port}/  (Ctrl+C to stop)")
        with http.server.ThreadingHTTPServer(("127.0.0.1", args.port), handler) as srv:
            try:
                srv.serve_forever()
            except KeyboardInterrupt:
                pass
        return 0
    if args.cmd == "check":
        errors, warnings = check(repo, strict=args.strict)
        for w in warnings:
            print(f"warn   {w}")
        for e in errors:
            print(f"ERROR  {e}")
        print(f"\n{len(errors)} error(s), {len(warnings)} warning(s)")
        return 1 if errors else 0
    if args.cmd == "vendor":
        print(vendor(repo))
        return 0
    if args.cmd == "board":
        if args.bcmd == "list":
            items = board_load(repo)["items"]
            for it in sorted(items, key=lambda i: (i.get("status") == "done", i.get("priority", "P9"))):
                if it.get("status") == "done" and not args.all:
                    continue
                print(f"{it.get('priority', '?')}  {it.get('status', 'open'):<6}  {it.get('id')}: {it.get('task')}"
                      + (f"  (due {it['deadline']})" if it.get("deadline") else ""))
            return 0
        if args.bcmd == "add":
            msg = board_add(repo, args)
            print(msg)
            return 0 if msg.startswith("added") else 1
        if args.bcmd in ("did", "done", "back"):
            to = {"did": "review", "done": "done", "back": "open"}[args.bcmd]
            msg = board_move(repo, args.id, to, args.note, by="cli")
            print(msg)
            return 0 if "->" in msg else 1
        problems = board_validate(board_load(repo)["items"])
        print("\n".join(problems) or "board OK")
        return 1 if problems else 0
    if args.cmd == "system":
        data = system_load(repo)
        if args.scmd == "check":
            errors, drafts = system_validate(data)
            for e in errors:
                print(f"ERROR  {e}")
            for d in drafts:
                print(f"draft  {d}: '{DRAFT_MARK}' still in its what line")
            print(f"{len(data['components'])} components, {len(errors)} error(s), {len(drafts)} draft(s)")
            return 1 if errors else 0
        res = probe_all(repo)
        for cid, r in res["components"].items():
            print(f"{r['state']:<8} {cid}: {r['detail']}")
        return 1 if any(r["state"] == "down" for r in res["components"].values()) else 0
    if args.cmd == "logs":
        comp = None
        if args.id:
            comp = next((c for c in system_load(repo)["components"] if c["id"] == args.id), None)
            if comp is None:
                print(f"no component {args.id}")
                return 1
        files = log_files(repo, comp)
        if not files:
            print("no logs found; add `logs` paths to components in .cockpit/system-map.json")
            return 1
        for cid, disp, f in files:
            lines = tail(f, args.n * 20 if args.grep else args.n)
            if args.grep:
                lines = [x for x in lines if args.grep.lower() in x.lower()][-args.n:]
            print(f"==> {disp} ({cid}) <==")
            print("\n".join(lines))
        return 0
    if args.cmd == "adr":
        print(new_adr(repo, args.title).relative_to(repo.root))
        return 0
    if args.cmd in ("plan", "context"):
        print(new_doc(repo, args.cmd, args.topic).relative_to(repo.root))
        return 0
    if args.cmd == "lint":
        bad = 0
        for f in args.files:
            problems = lint(Path(f))
            print(f"{'PASS' if not problems else 'FAIL'} {f}")
            for pr in problems:
                print(f"  - {pr}")
            bad += bool(problems)
        return 1 if bad else 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
