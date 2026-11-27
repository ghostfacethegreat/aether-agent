import subprocess
import sys
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


class ImportAnnotationRegressionTests(unittest.TestCase):
    def assert_module_imports(self, module_name: str) -> None:
        result = subprocess.run(
            [sys.executable, "-c", f"import {module_name}"],
            cwd=REPOSITORY_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(
            result.returncode,
            0,
            f"Import of {module_name} failed:\n{result.stderr}",
        )

    def test_learning_engine_module_imports(self) -> None:
        self.assert_module_imports("aether.learning.engine")

    def test_layered_memory_module_imports(self) -> None:
        self.assert_module_imports("aether.memory.layers")

    def test_memory_store_module_imports(self) -> None:
        self.assert_module_imports("aether.memory.store")


if __name__ == "__main__":
    unittest.main()
