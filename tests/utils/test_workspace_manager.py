import unittest
from pathlib import Path
from unittest.mock import MagicMock # Not strictly needed if only using Path objects

from src.ii_agent.utils.workspace_manager import WorkspaceManager

class TestWorkspaceManager(unittest.TestCase):

    def test_init(self):
        root_path = Path("/test/root")
        container_path = Path("/container/ws")

        # Test with container_workspace
        wm_with_container = WorkspaceManager(root=root_path, container_workspace=container_path)
        self.assertEqual(wm_with_container.root, root_path.absolute())
        self.assertEqual(wm_with_container.container_workspace, container_path) # Does not call .absolute() in constructor

        # Test without container_workspace
        wm_no_container = WorkspaceManager(root=root_path)
        self.assertEqual(wm_no_container.root, root_path.absolute())
        self.assertIsNone(wm_no_container.container_workspace)

        # Test with string paths
        wm_str_paths = WorkspaceManager(root="/another/root", container_workspace="/cont/ws_str")
        self.assertEqual(wm_str_paths.root, Path("/another/root").absolute())
        self.assertEqual(wm_str_paths.container_workspace, Path("/cont/ws_str"))


    def test_workspace_path_resolution(self):
        # Setup
        local_root = Path("/local/workspace_root").absolute()
        container_root = Path("/var/project_in_container").absolute()
        wm = WorkspaceManager(root=local_root, container_workspace=container_root)

        # 1. Relative path
        self.assertEqual(wm.workspace_path("file.txt"), local_root / "file.txt")
        self.assertEqual(wm.workspace_path("subdir/another.py"), local_root / "subdir/another.py")
        self.assertEqual(wm.workspace_path(Path("path_obj/file.c")), local_root / "path_obj/file.c")

        # 2. Absolute path NOT in container_workspace
        self.assertEqual(wm.workspace_path("/abs/random/file.txt"), Path("/abs/random/file.txt").absolute())

        # 3. Absolute path that IS in container_workspace
        #    (e.g., agent thinks it's operating inside container at /var/project_in_container/data/img.png)
        #    This should be mapped to /local/workspace_root/data/img.png
        container_file_abs = container_root / "data/img.png"
        self.assertEqual(wm.workspace_path(str(container_file_abs)), local_root / "data/img.png")
        self.assertEqual(wm.workspace_path(container_file_abs), local_root / "data/img.png")

        # 4. Absolute path that IS local_root (should resolve to itself)
        self.assertEqual(wm.workspace_path(local_root / "some_local.txt"), local_root / "some_local.txt")


    def test_workspace_path_no_container_workspace_set(self):
        local_root = Path("/local_only_ws").absolute()
        wm = WorkspaceManager(root=local_root) # No container_workspace

        # 1. Relative path
        self.assertEqual(wm.workspace_path("file.txt"), local_root / "file.txt")

        # 2. Absolute path (should return as is, since no container mapping to consider)
        self.assertEqual(wm.workspace_path("/abs/path/data.doc"), Path("/abs/path/data.doc").absolute())


    def test_container_path_resolution_with_container_ws(self):
        local_root = Path("/local/workspace_root").absolute()
        container_root = Path("/var/project_in_container").absolute()
        wm = WorkspaceManager(root=local_root, container_workspace=container_root)

        # 1. Relative path (relative to what? Ambiguous, assumes relative to current logic's root for container)
        #    Current logic: if relative, it becomes container_root / path
        self.assertEqual(wm.container_path("file.txt"), container_root / "file.txt")
        self.assertEqual(wm.container_path("subdir/script.sh"), container_root / "subdir/script.sh")

        # 2. Absolute path NOT in local_root
        self.assertEqual(wm.container_path("/abs/elsewhere/data"), Path("/abs/elsewhere/data").absolute())

        # 3. Absolute path that IS in local_root
        #    (e.g., tool provides /local/workspace_root/src/main.py)
        #    This should be mapped to /var/project_in_container/src/main.py
        local_file_abs = local_root / "src/main.py"
        self.assertEqual(wm.container_path(str(local_file_abs)), container_root / "src/main.py")
        self.assertEqual(wm.container_path(local_file_abs), container_root / "src/main.py")

        # 4. Absolute path that IS container_root (should resolve to itself)
        self.assertEqual(wm.container_path(container_root / "some_cont.txt"), container_root / "some_cont.txt")


    def test_container_path_resolution_no_container_ws(self):
        local_root = Path("/local_only_ws").absolute()
        wm = WorkspaceManager(root=local_root) # No container_workspace

        # 1. Relative path (should become local_root / path as fallback)
        self.assertEqual(wm.container_path("file.txt"), local_root / "file.txt")

        # 2. Absolute path (should return as is)
        self.assertEqual(wm.container_path("/abs/some/other.zip"), Path("/abs/some/other.zip").absolute())


    def test_relative_path_resolution(self):
        local_root = Path("/users/test/project_alpha").absolute()
        wm = WorkspaceManager(root=local_root)

        # 1. Path inside workspace (provided as absolute)
        abs_inside_path = local_root / "src/app.py"
        self.assertEqual(wm.relative_path(abs_inside_path), Path("src/app.py"))

        # 2. Path inside workspace (provided as relative to CWD, but resolves inside)
        #    This depends on CWD of test runner. Path.resolve() is key.
        #    To make this robust, we need to ensure the input path is truly relative to root.
        #    The `workspace_path` call inside `relative_path` handles resolving it first.
        self.assertEqual(wm.relative_path("docs/readme.md"), Path("docs/readme.md"))

        # 3. Path outside workspace
        outside_path_abs = Path("/etc/hosts").absolute()
        self.assertEqual(wm.relative_path(outside_path_abs), outside_path_abs)

        # 4. Path that is the root itself
        self.assertEqual(wm.relative_path(local_root), Path("."))

        # 5. Path that looks relative but would go "above" root if simply joined
        #    e.g., if root is /a/b, and path is ../../c
        #    workspace_path will resolve it first. If it resolves outside, then absolute path is returned.
        #    If it resolves inside (e.g. root=/a/b/c, path=../d -> /a/b/d), then relative.
        root_for_traversal = Path("/usr/local/project").absolute()
        wm_trav = WorkspaceManager(root=root_for_traversal)

        # Path that resolves outside after joining with root via workspace_path
        # workspace_path("../../../etc/passwd") -> /usr/local/project/../../../etc/passwd -> /etc/passwd
        self.assertEqual(wm_trav.relative_path("../../../etc/passwd"), Path("/etc/passwd").absolute())

        # Path that resolves inside after joining
        # workspace_path("sub/../file.txt") -> /usr/local/project/sub/../file.txt -> /usr/local/project/file.txt
        self.assertEqual(wm_trav.relative_path("sub/../file.txt"), Path("file.txt"))


if __name__ == "__main__":
    unittest.main()
