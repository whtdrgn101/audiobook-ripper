"""Configuration management for the audiobook ripper."""

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class Config:
    """Application configuration."""

    # Output settings
    output_directory: str = ""
    default_bitrate: int = 192
    filename_template: str = "{track:02d} - {title}"

    # Metadata defaults
    default_genre: str = "Audiobook"
    default_artist: str = ""
    default_narrator: str = ""

    # UI settings
    window_width: int = 900
    window_height: int = 600
    last_drive: str = ""

    # MusicBrainz settings
    auto_lookup: bool = True

    @classmethod
    def get_config_path(cls) -> Path:
        """Get the path to the config file."""
        config_dir = Path.home() / ".audiobook-ripper"
        config_dir.mkdir(exist_ok=True)
        return config_dir / "config.json"

    @classmethod
    def load(cls) -> "Config":
        """Load configuration from disk."""
        config_path = cls.get_config_path()
        if config_path.exists():
            try:
                with open(config_path, encoding="utf-8") as f:
                    data = json.load(f)
                return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
            except (json.JSONDecodeError, OSError):
                pass
        return cls()

    def save(self) -> None:
        """Save configuration to disk."""
        config_path = self.get_config_path()
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, indent=2)

    def get_output_dir(self) -> Path:
        """Get output directory, defaulting to user's Music folder."""
        if self.output_directory:
            return Path(self.output_directory)
        return Path.home() / "Music" / "Audiobooks"

    def format_filename(self, track_number: int, title: str, **kwargs) -> str:
        """Format a filename using the template."""
        # Sanitize title for filesystem
        safe_title = "".join(c for c in title if c not in '<>:"/\\|?*')
        return self.filename_template.format(
            track=track_number,
            title=safe_title,
            **kwargs,
        )
