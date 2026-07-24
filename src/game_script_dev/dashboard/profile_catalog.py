from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path

import yaml

from game_script_dev.authoring import scaffold_profile_pack
from game_script_dev.dashboard.structured_actions import mutate_action_source
from game_script_dev.profile_loader import ProfileLoadError, load_profile
from game_script_dev.schema import (
    ProfileValidationError,
    profile_from_mapping,
    validate_profile,
)


class ProfileConflictError(RuntimeError):
    """Raised when a save would overwrite a newer saved Profile."""


class InvalidProfileDraftError(ValueError):
    def __init__(self, errors: list[str]) -> None:
        super().__init__("profile draft is invalid")
        self.errors = errors


@dataclass(frozen=True)
class ProfileEntry:
    id: str
    path: Path
    name: str
    valid: bool
    error: str | None = None
    profile_pack: dict[str, object] | None = None
    notes: str | None = None
    pack_status: str = "not_applicable"
    target: dict[str, object] | None = None
    resolution: dict[str, object] | None = None
    state_count: int = 0
    action_count: int = 0

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "path": str(self.path),
            "name": self.name,
            "valid": self.valid,
            "error": self.error,
            "profile_pack": self.profile_pack,
            "notes": self.notes,
            "pack_status": self.pack_status,
            "target": self.target,
            "resolution": self.resolution,
            "state_count": self.state_count,
            "action_count": self.action_count,
        }


