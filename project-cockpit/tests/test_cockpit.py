"""project-cockpit tests. Standard library only:  python3 -m unittest discover -s tests"""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

KIT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KIT))
import cockpit as c  # noqa: E402


def make_repo(git: bool = True) -> Path:
    root = Path(tempfile.mkdtemp(prefix="cockpit-test."))
    (root / "docs").mkdir()
    (root / "logs").mkdir()
    (root / "README.md").write_text("# Demo\n\nHello.\n")
    (root / "docs" / "design.md").write_text("# Design\n\n**Status:** DONE 2026-01-01. Shipped.\n")
    (root / "docs" / "idea.md").write_text("# Idea\n\nNo status here.\n")
    (root / "docker-compose.yml").write_text(
        "services:\n  web:\n    image: nginx\n    ports:\n      - \"8080:80\"\n  db:\n    image: postgres\n")
    (root / "logs" / "app.log").write_text("ok\nERROR login failed password=hunter2\n")
    if git:
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        subprocess.run(["git", "add", "-A"], cwd=root, check=True)
        subprocess.run(["git", "-c", "user.email=t@example.com", "-c", "user.name=t",
                        "commit", "-qm", "init"], cwd=root, check=True)
    return root


class Status(unittest.TestCase):
    def test_classify_clear_words(self):
        self.assertEqual(c.classify_status("DONE, live and confirmed"), "done")
        self.assertEqual(c.classify_status("Accepted 2026-09-26 (owner)"), "done")
        self.assertEqual(c.classify_status("parked. Do not run it."), "cancel")
        self.assertEqual(c.classify_status("design locked, build not started"), "todo")
        self.assertEqual(c.classify_status("Blocked on the vendor"), "blocked")
        self.assertEqual(c.classify_status("Proposed 2026-10-02. Waiting."), "started")

    def test_vague_is_no_opinion(self):
        self.assertIsNone(c.classify_status("built and installed, waiting on someone"))
        self.assertIsNone(c.classify_status("Ready to send"))

    def test_first_sentence_only(self):
        self.assertIsNone(c.classify_status("Plan approved. Stage 2 blocked on hardware."))

    def test_own_status_forms(self):
        self.assertEqual(c.own_status("# T\n## Status: DONE\n")[0], "done")
        self.assertEqual(c.own_status("# T\n**Status (2026-01-01):** in progress\n")[0], "started")
        self.assertEqual(c.own_status("# T\n## Status\n\nCancelled.\n")[0], "cancel")
        self.assertIsNone(c.own_status("# T\n```\nStatus: done\n```\n")[0])
        self.assertIsNone(c.own_status("# T\n" + "x\n" * 60 + "Status: done\n")[0])

    def test_label_order(self):
        m = {"a/x.md": "todo", "a/": "cancel"}
        doc = "# X\n**Status:** DONE\n"
        self.assertEqual(c.doc_label("a/x.md", doc, m, "started"), ("todo", "status.json"))
        self.assertEqual(c.doc_label("a/y.md", doc, m, "started"), ("done", "doc"))
        self.assertEqual(c.doc_label("a/z.md", "# Z\n", m, "started"), ("cancel", "status.json folder"))
        self.assertEqual(c.doc_label("b/z.md", "# Z\n", m, "started"), ("started", "default"))


class InitAndDetect(unittest.TestCase):
    def setUp(self):
        self.root = make_repo()
        self.repo = c.Repo(self.root)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_detect(self):
        found = c.detect(self.repo)
        ids = {x["id"] for x in found["components"]}
        self.assertIn("web", ids)
        self.assertIn("db", ids)
        web = next(x for x in found["components"] if x["id"] == "web")
        self.assertEqual(web["probe"], {"type": "tcp", "host": "127.0.0.1", "port": 8080})
        self.assertIn("logs/app.log", found["logs"])

    def test_init_creates_and_never_overwrites(self):
        (self.root / "AGENTS.md").write_text("# Our rules\n\nKeep it.\n")
        c.init(self.repo)
        agents = (self.root / "AGENTS.md").read_text()
        self.assertTrue(agents.startswith("# Our rules"), "existing AGENTS.md must be kept")
        self.assertIn(c.BLOCK_START, agents)
        for rel in ("CLAUDE.md", "CHANGELOG.md", "MANUAL.md", ".cockpit/board.json",
                    ".cockpit/system-map.json", ".cockpit/index.md", "docs/adr/0001-record-decisions-as-adrs.md",
                    ".claude/skills/cockpit/SKILL.md", ".githooks/pre-commit"):
            self.assertTrue((self.root / rel).exists(), rel)
        before = {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file() and ".git/" not in str(p)}
        report = c.init(c.Repo(self.root))
        after = {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file() and ".git/" not in str(p)}
        self.assertEqual(before, after, "a second init must change nothing")
        self.assertFalse([r for r in report if r.startswith(("created", "appended"))])

    def test_fresh_init_passes_check(self):
        c.init(self.repo)
        errors, warnings = c.check(c.Repo(self.root))
        self.assertEqual(errors, [])
        self.assertTrue(any("REPLACE ME" in w for w in warnings))

    def test_no_git_still_works(self):
        root = make_repo(git=False)
        try:
            repo = c.Repo(root)
            self.assertIn("docs/design.md", c.list_docs(repo))
            c.init(repo, hooks=False)
            self.assertTrue((root / ".cockpit" / "index.md").exists())
        finally:
            shutil.rmtree(root, ignore_errors=True)


