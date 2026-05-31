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

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "path": str(self.path),
            "name": self.name,
            "valid": self.valid,
            "error": self.error,
        }


class ProfileCatalog:
    def __init__(self, profiles_root: Path) -> None:
        self.profiles_root = profiles_root

    def list_profiles(self) -> list[ProfileEntry]:
        entries = [
            self._entry_for_path(path)
            for path in sorted(self.profiles_root.glob("**/profile.yaml"))
        ]
        return entries

    def get_profile_path(self, profile_id: str) -> Path:
        for entry in self.list_profiles():
            if entry.id == profile_id:
                return entry.path
        raise KeyError(f"unknown profile id: {profile_id}")

    def validate_profile(self, profile_id: str) -> ProfileEntry:
        return self._entry_for_path(self.get_profile_path(profile_id))

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
            )
        return ProfileEntry(id=profile_id, path=path, name=name, valid=True)

    def _id_for_path(self, path: Path) -> str:
        relative_parent = path.parent.relative_to(self.profiles_root)
        if str(relative_parent) == ".":
            return path.parent.name
        return "__".join(relative_parent.parts)
