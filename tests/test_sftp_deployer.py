import stat
import tempfile
import unittest
from pathlib import Path, PurePosixPath
from types import SimpleNamespace
from unittest.mock import ANY, Mock, call, patch

from services.sftp_deployer import (
    DeploymentPlan,
    ProjectFile,
    apply_deployment_plan,
    build_deployment_plan,
    collect_project_files,
    main,
    normalize_remote_directory,
)


class SFTPDeployerTests(unittest.TestCase):
    def test_collects_site_files_and_skips_secrets_and_tooling(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "index.html").write_text("<h1>site</h1>", encoding="utf-8")
            (root / ".env").write_text("SECRET=value", encoding="utf-8")
            (root / ".env.example").write_text("KEY=replace-me", encoding="utf-8")
            (root / "private.pem").write_text("private-key", encoding="utf-8")
            (root / ".git").mkdir()
            (root / ".git" / "config").write_text("internal", encoding="utf-8")
            (root / "assets").mkdir()
            (root / "assets" / "app.js").write_text("console.log('ok')", encoding="utf-8")

            relative_paths = {
                item.relative_path.as_posix() for item in collect_project_files(root)
            }

        self.assertEqual(
            relative_paths,
            {"index.html", ".env.example", "assets/app.js"},
        )

    def test_rejects_unsafe_remote_directories(self):
        for directory in ("public_html", "/", "/home/site/../other", "/public_html\\.."):
            with self.subTest(directory=directory):
                with self.assertRaises(ValueError):
                    normalize_remote_directory(directory)

        self.assertEqual(normalize_remote_directory("/home/site/public_html/"), "/home/site/public_html")

    def test_plan_identifies_overwrites_and_missing_directories(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "index.html").write_text("new home page", encoding="utf-8")
            (root / "assets").mkdir()
            (root / "assets" / "app.js").write_text("new script", encoding="utf-8")
            files = collect_project_files(root)

            sftp = Mock()
            remote_entries = {
                "/": stat.S_IFDIR,
                "/public_html": stat.S_IFDIR,
                "/public_html/index.html": stat.S_IFREG,
            }

            def lstat(path):
                mode = remote_entries.get(path)
                if mode is None:
                    raise FileNotFoundError(path)
                return SimpleNamespace(st_mode=mode)

            sftp.lstat.side_effect = lstat
            plan = build_deployment_plan(sftp, files, "/public_html")

        self.assertEqual([path.as_posix() for path in plan.conflicts], ["index.html"])
        self.assertIn("/public_html/assets", plan.missing_directories)

    def test_plan_rejects_remote_symlink(self):
        project_file = ProjectFile(
            source=Path("index.html"),
            relative_path=PurePosixPath("index.html"),
            size=10,
        )
        sftp = Mock()
        sftp.lstat.side_effect = lambda path: (
            SimpleNamespace(st_mode=stat.S_IFDIR)
            if path in ("/", "/public_html")
            else SimpleNamespace(st_mode=stat.S_IFLNK)
        )

        with self.assertRaisesRegex(ValueError, "symlink"):
            build_deployment_plan(sftp, (project_file,), "/public_html")

    def test_plan_rejects_relative_path_traversal(self):
        project_file = ProjectFile(
            source=Path("outside.html"),
            relative_path=PurePosixPath("../outside.html"),
            size=10,
        )
        with self.assertRaisesRegex(ValueError, "Unsafe project file path"):
            build_deployment_plan(Mock(), (project_file,), "/public_html")

    def test_apply_backups_existing_file_before_upload(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "site"
            root.mkdir()
            (root / "index.html").write_text("new content", encoding="utf-8")
            files = collect_project_files(root)
            sftp = Mock()
            deployment_plan = DeploymentPlan(
                remote_directory="/public_html",
                files=files,
                conflicts=(files[0].relative_path,),
                missing_directories=(),
            )
            sftp.get.side_effect = lambda remote, local: Path(local).write_text(
                "old content", encoding="utf-8"
            )

            with patch(
                "services.sftp_deployer._backup_directory",
                return_value=Path(temp_dir) / "backups",
            ):
                uploaded, backup_directory = apply_deployment_plan(
                    sftp,
                    root,
                    deployment_plan,
                )

            self.assertEqual(uploaded, 1)
            self.assertIsNotNone(backup_directory)
            self.assertEqual(
                (backup_directory / "index.html").read_text(encoding="utf-8"),
                "old content",
            )
            self.assertLess(
                sftp.method_calls.index(call.get("/public_html/index.html", ANY)),
                sftp.method_calls.index(
                    call.put(str(root / "index.html"), "/public_html/index.html")
                ),
            )
            sftp.put.assert_called_once_with(
                str(root / "index.html"),
                "/public_html/index.html",
            )

    @patch("services.sftp_deployer.paramiko.SSHClient")
    @patch("services.sftp_deployer.getpass.getpass", return_value="test-password")
    @patch("builtins.input")
    def test_cancelled_deployment_does_not_write_remote_files(
        self, input_mock, getpass_mock, ssh_client
    ):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "index.html").write_text("<h1>site</h1>", encoding="utf-8")
            sftp = ssh_client.return_value.open_sftp.return_value
            remote_entries = {"/": stat.S_IFDIR, "/public_html": stat.S_IFDIR}

            def lstat(path):
                mode = remote_entries.get(path)
                if mode is None:
                    raise FileNotFoundError(path)
                return SimpleNamespace(st_mode=mode)

            sftp.lstat.side_effect = lstat
            input_mock.side_effect = [
                "hosting.example",
                "22",
                "site-user",
                "1",
                "/public_html",
                "",
            ]

            result = main([str(root)])

        self.assertEqual(result, 0)
        sftp.mkdir.assert_not_called()
        sftp.put.assert_not_called()


if __name__ == "__main__":
    unittest.main()
