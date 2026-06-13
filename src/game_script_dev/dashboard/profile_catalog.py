from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from game_script_dev.profile_loader import ProfileLoadError, load_profile
from game_script_dev.schema import ProfileValidationError, validate_profile


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
        }


class ProfileCatalog:
    def __init__(self, profiles_root: Path) -> None:
        self.profiles_root = profiles_root
        self._cached_entries: list[ProfileEntry] | None = None
        self._cached_signature: tuple[tuple[str, str], ...] | None = None
        self._cached_paths_by_id: dict[str, Path] | None = None

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