class BoardSystemLogs(unittest.TestCase):
    def setUp(self):
        self.root = make_repo()
        c.init(c.Repo(self.root))
        self.repo = c.Repo(self.root)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_board_requires_every_field(self):
        problems = c.board_validate([{"id": "x", "priority": "P2", "task": "t", "what": "w",
                                      "why": "", "steps": [], "dod": "d"}])
        self.assertIn("x: 'why' is empty", problems)
        self.assertIn("x: 'steps' is empty", problems)

    def test_board_flow(self):
        self.assertEqual(c.board_move(self.repo, "cockpit-first-look", "review", "did it"),
                         "cockpit-first-look: open -> review")
        self.assertEqual(c.board_move(self.repo, "cockpit-first-look", "done"), "cockpit-first-look: review -> done")
        self.assertIn("cannot go", c.board_move(self.repo, "cockpit-first-look", "review"))

    def test_system_validate(self):
        data = {"groups": [{"id": "g"}], "components": [
            {"id": "a", "name": "A", "what": "does a", "group": "g", "talksTo": ["nope"]},
            {"id": "b", "name": "B", "what": "REPLACE ME: x", "group": "g"}]}
        errors, drafts = c.system_validate(data)
        self.assertTrue(any("talksTo 'nope'" in e for e in errors))
        self.assertEqual(drafts, ["b"])

    def test_file_probe(self):
        comp = {"id": "f", "probe": {"type": "file", "path": "logs/app.log", "expectedEvery": "1h"}}
        self.assertEqual(c.probe(self.repo, comp)["state"], "up")
        comp["probe"]["path"] = "logs/missing.log"
        self.assertEqual(c.probe(self.repo, comp)["state"], "down")

    def test_logs_are_redacted(self):
        files = c.log_files(self.repo)
        self.assertTrue(files)
        lines = c.tail(files[0][2], 10)
        self.assertTrue(any("[redacted]" in x for x in lines))
        self.assertFalse(any("hunter2" in x for x in lines))


class Drift(unittest.TestCase):
    def test_override_disagreeing_with_doc_is_drift(self):
        root = make_repo()
        try:
            c.init(c.Repo(root))
            c.write_json(root / ".cockpit" / "status.json", {"docs/design.md": "started"})
            repo = c.Repo(root)
            rows = c.drift(c.load_docs(repo))
            self.assertEqual([d.rel for d in rows], ["docs/design.md"])
            errors, _ = c.check(repo)
            self.assertTrue(any("status drift" in e for e in errors))
        finally:
            shutil.rmtree(root, ignore_errors=True)


class Build(unittest.TestCase):
    def test_build_writes_every_page(self):
        root = make_repo()
        try:
            c.init(c.Repo(root))
            (root / "docs" / "links.md").write_text("# Links\n\nSee [design](design.md#top).\n")
            out = root / ".cockpit" / "site"
            n = c.Site(c.Repo(root), out).build()
            self.assertGreaterEqual(n, 4)
            for page in ("index.html", "board.html", "system.html", "logs.html", "decisions.html",
                         "plans.html", "docs.html", "docs/docs/design.html", "cockpit.json"):
                self.assertTrue((out / page).exists(), page)
            self.assertIn('href="design.html#top"', (out / "docs/docs/links.html").read_text())
            summary = json.loads((out / "cockpit.json").read_text())
            self.assertEqual(summary["docs"]["done"] >= 1, True)
            self.assertNotIn("hunter2", (out / "logs.html").read_text())
        finally:
            shutil.rmtree(root, ignore_errors=True)


class Markdown(unittest.TestCase):
    def test_builtin_renderer(self):
        out = c.mini_markdown("# Title\n\nSome **bold** and `code`.\n\n- [x] done\n- [ ] open\n  - nested\n\n"
                              "| a | b |\n|---|---|\n| 1 | 2 |\n\n```\n<raw>\n```\n")
        self.assertIn('<h1 id="title">Title</h1>', out)
        self.assertIn("<strong>bold</strong>", out)
        self.assertIn("✅ done", out)
        self.assertIn("<ul><li>nested</li></ul>", out)
        self.assertIn("<td>1</td>", out)
        self.assertIn("&lt;raw&gt;", out)

    def test_html_is_escaped(self):
        self.assertNotIn("<script>", c.mini_markdown("hello <script>x</script>"))


class Lint(unittest.TestCase):
    def test_templates_pass_and_bad_file_fails(self):
        root = make_repo()
        try:
            c.init(c.Repo(root))
            repo = c.Repo(root)
            for kind in ("plan", "context"):
                path = c.new_doc(repo, kind, "Checkout revamp")
                self.assertEqual(c.lint(path), [], kind)
            bad = root / "plans" / "bad-plan.md"
            bad.write_text("# Bad - Plan\n\n## Goal\n\nx\n")
            problems = c.lint(bad)
            self.assertTrue(any("Handover prompt" in p for p in problems))
            adr = c.new_adr(repo, "Use Postgres")
            self.assertEqual(adr.name, "0002-use-postgres.md")
            self.assertIn("# ADR-0002: Use Postgres", adr.read_text())
        finally:
            shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
