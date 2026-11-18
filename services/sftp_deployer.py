import argparse
import getpass
import os
import posixpath
import stat
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath

import paramiko


_EXCLUDED_DIRS = {
    ".aws",
    ".deploy_backups",
    ".git",
    ".ssh",
    ".venv",
    "__pycache__",
    "node_modules",
    "venv",
}
_EXCLUDED_FILES = {
    ".dockerconfigjson",
    ".netrc",
    ".npmrc",
    ".pypirc",
    ".envrc",
    ".git-credentials",
    "secrets.toml",
    "authorized_keys",
    "credentials.json",
    "id_ecdsa",
    "id_ed25519",
    "id_rsa",
    "known_hosts",
}
_EXCLUDED_SUFFIXES = {".key", ".pem", ".p12", ".pfx", ".ppk"}


@dataclass(frozen=True)
class ProjectFile:
    source: Path
    relative_path: PurePosixPath
    size: int


@dataclass(frozen=True)
class DeploymentPlan:
    remote_directory: str
    files: tuple[ProjectFile, ...]
    conflicts: tuple[PurePosixPath, ...]
    missing_directories: tuple[str, ...]


@dataclass(frozen=True)
class SFTPConnection:
    host: str
    port: int
    username: str
    auth_kwargs: dict[str, str | None]


def _is_sensitive_path(relative_path: Path) -> bool:
    if any(part.casefold() in _EXCLUDED_DIRS for part in relative_path.parts[:-1]):
        return True

    name = relative_path.name.casefold()
    if name in _EXCLUDED_FILES or name.endswith(tuple(_EXCLUDED_SUFFIXES)):
        return True
    if name == ".env" or (name.startswith(".env.") and name != ".env.example"):
        return True
    return False


def collect_project_files(project_directory: str | Path) -> tuple[ProjectFile, ...]:
    root = Path(project_directory).expanduser().resolve(strict=True)
    if not root.is_dir():
        raise ValueError(f"Project path is not a directory: {root}")

    project_files: list[ProjectFile] = []
    for current, directories, filenames in os.walk(root, followlinks=False):
        current_path = Path(current)
        directories[:] = sorted(
            name
            for name in directories
            if name.casefold() not in _EXCLUDED_DIRS
            and not (current_path / name).is_symlink()
        )
        for filename in filenames:
            source = current_path / filename
            if source.is_symlink():
                continue
            relative = source.relative_to(root)
            if _is_sensitive_path(relative):
                continue
            project_files.append(
                ProjectFile(
                    source=source,
                    relative_path=PurePosixPath(*relative.parts),
                    size=source.stat().st_size,
                )
            )

    project_files.sort(key=lambda project_file: project_file.relative_path.as_posix())
    if not project_files:
        raise ValueError("No deployable project files found.")
    return tuple(project_files)


def normalize_remote_directory(directory: str) -> str:
    directory = directory.strip()
    if not directory or not directory.startswith("/"):
        raise ValueError("SFTP target directory must be an absolute path, such as /public_html.")
    if "\x00" in directory or "\\" in directory:
        raise ValueError("SFTP target directory contains an invalid character.")
    if any(part in (".", "..") for part in directory.split("/")):
        raise ValueError("SFTP target directory cannot contain . or .. path segments.")

    normalized = posixpath.normpath(directory)
    if normalized == "/":
        raise ValueError("Refusing to deploy to the SFTP root directory.")
    return normalized


def _lstat_optional(sftp: paramiko.SFTPClient, remote_path: str):
    try:
        return sftp.lstat(remote_path)
    except FileNotFoundError:
        return None


def _remote_ancestors(path: str) -> tuple[str, ...]:
    parts = PurePosixPath(path).parts
    current = ""
    ancestors = []
    for part in parts:
        if part == "/":
            current = "/"
            continue
        current = posixpath.join(current, part)
        ancestors.append(current)
    return tuple(ancestors)


def build_deployment_plan(
    sftp: paramiko.SFTPClient,
    project_files: tuple[ProjectFile, ...],
    remote_directory: str,
) -> DeploymentPlan:
    remote_directory = normalize_remote_directory(remote_directory)
    required_directories = {remote_directory}
    destinations: dict[PurePosixPath, str] = {}

    for project_file in project_files:
        relative_path = project_file.relative_path
        if (
            relative_path.is_absolute()
            or not relative_path.parts
            or any(part in (".", "..") for part in relative_path.parts)
        ):
            raise ValueError(f"Unsafe project file path: {relative_path}")
        destination = posixpath.join(
            remote_directory,
            relative_path.as_posix(),
        )
        destinations[relative_path] = destination
        required_directories.update(_remote_ancestors(posixpath.dirname(destination)))

    missing_directories: list[str] = []
    for directory in sorted(required_directories, key=lambda value: value.count("/")):
        attributes = _lstat_optional(sftp, directory)
        if attributes is None:
            missing_directories.append(directory)
        elif stat.S_ISLNK(attributes.st_mode):
            raise ValueError(f"Refusing to deploy through remote symlink: {directory}")
        elif not stat.S_ISDIR(attributes.st_mode):
            raise NotADirectoryError(f"Remote path component is not a directory: {directory}")

    conflicts: list[PurePosixPath] = []
    for relative_path, destination in destinations.items():
        attributes = _lstat_optional(sftp, destination)
        if attributes is None:
            continue
        if stat.S_ISLNK(attributes.st_mode):
            raise ValueError(f"Refusing to overwrite remote symlink: {destination}")
        if not stat.S_ISREG(attributes.st_mode):
            raise IsADirectoryError(f"Remote destination is not a regular file: {destination}")
        conflicts.append(relative_path)

    return DeploymentPlan(
        remote_directory=remote_directory,
        files=project_files,
        conflicts=tuple(conflicts),
        missing_directories=tuple(missing_directories),
    )


