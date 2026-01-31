# Audiobook CD Ripper

A Windows desktop application for ripping audiobook CDs to MP3 files with proper metadata support.

## Features

- **Single-pass disc ripping**: Rips the entire CD in one operation for maximum speed
- **Combine tracks**: Merge all tracks into a single MP3 file per disc
- **Split tracks**: Keep tracks separate with parallel encoding for speed
- **Metadata support**: Edit title, author, narrator, album, series, and disc information
- **MusicBrainz integration**: Automatic metadata lookup by disc ID
- **Disc numbering**: Proper disc number support for multi-disc audiobooks
- **Cover art support**: Embed cover art in MP3 files
- **Progress tracking**: Real-time progress display during ripping and encoding

## Requirements

- Windows 10 or later
- Python 3.11+
- FFmpeg with libcdio support (for CD ripping)
- libdiscid (for MusicBrainz disc ID lookup)

## Installation

```bash
# Clone the repository
cd audiobook-ripper

# Install with UV
uv sync

# Or install with pip
pip install -e .
```

### FFmpeg Setup

FFmpeg must be in your system PATH with libcdio support for CD ripping.

- Download a full build from [gyan.dev](https://www.gyan.dev/ffmpeg/builds/)
- Or use `choco install ffmpeg`
- Verify: `ffmpeg -version` (should show `--enable-libcdio`)

### libdiscid Setup

Required for MusicBrainz disc ID reading:
- Windows: `choco install libdiscid` or download from [MusicBrainz](https://musicbrainz.org/doc/libdiscid)

## Usage

```bash
# Run with UV
uv run audiobook-ripper

# Or run as module
python -m audiobook_ripper
```

### Basic Workflow

1. Insert an audiobook CD
2. Select your CD drive from the dropdown
3. Click **Lookup** to fetch metadata from MusicBrainz (optional)
4. Edit metadata as needed:
   - Select tracks and click **Edit Metadata...** for full editing
   - Use **Batch Edit...** to apply changes to multiple tracks
5. Check **Combine into single file** for a single MP3 per disc
6. Click **Rip Selected Tracks**
7. If combining, enter the filename and disc number in the dialog
8. Wait for ripping and encoding to complete

### Output

- **Combined mode**: Creates `"Album Name - Disc 01.mp3"` with disc metadata
- **Split mode**: Creates individual track files like `"01 - Track Title.mp3"`

## Configuration

Settings are accessible via the **Settings** button and stored in `~/.audiobook-ripper/config.json`:

- Output directory
- Default MP3 bitrate (128-320 kbps)
- MusicBrainz auto-lookup

## Development

### Running Tests

```bash
# Run all tests with coverage
uv run pytest

# Run with verbose output
uv run pytest -v

# Generate HTML coverage report
uv run pytest --cov-report=html
```

### Project Structure

```
audiobook-ripper/
├── src/audiobook_ripper/
│   ├── core/           # Data models, interfaces, DI container
│   ├── services/       # CD drive, ripper, encoder, metadata services
│   ├── ui/             # Qt widgets and dialogs
│   └── utils/          # Configuration utilities
└── tests/
    ├── unit/           # Unit tests
    └── integration/    # UI integration tests
```

## License

BSD 3-Clause License. See [LICENSE.md](LICENSE.md) for details.