class ProfileCatalog:
    def __init__(self, profiles_root: Path, draft_root: Path | None = None) -> None:
        self.profiles_root = profiles_root
        self.draft_root = draft_root or profiles_root.parent / ".profile-drafts"
        self._cached_entries: list[ProfileEntry] | None = None
        self._cached_signature: tuple[tuple[str, str], ...] | None = None
        self._cached_paths_by_id: dict[str, Path] | None = None
        self._write_lock = threading.RLock()
        self._undo_history: dict[str, list[str]] = {}
        self._redo_history: dict[str, list[str]] = {}

    def list_profiles(self) -> list[ProfileEntry]:
        signature = self._profile_signature()
        if self._cached_entries is not None and self._cached_signature == signature:
            return list(self._cached_entries)
        entries = [
            self._entry_for_path(path)
            for path in sorted(self.profiles_root.glob("**/profile.yaml"))
        ]
        self._cached_entries = entries
        self._cached_signature = signature
        self._cached_paths_by_id = {entry.id: entry.path for entry in entries}
        return list(entries)

    def get_profile_path(self, profile_id: str) -> Path:
        self.list_profiles()
        if self._cached_paths_by_id is not None and profile_id in self._cached_paths_by_id:
            return self._cached_paths_by_id[profile_id]
        raise KeyError(f"unknown profile id: {profile_id}")

    def validate_profile(self, profile_id: str) -> ProfileEntry:
        entry = self._entry_for_path(self.get_profile_path(profile_id))
        if self._cached_entries is not None:
            updated = False
            next_entries: list[ProfileEntry] = []
            for cached_entry in self._cached_entries:
                if cached_entry.id == profile_id:
                    next_entries.append(entry)
                    updated = True
                else:
                    next_entries.append(cached_entry)
            if updated:
                self._cached_entries = next_entries
                if self._cached_paths_by_id is not None:
                    self._cached_paths_by_id[profile_id] = entry.path
                self._cached_signature = self._profile_signature()
                return entry
        self._cached_entries = None
        self._cached_signature = None
        self._cached_paths_by_id = None
        return entry

    def profile_source(self, profile_id: str) -> dict[str, object]:
        path = self.get_profile_path(profile_id)
        source = path.read_text(encoding="utf-8")
        return {
            "profile_id": profile_id,
            "path": str(path),
            "source": source,
            "fingerprint": _source_fingerprint(source),
            "read_only": False,
        }

    def structured_profile(self, profile_id: str) -> dict[str, object]:
        source_record = self.profile_source(profile_id)
        try:
            document = yaml.safe_load(str(source_record["source"]))
        except yaml.YAMLError as error:
            raise ProfileLoadError(f"invalid YAML: {error}") from error
        if not isinstance(document, dict):
            raise ProfileLoadError("profile root must be a mapping")
        return {
            "profile_id": profile_id,
            "path": source_record["path"],
            "fingerprint": source_record["fingerprint"],
            "read_only": False,
            "document": document,
        }

    def create_profile(
        self,
        *,
        profile_id: str,
        name: str,
        game: str,
        mode: str,
        initial_state: str,
    ) -> ProfileEntry:
        profile_id = _required_text(profile_id, "profile_id", 64)
        name = _required_text(name, "name", 120)
        game = _required_text(game, "game", 120)
        mode = _required_text(mode, "mode", 120)
        initial_state = _required_text(initial_state, "initial_state", 64)
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", profile_id):
            raise ValueError(
                "profile_id must contain only lowercase letters, numbers, "
                "underscores, and hyphens"
            )
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", initial_state):
            raise ValueError(
                "initial_state must start with a lowercase letter and contain only "
                "lowercase letters, numbers, and underscores"
            )

        with self._write_lock:
            self.profiles_root.mkdir(parents=True, exist_ok=True)
            pack_dir = self.profiles_root / profile_id
            if pack_dir.exists():
                raise FileExistsError(f"profile destination already exists: {profile_id}")
            temporary_dir = Path(
                tempfile.mkdtemp(prefix=".creating-profile-", dir=self.profiles_root)
            )
            try:
                scaffold_profile_pack(
                    temporary_dir,
                    game=game,
                    mode=mode,
                    name=name,
                    initial_state=initial_state,
                )
                temporary_dir.rename(pack_dir)
            finally:
                if temporary_dir.exists():
                    shutil.rmtree(temporary_dir)

            self._invalidate_cache()
            entry = self.validate_profile(profile_id)
            if not entry.valid:
                raise InvalidProfileDraftError([entry.error or "profile is invalid"])
            return entry

    def get_draft(self, profile_id: str) -> dict[str, object]:
        saved = self.profile_source(profile_id)
        record = self._read_draft_record(profile_id)
        exists = record is not None
        source = str(record["source"]) if record is not None else str(saved["source"])
        version = int(record.get("version", 0)) if record is not None else 0
        base_fingerprint = (
            str(record["base_fingerprint"])
            if record is not None
            else str(saved["fingerprint"])
        )
        validation = self.validate_source(profile_id, source)
        return {
            "profile_id": profile_id,
            "source": source,
            "version": version,
            "draft_fingerprint": _source_fingerprint(source),
            "base_fingerprint": base_fingerprint,
            "saved_fingerprint": saved["fingerprint"],
            "exists": exists,
            "dirty": source != saved["source"],
            "conflict": base_fingerprint != saved["fingerprint"],
            "valid": validation["valid"],
            "errors": validation["errors"],
            "problems": validation["problems"],
            "document": validation["document"],
            "history": {
                "can_undo": bool(self._undo_history.get(profile_id)),
                "can_redo": bool(self._redo_history.get(profile_id)),
            },
        }

    def save_draft(
        self,
        profile_id: str,
        source: str,
        *,
        base_fingerprint: str | None = None,
        expected_version: int | None = None,
        expected_fingerprint: str | None = None,
    ) -> dict[str, object]:
        if not isinstance(source, str):
            raise ValueError("source must be text")
        if len(source.encode("utf-8")) > 2_000_000:
            raise ValueError("profile source must not exceed 2 MB")
        with self._write_lock:
            saved = self.profile_source(profile_id)
            existing = self._read_draft_record(profile_id)
            current_source = (
                str(existing["source"]) if existing is not None else str(saved["source"])
            )
            current_version = int(existing.get("version", 0)) if existing else 0
            _assert_expected_draft(
                current_source,
                current_version,
                expected_version=expected_version,
                expected_fingerprint=expected_fingerprint,
            )
            if base_fingerprint is None:
                base_fingerprint = (
                    str(existing["base_fingerprint"])
                    if existing is not None
                    else str(saved["fingerprint"])
                )
            if not re.fullmatch(r"[0-9a-f]{64}", str(base_fingerprint)):
                raise ValueError("base_fingerprint must be a SHA-256 fingerprint")
            if source == current_source:
                return self.get_draft(profile_id)
            record = {
                "profile_id": profile_id,
                "source": source,
                "base_fingerprint": str(base_fingerprint),
                "version": current_version + 1,
                "updated_at_ns": time.time_ns(),
            }
            _atomic_write_text(
                self._draft_path(profile_id),
                json.dumps(record, ensure_ascii=False),
            )
            self._undo_history.pop(profile_id, None)
            self._redo_history.pop(profile_id, None)
            return self.get_draft(profile_id)

    def mutate_actions(
        self,
        profile_id: str,
        mutation: dict[str, object],
        *,
        expected_version: int | None,
        expected_fingerprint: str | None = None,
    ) -> dict[str, object]:
        with self._write_lock:
            draft = self.get_draft(profile_id)
            source = str(draft["source"])
            version = int(draft["version"])
            _assert_expected_draft(
                source,
                version,
                expected_version=expected_version,
                expected_fingerprint=expected_fingerprint,
                required=True,
            )
            updated = mutate_action_source(source, mutation)
            if updated == source:
                return draft
            self._undo_history.setdefault(profile_id, []).append(source)
            self._undo_history[profile_id] = self._undo_history[profile_id][-100:]
            self._redo_history.pop(profile_id, None)
            self._write_structured_draft(
                profile_id,
                updated,
                base_fingerprint=str(draft["base_fingerprint"]),
                version=version + 1,
            )
            return self.get_draft(profile_id)

    def undo_actions(
        self,
        profile_id: str,
        *,
        expected_version: int | None,
        expected_fingerprint: str | None = None,
    ) -> dict[str, object]:
        return self._restore_action_history(
            profile_id,
            undo=True,
            expected_version=expected_version,
            expected_fingerprint=expected_fingerprint,
        )

    def redo_actions(
        self,
        profile_id: str,
        *,
        expected_version: int | None,
        expected_fingerprint: str | None = None,
    ) -> dict[str, object]:
        return self._restore_action_history(
            profile_id,
            undo=False,
            expected_version=expected_version,
            expected_fingerprint=expected_fingerprint,
        )

    def _restore_action_history(
        self,
        profile_id: str,
        *,
        undo: bool,
        expected_version: int | None,
        expected_fingerprint: str | None,
    ) -> dict[str, object]:
        with self._write_lock:
            draft = self.get_draft(profile_id)
            source = str(draft["source"])
            version = int(draft["version"])
            _assert_expected_draft(
                source,
                version,
                expected_version=expected_version,
                expected_fingerprint=expected_fingerprint,
                required=True,
            )
            source_history = (
                self._undo_history if undo else self._redo_history
            ).setdefault(profile_id, [])
            if not source_history:
                raise ValueError(f"nothing to {'undo' if undo else 'redo'}")
            target = source_history.pop()
            destination = self._redo_history if undo else self._undo_history
            destination.setdefault(profile_id, []).append(source)
            self._write_structured_draft(
                profile_id,
                target,
                base_fingerprint=str(draft["base_fingerprint"]),
                version=version + 1,
            )
            return self.get_draft(profile_id)

    def _write_structured_draft(
        self,
        profile_id: str,
        source: str,
        *,
        base_fingerprint: str,
        version: int,
    ) -> None:
        record = {
            "profile_id": profile_id,
            "source": source,
            "base_fingerprint": base_fingerprint,
            "version": version,
            "updated_at_ns": time.time_ns(),
        }
        _atomic_write_text(
            self._draft_path(profile_id),
            json.dumps(record, ensure_ascii=False),
        )

    def discard_draft(self, profile_id: str) -> dict[str, object]:
        self.get_profile_path(profile_id)
        with self._write_lock:
            self._draft_path(profile_id).unlink(missing_ok=True)
            self._undo_history.pop(profile_id, None)
            self._redo_history.pop(profile_id, None)
        return self.get_draft(profile_id)

    def validate_source(self, profile_id: str, source: str) -> dict[str, object]:
        profile_path = self.get_profile_path(profile_id)
        errors: list[str] = []
        document: dict[str, object] | None = None
        try:
            raw = yaml.safe_load(source)
            if not isinstance(raw, dict):
                raise ProfileLoadError("profile root must be a mapping")
            document = raw
            profile = profile_from_mapping(raw)
            validate_profile(profile, profile_path.parent)
        except yaml.YAMLError as error:
            errors.append(f"invalid YAML: {error}")
        except (ProfileLoadError, ProfileValidationError, TypeError, ValueError) as error:
            errors.append(str(error))
        return {
            "valid": not errors,
            "errors": errors,
            "problems": _problems_from_errors(errors),
            "document": _json_safe(document) if document is not None else None,
        }

    def save_profile(self, profile_id: str) -> ProfileEntry:
        with self._write_lock:
            draft_record = self._read_draft_record(profile_id)
            if draft_record is None:
                raise ValueError("no recoverable draft exists for this profile")
            saved = self.profile_source(profile_id)
            base_fingerprint = str(draft_record["base_fingerprint"])
            if base_fingerprint != saved["fingerprint"]:
                raise ProfileConflictError(
                    "profile.yaml changed outside the application; the draft was preserved"
                )
            source = str(draft_record["source"])
            validation = self.validate_source(profile_id, source)
            if not validation["valid"]:
                raise InvalidProfileDraftError(list(validation["errors"]))

            profile_path = self.get_profile_path(profile_id)
            if source != saved["source"]:
                self._retain_revision(profile_id, str(saved["source"]))
                _atomic_write_text(profile_path, source)
            self._draft_path(profile_id).unlink(missing_ok=True)
            self._undo_history.pop(profile_id, None)
            self._redo_history.pop(profile_id, None)
            self._invalidate_cache()
            return self.validate_profile(profile_id)

    def _draft_path(self, profile_id: str) -> Path:
        digest = hashlib.sha256(profile_id.encode("utf-8")).hexdigest()
        return self.draft_root / "profiles" / f"{digest}.json"

    def _read_draft_record(self, profile_id: str) -> dict[str, object] | None:
        path = self._draft_path(profile_id)
        if not path.is_file():
            return None
        record = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(record, dict) or record.get("profile_id") != profile_id:
            raise OSError(f"invalid recoverable draft record for {profile_id}")
        if not isinstance(record.get("source"), str):
            raise OSError(f"invalid recoverable draft source for {profile_id}")
        version = record.get("version", 0)
        if not isinstance(version, int) or isinstance(version, bool) or version < 0:
            raise OSError(f"invalid recoverable draft version for {profile_id}")
        return record

    def _retain_revision(self, profile_id: str, source: str) -> None:
        profile_key = hashlib.sha256(profile_id.encode("utf-8")).hexdigest()
        revision_root = self.draft_root / "revisions" / profile_key
        fingerprint = _source_fingerprint(source)[:12]
        revision_path = revision_root / f"{time.time_ns()}-{fingerprint}.yaml"
        _atomic_write_text(revision_path, source)
        revisions = sorted(revision_root.glob("*.yaml"), reverse=True)
        for old_revision in revisions[10:]:
            old_revision.unlink(missing_ok=True)

    def _invalidate_cache(self) -> None:
        self._cached_entries = None
        self._cached_signature = None
        self._cached_paths_by_id = None

    def _entry_for_path(self, path: Path) -> ProfileEntry:
        profile_id = self._id_for_path(path)
        name = path.parent.name
        try:
            profile = load_profile(path)
            name = profile.name
            validate_profile(profile, path.parent)
        except (ProfileLoadError, ProfileValidationError) as error:
            return ProfileEntry(
                id=profile_id,
                path=path,
                name=name,
                valid=False,
                error=str(error),
                notes=_read_notes(path.parent),
                pack_status="invalid",
            )
        profile_pack = None
        pack_status = "not_applicable"
        if profile.profile_pack is not None:
            profile_pack = {
                "game": profile.profile_pack.game,
                "game_mode": profile.profile_pack.game_mode,
                "detection_strategy": profile.profile_pack.detection_strategy,
                "known_limitations": profile.profile_pack.known_limitations,
                "compatibility": profile.profile_pack.compatibility,
                "missing_compatibility_checks": (
                    profile.profile_pack.missing_compatibility_checks
                ),
            }
            pack_status = (
                "complete" if profile.profile_pack.compatibility_complete else "incomplete"
            )
        return ProfileEntry(
            id=profile_id,
            path=path,
            name=name,
            valid=True,
            profile_pack=profile_pack,
            notes=_read_notes(path.parent),
            pack_status=pack_status,
            target={
                "process_name": profile.target.process_name,
                "window_title_contains": profile.target.window_title_contains,
                "input_mode": profile.target.input_mode,
            },
            resolution={
                "width": profile.resolution.width,
                "height": profile.resolution.height,
                "policy": profile.resolution.policy,
            },
            state_count=len(profile.states),
            action_count=sum(len(state.actions) for state in profile.states.values()),
        )

    def _id_for_path(self, path: Path) -> str:
        relative_parent = path.parent.relative_to(self.profiles_root)
        if str(relative_parent) == ".":
            return path.parent.name
        return "__".join(relative_parent.parts)

    def _profile_signature(self) -> tuple[tuple[str, str], ...]:
        signature: list[tuple[str, str]] = []
        for path in sorted(self.profiles_root.glob("**/profile.yaml")):
            stat = path.stat()
            signature.append((str(path), str(stat.st_mtime_ns)))
            notes_path = path.parent / "notes.md"
            if notes_path.is_file():
                notes_stat = notes_path.stat()
                signature.append((str(notes_path), str(notes_stat.st_mtime_ns)))
        return tuple(signature)