def _backup_directory(project_root: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    return (
        Path.home()
        / ".ai_website_builder"
        / "deploy_backups"
        / f"{project_root.name}-{timestamp}"
    )


def apply_deployment_plan(
    sftp: paramiko.SFTPClient,
    project_root: Path,
    plan: DeploymentPlan,
) -> tuple[int, Path | None]:
    backup_directory = _backup_directory(project_root) if plan.conflicts else None

    if backup_directory is not None:
        for relative_path in plan.conflicts:
            backup_file = backup_directory.joinpath(*relative_path.parts)
            backup_file.parent.mkdir(parents=True, exist_ok=True)
            remote_file = posixpath.join(plan.remote_directory, relative_path.as_posix())
            sftp.get(remote_file, str(backup_file))

    for directory in plan.missing_directories:
        sftp.mkdir(directory)

    try:
        for project_file in plan.files:
            remote_file = posixpath.join(
                plan.remote_directory,
                project_file.relative_path.as_posix(),
            )
            sftp.put(str(project_file.source), remote_file)
    except (OSError, EOFError, paramiko.SSHException) as error:
        backup_message = (
            f" Existing remote files are backed up at {backup_directory}."
            if backup_directory is not None
            else ""
        )
        raise RuntimeError(
            "SFTP upload failed; the remote site may be partially updated."
            + backup_message
        ) from error

    return len(plan.files), backup_directory


def _prompt_connection() -> SFTPConnection:
    host = input("SFTP host: ").strip()
    if not host:
        raise ValueError("SFTP host is required.")

    port_text = input("SFTP port [22]: ").strip() or "22"
    try:
        port = int(port_text)
    except ValueError as error:
        raise ValueError("SFTP port must be an integer.") from error
    if not 1 <= port <= 65535:
        raise ValueError("SFTP port must be between 1 and 65535.")

    username = input("SFTP username: ").strip()
    if not username:
        raise ValueError("SFTP username is required.")

    print("Authentication: [1] password  [2] SSH private key")
    authentication = input("Choose [1/2]: ").strip()
    if authentication == "1":
        return SFTPConnection(
            host,
            port,
            username,
            {"password": getpass.getpass("SFTP password: ")},
        )
    if authentication == "2":
        key_path = Path(input("Private key file path: ").strip()).expanduser()
        if not key_path.is_file():
            raise ValueError(f"Private key file not found: {key_path}")
        passphrase = getpass.getpass("Private key passphrase (leave blank if none): ")
        return SFTPConnection(
            host,
            port,
            username,
            {
                "key_filename": str(key_path),
                "passphrase": passphrase or None,
            },
        )
    raise ValueError("Choose 1 for password or 2 for SSH private key.")


def _print_plan(host: str, port: int, plan: DeploymentPlan) -> None:
    total_size = sum(project_file.size for project_file in plan.files)
    print(f"\nDeploy target: {host}:{port}:{plan.remote_directory}")
    print(f"Files to upload: {len(plan.files)} ({total_size:,} bytes)")
    for project_file in plan.files:
        print(f"  {project_file.relative_path.as_posix()}")
    print(f"Files to back up locally before overwrite: {len(plan.conflicts)}")
    for conflict in plan.conflicts:
        print(f"  {conflict.as_posix()}")
    print("Remote files not present in the project will not be deleted.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Preview and upload a local website project to an SFTP hosting account."
    )
    parser.add_argument("project_directory", help="Path to the local website project directory")
    args = parser.parse_args(argv)

    root = Path(args.project_directory).expanduser().resolve(strict=True)
    project_files = collect_project_files(root)
    connection = _prompt_connection()
    remote_directory = normalize_remote_directory(
        input("Remote website directory [/public_html]: ").strip() or "/public_html"
    )

    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(paramiko.RejectPolicy())
    try:
        client.connect(
            hostname=connection.host,
            port=connection.port,
            username=connection.username,
            timeout=15,
            banner_timeout=15,
            auth_timeout=15,
            allow_agent=False,
            look_for_keys=False,
            **connection.auth_kwargs,
        )
        sftp = client.open_sftp()
        try:
            plan = build_deployment_plan(sftp, project_files, remote_directory)
            _print_plan(connection.host, connection.port, plan)
            if input('\nType "DEPLOY" to create backups and upload these files: ').strip() != "DEPLOY":
                print("Deployment cancelled. No remote files were changed.")
                return 0

            uploaded, backup_directory = apply_deployment_plan(sftp, root, plan)
            print(f"Deployment complete. Uploaded {uploaded} file(s).")
            if backup_directory is not None:
                print(f"Previous remote files backed up locally at: {backup_directory}")
            return 0
        finally:
            sftp.close()
    except paramiko.AuthenticationException as error:
        raise RuntimeError("SFTP authentication failed. Check the username and credential.") from error
    except paramiko.BadHostKeyException as error:
        raise RuntimeError(
            "The SFTP server host key does not match your trusted known_hosts entry."
        ) from error
    except paramiko.SSHException as error:
        raise RuntimeError(
            "SFTP connection failed. Check the host and verify its SSH host key is in known_hosts."
        ) from error
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
