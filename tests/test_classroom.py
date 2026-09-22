"""離線回歸測試：不使用金鑰、不呼叫真實 API。"""
from contextlib import ExitStack, redirect_stdout
from datetime import datetime
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "server")]
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
from movieapp import config, demo, gemini, http, merge, sources, tmdb
import django
with patch.object(config, "ensure_env_file"):
    django.setup()
from django.test import Client, override_settings
import requests
import build_modules


class OfflineCase(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.dict(os.environ, {
            "MOVIEAPP_MODE": "demo", "TMDB_READ_ACCESS_TOKEN": "", "GEMINI_API_KEY": "",
        }))
        self.stack.enter_context(patch.object(config, "load_env", return_value={}))
        self.network = self.stack.enter_context(patch(
            "requests.sessions.Session.request", side_effect=AssertionError("Unexpected network call")))
        tmdb.clear_cache()
        gemini.reset_session()


class CoreTests(OfflineCase):
    def test_title_cleanup(self):
        self.assertEqual(sources.clean_titles(["星際郵差 (國語版)", "星際郵差 特別場", ""]), ["星際郵差"])

    def test_missing_title_is_not_a_match(self):
        for candidate in [{"title": "zzzz"}, {"original_title": "zzzz"}, {}, {"title": None}]:
            with self.subTest(candidate=candidate):
                self.assertLess(tmdb.match_score("alpha", candidate), 0.6)
                self.assertIsNone(tmdb.best_match("alpha", [candidate]))

    def test_exact_and_normalized_match(self):
        candidate = {"id": 1, "title": "星際郵差"}
        self.assertEqual(tmdb.match_score("星際 郵差", candidate), 1)
        self.assertEqual(tmdb.best_match("星際 郵差", [candidate]), candidate)
        self.assertEqual(tmdb.match_score("", candidate), 0)

    def test_demo_catalog_deduplicates_and_keeps_sources(self):
        movies, genres, errors = merge.catalog()
        self.assertFalse(errors)
        self.assertEqual(len(movies), 3)
        shared = next(m for m in movies if m["meta"]["id"] == 910001)
        self.assertEqual(set(shared["sources"]), {"showtimes", "miramar"})
        self.assertEqual(len(shared["titles"]), 2)
        self.assertIn(16, genres)
        self.network.assert_not_called()

    def test_demo_data_is_independent_between_calls(self):
        result = demo.search_results("星際郵差")
        result[0]["title"] = "changed"
        self.assertEqual(demo.search_results("星際郵差")[0]["title"], "星際郵差")

    def test_dates_use_day_and_missing_last(self):
        movies = [{"title": "early", "meta": {"release_date": "2026-07-01"}},
                  {"title": "late", "meta": {"release_date": "2026-07-31"}},
                  {"title": "missing", "meta": {}}]
        for descending, expected in [(True, ["late", "early", "missing"]), (False, ["early", "late", "missing"])]:
            result = merge.apply_filters(movies, sort_by="release_date", descending=descending)
            self.assertEqual([m["title"] for m in result], expected)

    def test_month_threshold_and_rating(self):
        movies = [{"title": "A", "meta": {"release_date": "2026-07-31", "vote_average": 8}},
                  {"title": "B", "meta": {"release_date": "2026-08-01", "vote_average": 9}}]
        self.assertEqual([m["title"] for m in merge.apply_filters(movies, since="2026-08", min_vote_average=7)], ["B"])

    def test_prompt_limit_and_sources(self):
        movies = [{"title": f"Movie {i}", "sources": ["showtimes"], "meta": {}} for i in range(70)]
        prompt = gemini.build_system_prompt(movies, now=datetime(2026, 7, 1))
        self.assertEqual(len(re.findall(r"^\d+\.", prompt, re.M)), 60)
        self.assertIn("秀泰影城", prompt)
        self.assertIn("不要編造", prompt)
        self.assertNotIn("Movie 60", prompt)

    def test_empty_prompt_is_explicit(self):
        self.assertIn("片單為空", gemini.build_system_prompt([]))

    def test_demo_chat_is_labeled_and_does_not_use_network(self):
        reply, error = gemini.ask("推薦電影")
        self.assertIsNone(error)
        self.assertIn("未呼叫 AI", reply)
        self.network.assert_not_called()

    def test_live_http_timeout(self):
        config.set_mode("live")
        with patch("requests.request", side_effect=requests.exceptions.Timeout):
            data, error = http.fetch_json("https://example.invalid")
        self.assertIsNone(data)
        self.assertIn("逾時", error)

    def test_live_gemini_response_and_previous_interaction(self):
        config.set_mode("live")
        answer = {"id": "interaction-a", "steps": [{"type": "model_output", "content": [{"type": "text", "text": "測試回答"}]}]}
        with patch.object(config, "gemini_key", return_value="placeholder"), patch.object(gemini, "fetch_json", return_value=(answer, None)) as fetch:
            self.assertEqual(gemini.ask("第一問", system="資料", session_id="lesson"), ("測試回答", None))
            gemini.ask("第二問", system="新資料", session_id="lesson")
            payload = fetch.call_args.kwargs["json_body"]
            self.assertEqual(payload["previous_interaction_id"], "interaction-a")
            self.assertEqual(payload["system_instruction"], "新資料")

    def test_cache_does_not_cross_modes(self):
        demo_result, _ = tmdb.search("星際郵差")
        config.set_mode("live")
        with patch.object(config, "tmdb_token", return_value="placeholder"), patch.object(tmdb, "fetch_json", return_value=({"results": [{"id": 42}]}, None)) as fetch:
            live_result, _ = tmdb.search("星際郵差")
        self.assertNotEqual(demo_result, live_result)
        fetch.assert_called_once()

    def test_demo_unknown_endpoint_is_not_live_fallback(self):
        result, error = http.fetch_json("https://example.invalid")
        self.assertIsNone(result)
        self.assertIn("示範模式", error)
        self.network.assert_not_called()

    def test_generated_files_match(self):
        with redirect_stdout(io.StringIO()):
            self.assertEqual(build_modules.build(check=True), 0)

    def test_doctor_requires_this_chapter_modules(self):
        with tempfile.TemporaryDirectory() as folder:
            package = Path(folder)
            for name in ("config", "http"):
                (package / f"{name}.py").write_text("", encoding="utf-8")
            with patch.object(config, "PKG_DIR", package), redirect_stdout(io.StringIO()) as out:
                self.assertFalse(config.doctor())
            self.assertRegex(out.getvalue(), r"\[--\]\s+movieapp/demo\.py")
            (package / "demo.py").write_text("", encoding="utf-8")
            with patch.object(config, "PKG_DIR", package), redirect_stdout(io.StringIO()) as out:
                self.assertTrue(config.doctor())
            self.assertRegex(out.getvalue(), r"\[OK\]\s+movieapp/demo\.py")

    def test_check_does_not_overwrite_drift(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "notebooks").mkdir()
            nb = {"cells": [{"cell_type": "code", "source": ["%%writefile ../sample.py\n", "value = 1\n"]}]}
            (root / "notebooks" / "sample.ipynb").write_text(json.dumps(nb), encoding="utf-8")
            target = root / "sample.py"
            target.write_text("value = 2\n", encoding="utf-8")
            with redirect_stdout(io.StringIO()):
                self.assertEqual(build_modules.build(check=True, root=root), 1)
            self.assertEqual(target.read_text(), "value = 2\n")

    def test_frontend_date_rules_match_python(self):
        node = os.environ.get("NODE_BINARY") or shutil.which("node")
        if not node:
            self.skipTest("Node.js 僅用於前端回歸測試，應用程式不需要它")
        js = (ROOT / "server/static/data.js").read_text(encoding="utf-8")
        function = js[js.index("function applyFilters("):js.index("function searchMovies(")]
        movies = [{"title": "early", "meta": {"release_date": "2026-07-01"}},
                  {"title": "late", "meta": {"release_date": "2026-07-31"}},
                  {"title": "unknown", "meta": {}}]
        for mode in ["asc", "desc"]:
            program = "const SORT_KEYS=['popularity','releaseDate','voteAverage'];\n" + function
            program += "\nconst movies=" + json.dumps(movies) + ";"
            program += "\nconst filters={adult:'off',genreId:null,popularity:{mode:'off',threshold:null},voteAverage:{mode:'off',threshold:null},releaseDate:{mode:'" + mode + "',threshold:null}};"
            program += "\nconsole.log(JSON.stringify(applyFilters(movies,filters).map(m=>m.title)));"
            proc = subprocess.run([node, "-e", program], capture_output=True, text=True, check=True)
            python_order = [m["title"] for m in merge.apply_filters(movies, sort_by="release_date", descending=mode == "desc")]
            self.assertEqual(json.loads(proc.stdout), python_order)


