"""MusicBrainz lookup service for CD metadata."""

import musicbrainzngs

from audiobook_ripper.core.models import AudiobookMetadata, Track


class MusicBrainzService:
    """Service for looking up CD metadata from MusicBrainz."""

    def __init__(self, app_name: str = "AudiobookRipper", version: str = "0.1.0") -> None:
        """Initialize the MusicBrainz service.

        Args:
            app_name: Application name for API identification
            version: Application version
        """
        musicbrainzngs.set_useragent(app_name, version)

    def lookup_by_disc_id(self, disc_id: str) -> dict | None:
        """Look up album information by MusicBrainz disc ID.

        Args:
            disc_id: The disc ID from discid library

        Returns:
            Dictionary with album/track info, or None if not found
        """
        try:
            result = musicbrainzngs.get_releases_by_discid(
                disc_id,
                includes=["artists", "recordings", "release-groups"],
            )

            if "disc" not in result:
                return None

            disc = result["disc"]
            releases = disc.get("release-list", [])

            if not releases:
                return None

            # Use the first release
            release = releases[0]

            return self._parse_release(release)

        except musicbrainzngs.WebServiceError:
            return None

    def _parse_release(self, release: dict) -> dict:
        """Parse a MusicBrainz release into our format."""
        # Get artist
        artist = ""
        if "artist-credit" in release:
            artists = release["artist-credit"]
            artist_names = []
            for credit in artists:
                if isinstance(credit, dict) and "artist" in credit:
                    artist_names.append(credit["artist"]["name"])
            artist = ", ".join(artist_names)

        # Get year
        year = None
        if "date" in release:
            try:
                year = int(release["date"][:4])
            except (ValueError, TypeError):
                pass

        # Get tracks
        tracks = []
        for medium in release.get("medium-list", []):
            for track in medium.get("track-list", []):
                recording = track.get("recording", {})
                track_info = {
                    "number": int(track.get("number", 0)),
                    "title": recording.get("title", f"Track {track.get('number', '?')}"),
                    "duration": int(recording.get("length", 0)) / 1000,  # ms to seconds
                }
                tracks.append(track_info)

        return {
            "title": release.get("title", ""),
            "artist": artist,
            "year": year,
            "tracks": tracks,
            "release_id": release.get("id"),
        }

    def search_release(self, query: str, limit: int = 10) -> list[dict]:
        """Search for releases by text query.

        Args:
            query: Search query (album title, artist, etc.)
            limit: Maximum number of results

        Returns:
            List of matching releases
        """
        try:
            result = musicbrainzngs.search_releases(
                query,
                limit=limit,
            )

            releases = []
            for release in result.get("release-list", []):
                releases.append(self._parse_release(release))

            return releases

        except musicbrainzngs.WebServiceError:
            return []

    def apply_to_tracks(
        self,
        release_info: dict,
        tracks: list[Track],
    ) -> dict[int, AudiobookMetadata]:
        """Apply release information to track metadata.

        Args:
            release_info: Release info from lookup_by_disc_id or search_release
            tracks: List of Track objects to apply metadata to

        Returns:
            Dictionary mapping track numbers to AudiobookMetadata
        """
        metadata_map: dict[int, AudiobookMetadata] = {}
        release_tracks = release_info.get("tracks", [])

        for track in tracks:
            metadata = AudiobookMetadata(
                album=release_info.get("title", ""),
                artist=release_info.get("artist", ""),
                year=release_info.get("year"),
                track_number=track.number,
                total_tracks=len(tracks),
            )

            # Find matching track info
            for rt in release_tracks:
                if rt.get("number") == track.number:
                    metadata.title = rt.get("title", track.title)
                    break
            else:
                metadata.title = track.title

            metadata_map[track.number] = metadata

        return metadata_map
