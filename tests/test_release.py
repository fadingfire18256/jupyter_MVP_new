"""GitHub 教材交付檢查。"""
import os
from pathlib import Path
import shutil
import subprocess
import unittest

import nbformat

ROOT = Path(__file__).resolve().parents[1]


class ReleaseTests(unittest.TestCase):
    def test_notebooks_are_valid_and_have_no_saved_outputs(self):
        paths = sorted((ROOT / "notebooks").glob("*.ipynb"))
        self.assertEqual(len(paths), 6)
        for path in paths:
            with self.subTest(notebook=path.name):
                nb = nbformat.read(path, as_version=4)
                nbformat.validate(nb)
                for cell in nb.cells:
                    if cell.cell_type == "code":
                        self.assertEqual(cell.outputs, [], path.name)
                        self.assertIsNone(cell.execution_count, path.name)

    def test_old_frontend_responses_do_not_overwrite_new_load(self):
        node = os.environ.get("NODE_BINARY") or shutil.which("node")
        if not node:
            self.skipTest("Node.js 僅用於前端回歸測試，CI 會執行本項")
        result = subprocess.run([node, str(ROOT / "tests/frontend_loading.cjs")],
                                capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
