#!/usr/bin/env python3
# requires: python3
"""Tests for scripts/ci/build-redirects.py (post-Hugo cross-domain redirect generator)."""
import contextlib
import importlib.util
import io
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[3]
TARGET = ROOT / "scripts/ci/build-redirects.py"


def load_module():
    spec = importlib.util.spec_from_file_location("build_redirects", TARGET)
    if spec is None or spec.loader is None or not TARGET.is_file():
        raise FileNotFoundError(f"missing {TARGET}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestBuildRedirects(unittest.TestCase):
    def setUp(self):
        self.mod = load_module()

    def _run(self, yaml_text: str, existing_files: list[str] | None = None):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            pub = root / "public"
            pub.mkdir()
            for rel in existing_files or []:
                p = pub / rel
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text("<html>live page</html>", encoding="utf-8")
            map_file = root / "redirects.yaml"
            map_file.write_text(yaml_text, encoding="utf-8")
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
                rc = self.mod.main(["build-redirects.py", "--public", str(pub), "--map", str(map_file)])
            generated = {
                p.relative_to(pub).as_posix(): p.read_text(encoding="utf-8")
                for p in pub.rglob("*.html")
            }
            return rc, buf.getvalue(), generated

    def test_generates_noindex_canonical_refresh_stub(self):
        rc, out, gen = self._run(
            '- from: /docs/use/guide/\n'
            '  to: https://maku.ogenki.io/docs/guide/\n'
        )
        self.assertEqual(rc, 0, out)
        self.assertIn("docs/use/guide/index.html", gen)
        html = gen["docs/use/guide/index.html"]
        self.assertIn('<meta name="robots" content="noindex">', html)
        self.assertIn('<link rel="canonical" href="https://maku.ogenki.io/docs/guide/">', html)
        self.assertIn('<meta http-equiv="refresh" content="0; url=https://maku.ogenki.io/docs/guide/">', html)
        self.assertIn('href="https://maku.ogenki.io/docs/guide/"', html)

    def test_refuses_collision_with_existing_live_page(self):
        rc, out, _ = self._run(
            '- from: /docs/serving/\n'
            '  to: https://maku.ogenki.io/docs/concepts/\n',
            existing_files=["docs/serving/index.html"],
        )
        self.assertNotEqual(rc, 0)
        self.assertIn("collision", out.lower())

    def test_refuses_duplicate_from_paths(self):
        rc, out, _ = self._run(
            '- from: /docs/use/guide/\n'
            '  to: https://maku.ogenki.io/docs/guide/\n'
            '- from: docs/use/guide\n'
            '  to: https://maku.ogenki.io/docs/guide/\n'
        )
        self.assertNotEqual(rc, 0)
        self.assertIn("duplicate", out.lower())

    def test_refuses_non_maku_target_and_path_traversal(self):
        rc1, out1, _ = self._run(
            '- from: /docs/foo/\n'
            '  to: https://evil.example/docs/foo/\n'
        )
        self.assertNotEqual(rc1, 0)
        self.assertIn("maku.ogenki.io", out1)

        rc2, out2, _ = self._run(
            '- from: /docs/../../etc/passwd\n'
            '  to: https://maku.ogenki.io/docs/guide/\n'
        )
        self.assertNotEqual(rc2, 0)
        self.assertIn("invalid", out2.lower())

    def test_escapes_html_in_target_url(self):
        rc, out, gen = self._run(
            '- from: /docs/use/guide/\n'
            '  to: "https://maku.ogenki.io/docs/guide/?a=1&b=2"\n'
        )
        self.assertEqual(rc, 0, out)
        html = gen["docs/use/guide/index.html"]
        self.assertIn("?a=1&amp;b=2", html)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestBuildRedirects)
    res = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if res.wasSuccessful() else 1)