class ConfigTests(unittest.TestCase):
    def test_load_env_override_replaces_only_filled_values(self):
        with tempfile.TemporaryDirectory() as folder:
            env_file = Path(folder) / ".env"
            env_file.write_text("A_KEY=new\nB_KEY=\n", encoding="utf-8")
            with patch.dict(os.environ, {"A_KEY": "old", "B_KEY": "keep"}):
                config.load_env(env_file)
                self.assertEqual(os.environ["A_KEY"], "old")
                config.load_env(env_file, override=True)
                self.assertEqual(os.environ["A_KEY"], "new")
                self.assertEqual(os.environ["B_KEY"], "keep")
                os.environ.pop("A_KEY")
                config.load_env(env_file)
                self.assertEqual(os.environ["A_KEY"], "new")

    def test_requirements_files_declare_utf8_for_pip(self):
        for name in ("requirements.txt", "requirements-classroom.txt", "requirements-dev.txt"):
            first = (ROOT / name).read_text(encoding="utf-8").splitlines()[0]
            self.assertRegex(first, r"^#.*coding[:=]\s*utf-8", name)


class ApiTests(OfflineCase):
    def setUp(self):
        super().setUp()
        self.stack.enter_context(override_settings(ALLOWED_HOSTS=["testserver", "127.0.0.1", "localhost"], DEBUG=False))
        self.client = Client(enforce_csrf_checks=True)
        response = self.client.get("/", REMOTE_ADDR="127.0.0.1")
        response.close()
        self.token = self.client.cookies["csrftoken"].value

    def post(self, path, body):
        return self.client.post(path, json.dumps(body), content_type="application/json",
                                HTTP_X_CSRFTOKEN=self.token, REMOTE_ADDR="127.0.0.1")

    def test_demo_catalog_without_key(self):
        response = self.client.get("/api/movies/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["movies"]), 3)
        self.network.assert_not_called()

    def test_live_missing_keys_are_401(self):
        config.set_mode("live")
        for path in ["/api/movies/", "/api/tmdb/search/?query=test", "/api/tmdb/genres/"]:
            response = self.client.get(path)
            self.assertEqual(response.status_code, 401)
            self.assertEqual(response.json()["need_key"], "tmdb")

    def test_invalid_chat_shapes_are_400(self):
        for body in [[], None, 1, {"messages": "bad"}, {"messages": ["bad"]},
                     {"messages": [{"role": "user", "content": 1}]}]:
            self.assertEqual(self.post("/api/chat/", body).status_code, 400)

    def test_invalid_movie_shape_is_400(self):
        for movies in [[{"title": "A", "meta": {"vote_average": "bad"}}],
                       [{"title": "A", "sources": "bad"}], ["bad"]]:
            body = {"messages": [{"role": "user", "content": "hello"}], "movies": movies}
            self.assertEqual(self.post("/api/chat/", body).status_code, 400)

    def test_invalid_genre_id_and_nonfinite_rating(self):
        body = {"messages": [{"role": "user", "content": "hello"}], "genres": {"²": "bad"}}
        self.assertEqual(self.post("/api/chat/", body).status_code, 400)
        for rating in [float("nan"), float("inf"), 10 ** 400, True]:
            body = {"messages": [{"role": "user", "content": "hello"}],
                    "movies": [{"title": "A", "meta": {"vote_average": rating}}]}
            self.assertEqual(self.post("/api/chat/", body).status_code, 400)

    def test_chat_builds_backend_prompt(self):
        body = {"messages": [{"role": "user", "content": "hello"}],
                "movies": [{"title": "A", "sources": ["showtimes"], "meta": {"genre_ids": [16]}}],
                "genres": {"16": "動畫"}, "system": "client override"}
        with patch.object(gemini, "ask", return_value=("answer", None)) as ask:
            response = self.post("/api/chat/", body)
        self.assertEqual(response.status_code, 200)
        prompt = ask.call_args.kwargs["system"]
        self.assertIn("秀泰影城", prompt)
        self.assertIn("動畫", prompt)
        self.assertNotIn("client override", prompt)

    def test_csrf_rejects_missing_token(self):
        response = self.client.post("/api/keys/", '{"tmdb":"placeholder"}', content_type="application/json", REMOTE_ADDR="127.0.0.1")
        self.assertEqual(response.status_code, 403)

    def test_csrf_rejects_foreign_origin(self):
        with patch.object(config, "save_keys") as save:
            response = self.client.post("/api/keys/", '{"tmdb":"placeholder"}', content_type="text/plain",
                                        HTTP_ORIGIN="https://example.invalid", HTTP_X_CSRFTOKEN=self.token,
                                        REMOTE_ADDR="127.0.0.1")
        self.assertEqual(response.status_code, 403)
        save.assert_not_called()

    def test_valid_local_key_post_and_invalid_values(self):
        with patch.object(config, "save_keys") as save:
            self.assertEqual(self.post("/api/keys/", {"tmdb": "placeholder"}).status_code, 200)
            save.assert_called_once_with(TMDB_READ_ACCESS_TOKEN="placeholder")
        for body in [[], {"tmdb": 5}, {"tmdb": "line1\nline2"}]:
            self.assertEqual(self.post("/api/keys/", body).status_code, 400)

    def test_keys_status_and_remote_rejection(self):
        response = self.client.get("/api/keys/", REMOTE_ADDR="127.0.0.1")
        self.assertEqual(response.json(), {"keys": {"tmdb": False, "gemini": False}, "mode": "demo"})
        self.assertEqual(self.client.get("/api/keys/", REMOTE_ADDR="192.0.2.1").status_code, 403)

    def test_static_assets_allowlist(self):
        for name in ["styles.css", "state.js", "data.js", "actions.js", "render.js", "keys.js", "app.js"]:
            response = self.client.get("/assets/" + name)
            self.assertEqual(response.status_code, 200)
            response.close()
        self.assertEqual(self.client.get("/assets/.env").status_code, 404)


if __name__ == "__main__":
    unittest.main()
