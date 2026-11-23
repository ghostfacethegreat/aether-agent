import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from aether.config import Config


class TempHomeTest(unittest.TestCase):
    def setUp(self):
        self._env = patch.dict(os.environ, {}, clear=False)
        self._env.start()
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.home = self.root / "home"
        self.workspace = self.root / "workspace"
        self.home.mkdir()
        self.workspace.mkdir()
        os.environ["AETHER_HOME"] = str(self.home)
        os.environ["AETHER_WORKSPACE"] = str(self.workspace)
        self.addCleanup(self._tmp.cleanup)
        self.addCleanup(self._env.stop)

    def config(self, **overrides):
        data = {
            "provider": "mock",
            "model": "mock-standard",
            "providers": {},
            "tool_permissions": {"require_approval": []},
        }
        data.update(overrides)
        return Config(data)