def _read_notes(profile_dir: Path) -> str | None:
    notes_path = profile_dir / "notes.md"
    if not notes_path.is_file():
        return None
    return notes_path.read_text(encoding="utf-8")


def _source_fingerprint(source: str) -> str:
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def _assert_expected_draft(
    source: str,
    version: int,
    *,
    expected_version: int | None,
    expected_fingerprint: str | None,
    required: bool = False,
) -> None:
    if required and expected_version is None and expected_fingerprint is None:
        raise ValueError(
            "expected_version or expected_fingerprint is required"
        )
    if expected_version is not None:
        if (
            not isinstance(expected_version, int)
            or isinstance(expected_version, bool)
            or expected_version < 0
        ):
            raise ValueError("expected_version must be a non-negative integer")
        if expected_version != version:
            raise ProfileConflictError(
                "Profile Draft changed before this edit; reload the newer Draft"
            )
    if expected_fingerprint is not None:
        if not re.fullmatch(r"[0-9a-f]{64}", expected_fingerprint):
            raise ValueError(
                "expected_fingerprint must be a SHA-256 fingerprint"
            )
        if expected_fingerprint != _source_fingerprint(source):
            raise ProfileConflictError(
                "Profile Draft changed before this edit; reload the newer Draft"
            )


def _problems_from_errors(errors: list[str]) -> list[dict[str, str]]:
    problems: list[dict[str, str]] = []
    for combined in errors:
        for message in combined.split("; "):
            location = ""
            match = re.search(
                r"state '([^']+)' actions\[(\d+)\]\.([a-zA-Z0-9_]+)"
                r"(?:\.([a-zA-Z0-9_]+))?",
                message,
            )
            if match:
                state_name, index, action_type, field_name = match.groups()
                location = f"states.{state_name}.actions[{index}]"
                if field_name:
                    location += f".{field_name}"
                elif action_type:
                    location += f".{action_type}"
            problems.append(
                {
                    "severity": "error",
                    "message": message,
                    "location": location,
                }
            )
    return problems


def _required_text(value: str, field_name: str, max_length: int) -> str:
    value = str(value).strip()
    if not value:
        raise ValueError(f"{field_name} is required")
    if len(value) > max_length:
        raise ValueError(f"{field_name} must not exceed {max_length} characters")
    return value


def _atomic_write_text(path: Path, source: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_name(f".{path.name}.{time.time_ns()}.tmp")
    try:
        temporary_path.write_text(source, encoding="utf-8")
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)


def _json_safe(document: dict[str, object]) -> dict[str, object]:
    return json.loads(json.dumps(document, default=str))
