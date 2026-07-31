from __future__ import annotations

import json
import os
import shutil
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml
from PIL import Image

from game_script_dev.authoring import check_profile_pack

IMAGE_SUFFIXES = {
    ".bmp",
    ".gif",
    ".jpeg",
    ".jpg",
    ".png",
    ".ppm",
    ".tif",
    ".tiff",
    ".webp",
}
SOURCE_SCRIPT_SUFFIXES = {
    ".ahk",
    ".bat",
    ".cmd",
    ".js",
    ".lua",
    ".ps1",
    ".py",
    ".sh",
    ".ts",
}
PACK_DOCUMENTS = ("notes.md", "workflow.md", "input-reconstruction.md")
IGNORED_DIRECTORIES = {".git", ".hg", ".svn", ".venv", "__pycache__", "node_modules"}


class DistillationError(ValueError):
    """Raised when repository distillation cannot run safely."""


@dataclass(frozen=True)
class DistillationItem:
    category: str
    source: str
    destination: str | None
    reason: str


@dataclass
class DistillationReport:
    source_repository: str
    workspace: str
    destination: str
    applied: bool
    items: list[DistillationItem] = field(default_factory=list)

    @property
    def summary(self) -> dict[str, int]:
        counts = {
            category: 0
            for category in ("imported", "converted", "skipped", "removed", "failed")
        }
        for item in self.items:
            counts[item.category] += 1
        return counts

    @property
    def ok(self) -> bool:
        return not self.summary["failed"] and not self.summary["removed"]

    def to_dict(self) -> dict[str, object]:
        return {
            "version": 1,
            "source_repository": self.source_repository,
            "workspace": self.workspace,
            "destination": self.destination,
            "applied": self.applied,
            "ok": self.ok,
            "summary": self.summary,
            "items": [asdict(item) for item in self.items],
        }


def distill_repository(
    source_repository: Path,
    workspace: Path,
    destination: Path,
    *,
    apply: bool = False,
) -> DistillationReport:
    source_root = source_repository.resolve()
    workspace_root = workspace.resolve()
    destination_root = _resolve_inside(workspace_root, destination, "destination")
    _validate_roots(source_root, workspace_root, destination_root)

    report = DistillationReport(
        source_repository=str(source_root),
        workspace=str(workspace_root),
        destination=str(destination_root),
        applied=apply,
    )
    files = list(_inventory_files(source_root, report))
    candidates = sorted(path for path in files if path.name.lower() == "profile.yaml")
    source_scripts = [
        path for path in files if path.suffix.lower() in SOURCE_SCRIPT_SUFFIXES
    ]
    if source_scripts:
        report.items.append(
            DistillationItem(
                category="skipped",
                source=".",
                destination=None,
                reason=(
                    f"{len(source_scripts)} executable source script(s) inventoried but "
                    "not executed or semantically translated"
                ),
            )
        )
    if not candidates:
        report.items.append(
            DistillationItem(
                category="failed",
                source=".",
                destination=None,
                reason="no declarative profile.yaml candidates were found",
            )
        )
        return report

    target_paths: set[Path] = set()
    for profile_path in candidates:
        pack_relative = _pack_relative_path(source_root, profile_path.parent)
        target_pack = destination_root / pack_relative
        if target_pack in target_paths:
            report.items.append(
                DistillationItem(
                    category="failed",
                    source=_relative_text(profile_path, source_root),
                    destination=_relative_text(target_pack, workspace_root),
                    reason="multiple source profiles map to the same destination pack",
                )
            )
            continue
        target_paths.add(target_pack)
        _distill_pack(
            profile_path,
            source_root,
            workspace_root,
            target_pack,
            apply,
            report,
        )
    return report


