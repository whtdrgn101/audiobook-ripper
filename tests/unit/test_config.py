"""Tests for configuration management."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch

from audiobook_ripper.utils.config import Config


class TestConfig:
    """Tests for Config class."""

    def test_default_values(self):
        """Test default configuration values."""
        config = Config()

        assert config.default_bitrate == 192
        assert config.default_genre == "Audiobook"
        assert config.auto_lookup is True
        assert config.filename_template == "{track:02d} - {title}"

    def test_get_output_dir_default(self):
        """Test default output directory."""
        config = Config()
        config.output_directory = ""

        output_dir = config.get_output_dir()

        assert "Music" in str(output_dir)
        assert "Audiobooks" in str(output_dir)

    def test_get_output_dir_custom(self, tmp_path):
        """Test custom output directory."""
        config = Config()
        custom_path = str(tmp_path / "custom" / "path")
        config.output_directory = custom_path

        output_dir = config.get_output_dir()

        assert str(output_dir) == custom_path

    def test_format_filename_basic(self):
        """Test basic filename formatting."""
        config = Config()
        config.filename_template = "{track:02d} - {title}"

        filename = config.format_filename(5, "Test Title")

        assert filename == "05 - Test Title"

    def test_format_filename_sanitizes_title(self):
        """Test that filename formatting sanitizes invalid characters."""
        config = Config()

        filename = config.format_filename(1, 'Invalid: "Title" <here>')

        assert ":" not in filename
        assert '"' not in filename
        assert "<" not in filename
        assert ">" not in filename

    def test_save_and_load(self, tmp_path):
        """Test saving and loading configuration."""
        with patch.object(Config, "get_config_path", return_value=tmp_path / "config.json"):
            # Save
            config = Config()
            config.default_bitrate = 320
            config.default_artist = "Test Author"
            config.save()

            # Load
            loaded = Config.load()

            assert loaded.default_bitrate == 320
            assert loaded.default_artist == "Test Author"

    def test_load_missing_file(self, tmp_path):
        """Test loading when config file doesn't exist."""
        with patch.object(Config, "get_config_path", return_value=tmp_path / "nonexistent.json"):
            config = Config.load()

            # Should return default config
            assert config.default_bitrate == 192

    def test_load_invalid_json(self, tmp_path):
        """Test loading with invalid JSON."""
        config_path = tmp_path / "config.json"
        config_path.write_text("invalid json {{{")

        with patch.object(Config, "get_config_path", return_value=config_path):
            config = Config.load()

            # Should return default config
            assert config.default_bitrate == 192

    def test_load_ignores_unknown_fields(self, tmp_path):
        """Test that loading ignores unknown fields."""
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps({
            "default_bitrate": 256,
            "unknown_field": "should be ignored"
        }))

        with patch.object(Config, "get_config_path", return_value=config_path):
            config = Config.load()

            assert config.default_bitrate == 256
            assert not hasattr(config, "unknown_field")
