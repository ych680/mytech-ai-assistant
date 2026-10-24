"""Serialized manifests stay reproducible across native filesystem flavours."""

from contextlib import contextmanager
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
import unittest
from unittest.mock import patch

from tools import build_aiep_test as aiep
from tools import build_prompt_ab_test as deferred
from tools import sync_catalogue as sync


@contextmanager
def windows_relative_paths():
    # Leave native file reads untouched; only emulate relative path formatting.
    relative_to = Path.relative_to

    def windows_relative_to(path, *args, **kwargs):
        return PureWindowsPath(relative_to(path, *args, **kwargs).as_posix())

    with patch.object(Path, "relative_to", windows_relative_to):
        yield


class ManifestPortabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dataset = sync.load_dataset(sync.TEST_DATASET)

    def assert_repository_path(self, path):
        self.assertNotIn("\\", path)
        self.assertFalse(PurePosixPath(path).is_absolute())
        self.assertNotIn("..", PurePosixPath(path).parts)

    def test_local_manifest_is_identical_with_windows_relative_paths(self):
        native = sync.render_outputs(self.dataset)
        with windows_relative_paths():
            self.assertEqual(sync.render_outputs(self.dataset), native)
        manifest = json.loads(native["manifest.json"])
        self.assertEqual(manifest["workflow_template"], "tools/templates/mytech_current_working_portable.json")
        self.assert_repository_path(manifest["master"])

    def test_hosted_manifest_is_identical_with_windows_relative_paths(self):
        native = aiep.render_outputs(self.dataset)
        with windows_relative_paths(), patch.object(aiep, "OUTPUT_SUBDIR", PureWindowsPath(aiep.OUTPUT_SUBDIR.as_posix())):
            self.assertEqual(aiep.render_outputs(self.dataset), native)
        manifest = json.loads(native["manifest.json"])
        self.assertEqual(manifest["upload_directory"], "generated/aiep_v2_1_test/site")
        for path in [manifest["master"], *manifest["sources_sha256"]]:
            self.assert_repository_path(path)

    def test_deferred_manifest_is_identical_with_windows_relative_paths(self):
        native = deferred.render_outputs()
        with windows_relative_paths():
            self.assertEqual(deferred.render_outputs(), native)
        manifest = json.loads(native["manifest.json"])
        for path in manifest["sources_sha256"]:
            self.assert_repository_path(path)


if __name__ == "__main__":
    unittest.main()