def write_distillation_report(
    report: DistillationReport,
    report_path: Path,
    *,
    overwrite: bool = False,
) -> Path:
    path = validate_distillation_report_path(
        Path(report.workspace),
        Path(report.destination),
        report_path,
        overwrite=overwrite,
    )
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(report.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    except OSError as error:
        raise DistillationError(f"report could not be written: {error}") from error
    return path


def validate_distillation_report_path(
    workspace: Path,
    destination: Path,
    report_path: Path,
    *,
    overwrite: bool = False,
) -> Path:
    workspace_root = workspace.resolve()
    destination_root = _resolve_inside(workspace_root, destination, "destination")
    path = _resolve_inside(workspace_root, report_path, "report")
    if path.is_relative_to(destination_root):
        raise DistillationError("report must be outside the destination directory")
    if path.exists() and not overwrite:
        raise DistillationError(f"report already exists: {path}")
    return path


def format_distillation_report(report: DistillationReport) -> str:
    mode = "APPLY" if report.applied else "DRY RUN"
    lines = [
        f"Repository distillation {mode}: {'ok' if report.ok else 'failed'}",
        f"Source: {report.source_repository}",
        f"Workspace: {report.workspace}",
        f"Destination: {report.destination}",
        "Summary: "
        + ", ".join(
            f"{category}={count}" for category, count in report.summary.items()
        ),
    ]
    for item in report.items:
        prefix = (
            "WOULD "
            if not report.applied and item.category in {"imported", "converted"}
            else ""
        )
        destination = f" -> {item.destination}" if item.destination else ""
        lines.append(
            f"{prefix}{item.category.upper()}: {item.source}{destination}: {item.reason}"
        )
    return "\n".join(lines)


def _distill_pack(
    profile_path: Path,
    source_root: Path,
    workspace_root: Path,
    target_pack: Path,
    apply: bool,
    report: DistillationReport,
) -> None:
    source_label = _relative_text(profile_path, source_root)
    destination_label = _relative_text(target_pack / "profile.yaml", workspace_root)
    if target_pack.exists():
        report.items.append(
            DistillationItem(
                category="failed",
                source=source_label,
                destination=destination_label,
                reason="destination pack already exists; overwriting is not allowed",
            )
        )
        return

    try:
        raw = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as error:
        report.items.append(
            DistillationItem(
                category="failed",
                source=source_label,
                destination=destination_label,
                reason=f"profile could not be read: {error}",
            )
        )
        return
    if not isinstance(raw, dict):
        report.items.append(
            DistillationItem(
                category="failed",
                source=source_label,
                destination=destination_label,
                reason="profile.yaml must contain a YAML mapping",
            )
        )
        return

    action_count = _count_actions(raw)
    if action_count == 0:
        report.items.append(
            DistillationItem(
                category="removed",
                source=source_label,
                destination=destination_label,
                reason=(
                    "profile has no state Actions or interruption recovery Actions; "
                    "the empty generated profile was rejected before destination write"
                ),
            )
        )
        return

    with tempfile.TemporaryDirectory(prefix="game-script-dev-distill-") as temp_dir:
        staged_pack = Path(temp_dir) / "pack"
        staged_pack.mkdir()
        pack_items: list[DistillationItem] = []
        try:
            _stage_pack(
                profile_path.parent,
                raw,
                source_root,
                workspace_root,
                target_pack,
                staged_pack,
                pack_items,
            )
            check = check_profile_pack(staged_pack)
        except (OSError, ValueError, yaml.YAMLError) as error:
            report.items.append(
                DistillationItem(
                    category="failed",
                    source=source_label,
                    destination=destination_label,
                    reason=f"pack transformation failed: {error}",
                )
            )
            return
        if not check.ok:
            report.items.append(
                DistillationItem(
                    category="failed",
                    source=source_label,
                    destination=destination_label,
                    reason="distilled pack validation failed: "
                    + "; ".join(check.errors),
                )
            )
            return

        if apply:
            pending_root: Path | None = None
            try:
                target_pack.parent.mkdir(parents=True, exist_ok=True)
                pending_root = Path(
                    tempfile.mkdtemp(prefix=".distillation-", dir=target_pack.parent)
                )
                pending_pack = pending_root / "pack"
                shutil.copytree(staged_pack, pending_pack)
                pending_pack.replace(target_pack)
            except OSError as error:
                report.items.append(
                    DistillationItem(
                        category="failed",
                        source=source_label,
                        destination=destination_label,
                        reason=f"destination write failed and was rolled back: {error}",
                    )
                )
                return
            finally:
                if pending_root is not None:
                    shutil.rmtree(pending_root, ignore_errors=True)
        report.items.extend(pack_items)


def _stage_pack(
    source_pack: Path,
    raw: dict[str, Any],
    source_root: Path,
    workspace_root: Path,
    target_pack: Path,
    staged_pack: Path,
    items: list[DistillationItem],
) -> None:
    images = _pack_images(source_pack, raw)
    replacements: dict[str, str] = {}
    destinations: set[Path] = set()
    for image_path in images:
        relative = image_path.relative_to(source_pack)
        output_relative = relative.with_suffix(".png")
        if output_relative in destinations:
            raise ValueError(
                f"image conversion collision at {output_relative.as_posix()}"
            )
        destinations.add(output_relative)
        output_path = staged_pack / output_relative
        output_path.parent.mkdir(parents=True, exist_ok=True)
        source_suffix = image_path.suffix.lower()
        if source_suffix == ".png":
            shutil.copy2(image_path, output_path)
            category = "imported"
            reason = "copied retained PNG image"
        else:
            with Image.open(image_path) as image:
                image.save(output_path, format="PNG")
            category = "converted"
            reason = f"converted {source_suffix.lstrip('.').upper()} image to PNG"
        source_reference = relative.as_posix()
        replacements[source_reference] = output_relative.as_posix()
        items.append(
            DistillationItem(
                category=category,
                source=_relative_text(image_path, source_root),
                destination=_relative_text(
                    target_pack / output_relative,
                    workspace_root,
                ),
                reason=reason,
            )
        )

    transformed = _replace_image_references(raw, replacements)
    (staged_pack / "profile.yaml").write_text(
        yaml.safe_dump(transformed, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    items.append(
        DistillationItem(
            category="imported",
            source=_relative_text(source_pack / "profile.yaml", source_root),
            destination=_relative_text(target_pack / "profile.yaml", workspace_root),
            reason="validated declarative profile",
        )
    )

    for document_name in PACK_DOCUMENTS:
        source_document = source_pack / document_name
        if source_document.is_file() and not source_document.is_symlink():
            shutil.copy2(source_document, staged_pack / document_name)
            items.append(
                DistillationItem(
                    category="imported",
                    source=_relative_text(source_document, source_root),
                    destination=_relative_text(
                        target_pack / document_name,
                        workspace_root,
                    ),
                    reason="copied profile-pack documentation",
                )
            )
    notes_path = staged_pack / "notes.md"
    if not notes_path.exists():
        notes_path.write_text(
            "# Distilled Profile\n\n"
            "Imported from an explicitly selected local repository. Review all "
            "compatibility evidence and limitations before live use.\n",
            encoding="utf-8",
        )
        items.append(
            DistillationItem(
                category="imported",
                source=_relative_text(source_pack, source_root),
                destination=_relative_text(target_pack / "notes.md", workspace_root),
                reason="generated required profile-pack notes",
            )
        )

    for relative_dir in (
        Path("assets"),
        Path("validation_examples") / "valid",
        Path("validation_examples") / "invalid",
    ):
        directory = staged_pack / relative_dir
        directory.mkdir(parents=True, exist_ok=True)
        if not any(directory.iterdir()):
            (directory / ".gitkeep").write_text("", encoding="utf-8")


def _pack_images(source_pack: Path, raw: dict[str, Any]) -> list[Path]:
    images: set[Path] = set()
    for directory_name in ("assets", "validation_examples"):
        directory = source_pack / directory_name
        if directory.is_dir() and not directory.is_symlink():
            for path in directory.rglob("*"):
                if (
                    path.is_file()
                    and not path.is_symlink()
                    and path.suffix.lower() in IMAGE_SUFFIXES
                ):
                    images.add(path)
    for reference in _string_values(raw):
        if Path(reference).suffix.lower() not in IMAGE_SUFFIXES:
            continue
        candidate = (source_pack / reference.replace("\\", "/")).resolve()
        if not candidate.is_relative_to(source_pack.resolve()):
            raise ValueError(f"image reference escapes source pack: {reference}")
        if candidate.is_file() and not candidate.is_symlink():
            images.add(candidate)
    return sorted(images)


def _replace_image_references(
    value: Any,
    replacements: dict[str, str],
) -> Any:
    if isinstance(value, dict):
        return {
            key: _replace_image_references(child, replacements)
            for key, child in value.items()
        }
    if isinstance(value, list):
        return [_replace_image_references(child, replacements) for child in value]
    if isinstance(value, str):
        normalized = value.replace("\\", "/")
        return replacements.get(normalized, value)
    return value


def _string_values(value: Any) -> list[str]:
    if isinstance(value, dict):
        return [text for child in value.values() for text in _string_values(child)]
    if isinstance(value, list):
        return [text for child in value for text in _string_values(child)]
    return [value] if isinstance(value, str) else []


def _count_actions(raw: dict[str, Any]) -> int:
    count = 0
    states = raw.get("states", {})
    if isinstance(states, dict):
        for state in states.values():
            if isinstance(state, dict) and isinstance(state.get("actions"), list):
                count += len(state["actions"])
    interruptions = raw.get("interruptions", [])
    if isinstance(interruptions, list):
        for interruption in interruptions:
            if isinstance(interruption, dict) and isinstance(
                interruption.get("recovery_actions"), list
            ):
                count += len(interruption["recovery_actions"])
    return count


def _inventory_files(
    source_root: Path,
    report: DistillationReport,
) -> list[Path]:
    files: list[Path] = []
    for root, directory_names, file_names in os.walk(source_root, followlinks=False):
        root_path = Path(root)
        kept_directories: list[str] = []
        for name in sorted(directory_names):
            path = root_path / name
            if name in IGNORED_DIRECTORIES:
                continue
            if path.is_symlink():
                report.items.append(
                    DistillationItem(
                        category="skipped",
                        source=_relative_text(path, source_root),
                        destination=None,
                        reason="symbolic-link directory was not followed",
                    )
                )
                continue
            kept_directories.append(name)
        directory_names[:] = kept_directories
        for name in sorted(file_names):
            path = root_path / name
            if path.is_symlink():
                report.items.append(
                    DistillationItem(
                        category="skipped",
                        source=_relative_text(path, source_root),
                        destination=None,
                        reason="symbolic-link file was not imported",
                    )
                )
                continue
            files.append(path)
    return files


def _pack_relative_path(source_root: Path, source_pack: Path) -> Path:
    relative = source_pack.relative_to(source_root)
    if relative.parts and relative.parts[0].lower() == "profiles":
        relative = Path(*relative.parts[1:])
    return relative


def _validate_roots(
    source_root: Path,
    workspace_root: Path,
    destination_root: Path,
) -> None:
    if not source_root.is_dir():
        raise DistillationError(f"source repository is not a directory: {source_root}")
    if not workspace_root.is_dir():
        raise DistillationError(f"workspace is not a directory: {workspace_root}")
    if source_root == workspace_root:
        raise DistillationError("source repository and workspace must be different")
    if destination_root == workspace_root:
        raise DistillationError("destination must be a directory inside the workspace")
    if destination_root.is_relative_to(source_root):
        raise DistillationError("destination must not be inside the source repository")


def _resolve_inside(root: Path, path: Path, label: str) -> Path:
    root = root.resolve()
    resolved = path.resolve() if path.is_absolute() else (root / path).resolve()
    if not resolved.is_relative_to(root):
        raise DistillationError(f"{label} must stay inside the workspace: {resolved}")
    return resolved


def _relative_text(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix() or "."
    except ValueError:
        return str(path)
