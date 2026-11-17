"""Read the repository's case-sensitive application mappings."""

import configparser
from dataclasses import dataclass
from pathlib import Path
from typing import override


class MappingError(ValueError):
    """A mapping could not be loaded or resolved."""


class MappingConfig(configparser.ConfigParser):
    @override
    def optionxform(self, optionstr: str) -> str:
        return optionstr


def read_mapping_config(path: Path) -> MappingConfig:
    config = MappingConfig(allow_no_value=True, interpolation=None)
    try:
        with path.open(encoding="utf-8") as stream:
            config.read_file(stream)
    except (OSError, UnicodeError, configparser.Error) as error:
        raise MappingError(f"Could not read mapping {path}: {error}") from error
    return config


def selected_applications(config: MappingConfig) -> list[str]:
    return (
        config.options("applications_to_sync")
        if "applications_to_sync" in config
        else []
    )


@dataclass(frozen=True)
class ApplicationMapping:
    home_paths: tuple[Path, ...]
    xdg_paths: tuple[Path, ...]
    optional_paths: tuple[Path, ...]


def read_application_mapping(path: Path) -> ApplicationMapping:
    config = read_mapping_config(path)

    def paths(section: str) -> tuple[Path, ...]:
        items = (
            tuple(Path(item) for item in config.options(section))
            if section in config
            else ()
        )
        for item in items:
            if not item.parts or item.is_absolute() or ".." in item.parts:
                raise MappingError(f"Invalid relative path in {path}: {item}")
        return items

    home_paths = paths("configuration_files")
    xdg_paths = paths("xdg_configuration_files")
    if not (home_paths or xdg_paths):
        raise MappingError(f"No configuration paths in {path}")
    return ApplicationMapping(
        home_paths, xdg_paths, paths("dotfiles_optional_reference_files")
    )


def application_config_path(directory: Path, name: str) -> Path:
    if Path(name).parts != (name,) or name == "..":
        raise MappingError(f"Invalid application name: {name}")
    return directory / f"{name}.cfg"
