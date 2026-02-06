#!/usr/bin/env python3
"""
Duplicate Detection Script

Scans all files recursively, identifies exact duplicates (by content hash)
and visually similar images (by perceptual hash), then provides an interactive
Panel web app with Plotly image display for reviewing and handling duplicates.

Usage:
    python find_duplicates.py "C:\\path\\to\\directory"
    python find_duplicates.py "C:\\path\\to\\directory" --dry-run
    python find_duplicates.py "C:\\path\\to\\directory" --exact-only
    python find_duplicates.py "C:\\path\\to\\directory" --similar-only
    python find_duplicates.py "C:\\path\\to\\directory" --threshold 5
    python find_duplicates.py "C:\\path\\to\\directory" --report-only
"""

import os
import hashlib
import argparse
import base64
import shutil
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

# Optional imports for image hashing and interactive mode
try:
    import imagehash
    from PIL import Image

    IMAGEHASH_AVAILABLE = True
except ImportError:
    IMAGEHASH_AVAILABLE = False

try:
    import panel as pn
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    INTERACTIVE_AVAILABLE = True
except ImportError:
    INTERACTIVE_AVAILABLE = False


# Files to exclude from duplicate detection
EXCLUDED_FILES = {
    "rename_files.py",
    "unzip_all.py",
    "find_duplicates.py",
    ".gitignore",
    ".python-version",
}

# Directories to exclude from scanning
EXCLUDED_DIRS = {".venv", "venv", "__pycache__", ".git", "node_modules"}

# Image extensions for perceptual hashing
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}

# Chunk size for reading large files (8MB)
CHUNK_SIZE = 8 * 1024 * 1024


@dataclass
class FileInfo:
    """Information about a file for duplicate detection."""

    path: Path
    size: int
    modified: datetime
    content_hash: Optional[str] = None
    perceptual_hash: Optional[str] = None


@dataclass
class DuplicateGroup:
    """A group of duplicate files."""

    group_type: str  # "exact" or "similar"
    files: list[FileInfo] = field(default_factory=list)
    similarity: Optional[int] = None  # For similar images, the hash distance


def get_content_hash(file_path: Path) -> str:
    """
    Calculate SHA256 hash of file contents using chunked reading.

    Args:
        file_path: Path to the file to hash.

    Returns:
        Hex string of the SHA256 hash.
    """
    sha256 = hashlib.sha256()

    with open(file_path, "rb") as f:
        while chunk := f.read(CHUNK_SIZE):
            sha256.update(chunk)

    return sha256.hexdigest()


def get_perceptual_hash(file_path: Path) -> Optional[str]:
    """
    Calculate perceptual hash for an image file.

    Args:
        file_path: Path to the image file.

    Returns:
        String representation of the perceptual hash, or None if not an image
        or hashing failed.
    """
    if not IMAGEHASH_AVAILABLE:
        return None

    if file_path.suffix.lower() not in IMAGE_EXTENSIONS:
        return None

    try:
        with Image.open(file_path) as img:
            return str(imagehash.phash(img))
    except Exception:
        return None


def scan_files(root_dir: Path) -> list[FileInfo]:
    """
    Recursively scan directory for all files.

    Args:
        root_dir: Root directory to scan.

    Returns:
        List of FileInfo objects for all files found.
    """
    files = []

    for dirpath, dirnames, filenames in os.walk(root_dir):
        # Skip excluded directories
        dirnames[:] = [d for d in dirnames if d not in EXCLUDED_DIRS]

        for filename in filenames:
            if filename in EXCLUDED_FILES:
                continue

            file_path = Path(dirpath) / filename

            try:
                stat = file_path.stat()
                files.append(
                    FileInfo(
                        path=file_path,
                        size=stat.st_size,
                        modified=datetime.fromtimestamp(stat.st_mtime),
                    )
                )
            except OSError:
                continue

    return files


def hash_files(
    files: list[FileInfo], do_content_hash: bool = True, do_perceptual_hash: bool = True
) -> None:
    """
    Calculate hashes for all files in place.

    Args:
        files: List of FileInfo objects to hash.
        do_content_hash: Whether to calculate content hashes.
        do_perceptual_hash: Whether to calculate perceptual hashes for images.
    """
    total = len(files)

    for i, file_info in enumerate(files, 1):
        print(f"\rHashing files: {i}/{total}", end="", flush=True)

        if do_content_hash:
            try:
                file_info.content_hash = get_content_hash(file_info.path)
            except OSError:
                pass

        if do_perceptual_hash:
            file_info.perceptual_hash = get_perceptual_hash(file_info.path)

    print()  # Newline after progress


def find_exact_duplicates(files: list[FileInfo]) -> list[DuplicateGroup]:
    """
    Find groups of files with identical content hashes.

    Args:
        files: List of FileInfo objects with content hashes.

    Returns:
        List of DuplicateGroup objects for exact duplicates.
    """
    hash_groups: dict[str, list[FileInfo]] = defaultdict(list)

    for file_info in files:
        if file_info.content_hash:
            hash_groups[file_info.content_hash].append(file_info)

    groups = []
    for hash_value, group_files in hash_groups.items():
        if len(group_files) > 1:
            groups.append(DuplicateGroup(group_type="exact", files=group_files))

    return groups


def find_similar_images(
    files: list[FileInfo], threshold: int = 5
) -> list[DuplicateGroup]:
    """
    Find groups of visually similar images using perceptual hashing.

    Args:
        files: List of FileInfo objects with perceptual hashes.
        threshold: Maximum hash distance to consider images similar.

    Returns:
        List of DuplicateGroup objects for similar images.
    """
    if not IMAGEHASH_AVAILABLE:
        return []

    # Filter to only files with perceptual hashes
    image_files = [f for f in files if f.perceptual_hash]

    if not image_files:
        return []

    # Track which files have been grouped
    grouped: set[Path] = set()
    groups = []

    for i, file1 in enumerate(image_files):
        if file1.path in grouped:
            continue

        hash1 = imagehash.hex_to_hash(file1.perceptual_hash)
        similar = [file1]

        for file2 in image_files[i + 1 :]:
            if file2.path in grouped:
                continue

            hash2 = imagehash.hex_to_hash(file2.perceptual_hash)
            distance = hash1 - hash2

            if distance <= threshold:
                similar.append(file2)
                grouped.add(file2.path)

        if len(similar) > 1:
            grouped.add(file1.path)
            groups.append(
                DuplicateGroup(
                    group_type="similar", files=similar, similarity=threshold
                )
            )

    return groups


def format_size(size_bytes: int) -> str:
    """Format file size in human-readable form."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def generate_report(groups: list[DuplicateGroup], output_path: Path) -> None:
    """
    Generate a text report of all duplicate groups.

    Args:
        groups: List of DuplicateGroup objects.
        output_path: Path to write the report to.
    """
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("Duplicate Detection Report\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 60 + "\n\n")

        exact_groups = [g for g in groups if g.group_type == "exact"]
        similar_groups = [g for g in groups if g.group_type == "similar"]

        f.write(f"Total duplicate groups found: {len(groups)}\n")
        f.write(f"  - Exact duplicates: {len(exact_groups)}\n")
        f.write(f"  - Similar images: {len(similar_groups)}\n\n")

        for i, group in enumerate(groups, 1):
            group_label = (
                "Exact Match" if group.group_type == "exact" else "Similar Images"
            )
            f.write(f"=== Group {i} ({group_label}) ===\n")

            for j, file_info in enumerate(group.files, 1):
                f.write(f"  [{j}] {file_info.path}\n")
                f.write(f"      Size: {format_size(file_info.size)}, ")
                f.write(f"Modified: {file_info.modified.strftime('%Y-%m-%d %H:%M')}\n")

            f.write("\n")

    print(f"Report saved to: {output_path}")


def move_to_duplicates(
    file_path: Path, root_dir: Path, duplicates_dir: Path, dry_run: bool = False
) -> bool:
    """
    Move a file to the _duplicates folder, preserving relative path structure.

    Args:
        file_path: Path to the file to move.
        root_dir: Original root directory.
        duplicates_dir: Destination _duplicates directory.
        dry_run: If True, don't actually move the file.

    Returns:
        True if successful (or would be in dry-run), False otherwise.
    """
    try:
        relative = file_path.relative_to(root_dir)
    except ValueError:
        relative = Path(file_path.name)

    dest_path = duplicates_dir / relative

    if dry_run:
        print(f"  [DRY-RUN] Would move: {file_path.name} -> {dest_path}")
        return True

    try:
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(file_path), str(dest_path))
        print(f"  Moved: {file_path.name} -> {dest_path}")
        return True
    except OSError as e:
        print(f"  Error moving {file_path}: {e}")
        return False


def delete_file(file_path: Path, dry_run: bool = False) -> bool:
    """
    Delete a file.

    Args:
        file_path: Path to the file to delete.
        dry_run: If True, don't actually delete the file.

    Returns:
        True if successful (or would be in dry-run), False otherwise.
    """
    if dry_run:
        print(f"  [DRY-RUN] Would delete: {file_path}")
        return True

    try:
        file_path.unlink()
        print(f"  Deleted: {file_path}")
        return True
    except OSError as e:
        print(f"  Error deleting {file_path}: {e}")
        return False


def interactive_cli_review(
    groups: list[DuplicateGroup], root_dir: Path, dry_run: bool = False
) -> dict:
    """
    Simple CLI-based interactive review of duplicate groups.

    Args:
        groups: List of DuplicateGroup objects.
        root_dir: Root directory for relative path calculations.
        dry_run: If True, don't actually perform actions.

    Returns:
        Summary statistics of actions taken.
    """
    duplicates_dir = root_dir / "_duplicates"

    stats = {"reviewed": 0, "skipped": 0, "moved": 0, "deleted": 0}

    total_groups = len(groups)

    for i, group in enumerate(groups, 1):
        group_label = "Exact Match" if group.group_type == "exact" else "Similar Images"

        print(f"\n{'=' * 60}")
        print(f"=== Duplicate Group {i}/{total_groups} ({group_label}) ===")
        print()

        for j, file_info in enumerate(group.files, 1):
            print(f"  [{j}] {file_info.path}")
            print(
                f"      Size: {format_size(file_info.size)}, "
                f"Modified: {file_info.modified.strftime('%Y-%m-%d %H:%M')}"
            )

        print()
        print("Actions: [K]eep (enter numbers), [M]ove others to _duplicates,")
        print("         [D]elete others, [S]kip, [Q]uit")

        while True:
            choice = input("> ").strip().lower()

            if choice == "q":
                print("\nQuitting review...")
                return stats

            if choice == "s":
                stats["skipped"] += 1
                break

            if choice.startswith("k"):
                # Parse numbers to keep
                parts = choice[1:].strip().split()
                if not parts:
                    parts = (
                        input("Enter file numbers to keep (space-separated): ")
                        .strip()
                        .split()
                    )

                try:
                    keep_indices = {int(p) for p in parts}
                except ValueError:
                    print("Invalid input. Enter numbers like: k 1 2")
                    continue

                # Validate indices
                valid_indices = set(range(1, len(group.files) + 1))
                if not keep_indices.issubset(valid_indices):
                    print(f"Invalid indices. Valid range: 1-{len(group.files)}")
                    continue

                print(f"\nKeeping files: {sorted(keep_indices)}")
                print("What to do with others? [M]ove to _duplicates or [D]elete?")
                action = input("> ").strip().lower()

                for j, file_info in enumerate(group.files, 1):
                    if j not in keep_indices:
                        if action == "m":
                            if move_to_duplicates(
                                file_info.path, root_dir, duplicates_dir, dry_run
                            ):
                                stats["moved"] += 1
                        elif action == "d":
                            if delete_file(file_info.path, dry_run):
                                stats["deleted"] += 1

                stats["reviewed"] += 1
                break

            if choice == "m":
                # Keep first file, move others
                print(f"\nKeeping: {group.files[0].path.name}")
                for file_info in group.files[1:]:
                    if move_to_duplicates(
                        file_info.path, root_dir, duplicates_dir, dry_run
                    ):
                        stats["moved"] += 1
                stats["reviewed"] += 1
                break

            if choice == "d":
                # Keep first file, delete others
                print(f"\nKeeping: {group.files[0].path.name}")
                for file_info in group.files[1:]:
                    if delete_file(file_info.path, dry_run):
                        stats["deleted"] += 1
                stats["reviewed"] += 1
                break

            print("Invalid choice. Use K, M, D, S, or Q.")

    return stats


class DuplicateReviewApp:
    """
    Interactive Panel app for reviewing duplicate files with Plotly image display.
    """

    def __init__(
        self, groups: list[DuplicateGroup], root_dir: Path, dry_run: bool = False
    ):
        self.groups = groups
        self.root_dir = root_dir
        self.dry_run = dry_run
        self.duplicates_dir = root_dir / "_duplicates"
        self.current_index = 0

        self.stats = {"reviewed": 0, "skipped": 0, "moved": 0, "deleted": 0}

        # Initialize Panel extension
        pn.extension("plotly")

        # Create widgets
        self._create_widgets()
        self._create_layout()

    def _create_widgets(self):
        """Create Panel widgets for the app."""
        # Progress indicator
        self.progress_text = pn.pane.Markdown(
            self._get_progress_text(), sizing_mode="stretch_width"
        )

        # Plotly pane for images
        self.image_pane = pn.pane.Plotly(
            self._create_image_figure(), sizing_mode="stretch_both", min_height=400
        )

        # File selection checkboxes
        self.file_checkboxes = pn.widgets.CheckBoxGroup(
            name="Files to KEEP",
            options=self._get_file_options(),
            value=[self._get_file_options()[0]] if self._get_file_options() else [],
        )

        # Action buttons
        self.move_btn = pn.widgets.Button(
            name="Move Others to _duplicates",
            button_type="primary",
            sizing_mode="stretch_width",
        )
        self.delete_btn = pn.widgets.Button(
            name="Delete Others", button_type="danger", sizing_mode="stretch_width"
        )
        self.skip_btn = pn.widgets.Button(
            name="Skip", button_type="default", sizing_mode="stretch_width"
        )

        # Navigation buttons
        self.prev_btn = pn.widgets.Button(name="< Previous", button_type="default")
        self.next_btn = pn.widgets.Button(name="Next >", button_type="default")

        # Status text
        self.status_text = pn.pane.Markdown(
            "*Select files to keep, then choose an action.*"
        )

        # Stats display
        self.stats_text = pn.pane.Markdown(self._get_stats_text())

        # Wire up callbacks
        self.move_btn.on_click(self._on_move)
        self.delete_btn.on_click(self._on_delete)
        self.skip_btn.on_click(self._on_skip)
        self.prev_btn.on_click(self._on_prev)
        self.next_btn.on_click(self._on_next)

    def _create_layout(self):
        """Create the Panel layout."""
        self.layout = pn.Column(
            pn.pane.Markdown("# Duplicate File Review"),
            pn.pane.Markdown(
                f"**Mode:** {'DRY RUN' if self.dry_run else 'LIVE'} | "
                f"**Directory:** {self.root_dir}"
            ),
            pn.layout.Divider(),
            self.progress_text,
            self.image_pane,
            pn.layout.Divider(),
            pn.Row(
                pn.Column(
                    pn.pane.Markdown("### Select Files to Keep"),
                    self.file_checkboxes,
                    sizing_mode="stretch_width",
                ),
                pn.Column(
                    pn.pane.Markdown("### Actions"),
                    self.move_btn,
                    self.delete_btn,
                    self.skip_btn,
                    sizing_mode="stretch_width",
                ),
                sizing_mode="stretch_width",
            ),
            pn.layout.Divider(),
            pn.Row(self.prev_btn, self.next_btn, sizing_mode="stretch_width"),
            self.status_text,
            self.stats_text,
            sizing_mode="stretch_both",
            min_width=800,
        )

    def _get_current_group(self) -> Optional[DuplicateGroup]:
        """Get the current duplicate group."""
        if 0 <= self.current_index < len(self.groups):
            return self.groups[self.current_index]
        return None

    def _get_progress_text(self) -> str:
        """Get the progress text."""
        group = self._get_current_group()
        if not group:
            return "**No duplicate groups to review.**"

        group_type = "Exact Match" if group.group_type == "exact" else "Similar Images"
        return (
            f"**Group {self.current_index + 1} of {len(self.groups)}** ({group_type})"
        )

    def _get_file_options(self) -> list[str]:
        """Get file options for the checkbox group."""
        group = self._get_current_group()
        if not group:
            return []

        options = []
        for i, f in enumerate(group.files, 1):
            label = f"[{i}] {f.path.name} ({format_size(f.size)})"
            options.append(label)
        return options

    def _get_stats_text(self) -> str:
        """Get the statistics text."""
        return (
            f"**Statistics:** "
            f"Reviewed: {self.stats['reviewed']} | "
            f"Skipped: {self.stats['skipped']} | "
            f"Moved: {self.stats['moved']} | "
            f"Deleted: {self.stats['deleted']}"
        )

    def _create_image_figure(self) -> go.Figure:
        """Create a Plotly figure with image grid for the current group."""
        group = self._get_current_group()

        if not group:
            fig = go.Figure()
            fig.add_annotation(
                text="No more duplicate groups to review",
                xref="paper",
                yref="paper",
                x=0.5,
                y=0.5,
                showarrow=False,
                font=dict(size=20),
            )
            fig.update_layout(xaxis=dict(visible=False), yaxis=dict(visible=False))
            return fig

        # Filter to image files only
        image_files = [
            f for f in group.files if f.path.suffix.lower() in IMAGE_EXTENSIONS
        ]

        if not image_files:
            # Non-image files - show file info as text
            fig = go.Figure()
            text_lines = ["<b>Non-image files in this group:</b><br><br>"]
            for i, f in enumerate(group.files, 1):
                text_lines.append(
                    f"[{i}] {f.path.name}<br>"
                    f"    Size: {format_size(f.size)}<br>"
                    f"    Modified: {f.modified.strftime('%Y-%m-%d %H:%M')}<br><br>"
                )
            fig.add_annotation(
                text="".join(text_lines),
                xref="paper",
                yref="paper",
                x=0.05,
                y=0.95,
                showarrow=False,
                font=dict(size=14),
                align="left",
                xanchor="left",
                yanchor="top",
            )
            fig.update_layout(
                xaxis=dict(visible=False), yaxis=dict(visible=False), height=300
            )
            return fig

        # Calculate grid dimensions
        n_images = len(image_files)
        cols = min(n_images, 3)
        rows = (n_images + cols - 1) // cols

        # Create subplots
        fig = make_subplots(
            rows=rows,
            cols=cols,
            subplot_titles=[
                f"[{i + 1}] {f.path.name}" for i, f in enumerate(image_files)
            ],
            horizontal_spacing=0.05,
            vertical_spacing=0.1,
        )

        # Add images
        for idx, file_info in enumerate(image_files):
            row = idx // cols + 1
            col = idx % cols + 1

            try:
                # Load and encode image
                with Image.open(file_info.path) as img:
                    # Resize for display
                    img.thumbnail((400, 400))

                    # Convert to base64
                    import io

                    buffer = io.BytesIO()
                    img_format = "PNG" if img.mode == "RGBA" else "JPEG"
                    img.save(buffer, format=img_format)
                    img_base64 = base64.b64encode(buffer.getvalue()).decode()

                    # Add image trace
                    fig.add_layout_image(
                        dict(
                            source=f"data:image/{img_format.lower()};base64,{img_base64}",
                            xref=f"x{idx + 1}" if idx > 0 else "x",
                            yref=f"y{idx + 1}" if idx > 0 else "y",
                            x=0,
                            y=1,
                            sizex=1,
                            sizey=1,
                            xanchor="left",
                            yanchor="top",
                            layer="below",
                        )
                    )

                    # Configure subplot axes
                    xaxis_name = f"xaxis{idx + 1}" if idx > 0 else "xaxis"
                    yaxis_name = f"yaxis{idx + 1}" if idx > 0 else "yaxis"

                    fig.update_layout(
                        **{
                            xaxis_name: dict(
                                showgrid=False,
                                zeroline=False,
                                showticklabels=False,
                                range=[0, 1],
                            ),
                            yaxis_name: dict(
                                showgrid=False,
                                zeroline=False,
                                showticklabels=False,
                                range=[0, 1],
                                scaleanchor=f"x{idx + 1}" if idx > 0 else "x",
                            ),
                        }
                    )

            except Exception:
                # Add placeholder for failed image load
                fig.add_annotation(
                    text=f"Failed to load:<br>{file_info.path.name}",
                    xref=f"x{idx + 1}" if idx > 0 else "x",
                    yref=f"y{idx + 1}" if idx > 0 else "y",
                    x=0.5,
                    y=0.5,
                    showarrow=False,
                    font=dict(size=10),
                )

        fig.update_layout(
            height=300 * rows, showlegend=False, margin=dict(l=10, r=10, t=40, b=10)
        )

        return fig

    def _update_display(self):
        """Update all display elements for the current group."""
        self.progress_text.object = self._get_progress_text()
        self.image_pane.object = self._create_image_figure()
        self.file_checkboxes.options = self._get_file_options()

        # Default selection: first file
        options = self._get_file_options()
        self.file_checkboxes.value = [options[0]] if options else []

        self.stats_text.object = self._get_stats_text()

    def _get_selected_indices(self) -> set[int]:
        """Get the indices of selected (to keep) files."""
        selected = set()
        for val in self.file_checkboxes.value:
            # Parse index from "[N] filename"
            try:
                idx = int(val.split("]")[0].strip("["))
                selected.add(idx)
            except (ValueError, IndexError):
                pass
        return selected

    def _on_move(self, event):
        """Handle move button click."""
        group = self._get_current_group()
        if not group:
            return

        keep_indices = self._get_selected_indices()
        if not keep_indices:
            self.status_text.object = "*Please select at least one file to keep.*"
            return

        moved = 0
        for i, file_info in enumerate(group.files, 1):
            if i not in keep_indices:
                if move_to_duplicates(
                    file_info.path, self.root_dir, self.duplicates_dir, self.dry_run
                ):
                    moved += 1

        self.stats["moved"] += moved
        self.stats["reviewed"] += 1

        action = "Would move" if self.dry_run else "Moved"
        self.status_text.object = f"*{action} {moved} file(s). Moving to next group...*"

        self._advance_group()

    def _on_delete(self, event):
        """Handle delete button click."""
        group = self._get_current_group()
        if not group:
            return

        keep_indices = self._get_selected_indices()
        if not keep_indices:
            self.status_text.object = "*Please select at least one file to keep.*"
            return

        deleted = 0
        for i, file_info in enumerate(group.files, 1):
            if i not in keep_indices:
                if delete_file(file_info.path, self.dry_run):
                    deleted += 1

        self.stats["deleted"] += deleted
        self.stats["reviewed"] += 1

        action = "Would delete" if self.dry_run else "Deleted"
        self.status_text.object = (
            f"*{action} {deleted} file(s). Moving to next group...*"
        )

        self._advance_group()

    def _on_skip(self, event):
        """Handle skip button click."""
        self.stats["skipped"] += 1
        self.status_text.object = "*Skipped group. Moving to next...*"
        self._advance_group()

    def _on_prev(self, event):
        """Handle previous button click."""
        if self.current_index > 0:
            self.current_index -= 1
            self._update_display()
            self.status_text.object = ""

    def _on_next(self, event):
        """Handle next button click."""
        if self.current_index < len(self.groups) - 1:
            self.current_index += 1
            self._update_display()
            self.status_text.object = ""

    def _advance_group(self):
        """Advance to the next group or show completion message."""
        if self.current_index < len(self.groups) - 1:
            self.current_index += 1
            self._update_display()
        else:
            self.status_text.object = (
                "**All groups reviewed!** "
                f"Reviewed: {self.stats['reviewed']}, "
                f"Skipped: {self.stats['skipped']}, "
                f"Moved: {self.stats['moved']}, "
                f"Deleted: {self.stats['deleted']}"
            )
            self._update_display()

    def serve(self, port: int = 5006):
        """Serve the Panel app."""
        print(f"\nStarting interactive review app at http://localhost:{port}")
        print("Press Ctrl+C to stop the server.\n")
        self.layout.show(port=port, threaded=False)

    def get_layout(self):
        """Get the layout for embedding or testing."""
        return self.layout


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description="Find and review duplicate files with interactive image display.",
        epilog='Example: python find_duplicates.py "C:\\path\\to\\directory"',
    )
    parser.add_argument(
        "directory", type=str, help="The root directory to scan for duplicates"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview actions without actually moving or deleting files",
    )
    parser.add_argument(
        "--exact-only",
        action="store_true",
        help="Only find exact duplicates (skip perceptual hashing)",
    )
    parser.add_argument(
        "--similar-only",
        action="store_true",
        help="Only find visually similar images (skip exact matching)",
    )
    parser.add_argument(
        "--threshold",
        type=int,
        default=5,
        help="Similarity threshold for perceptual hashing (default: 5)",
    )
    parser.add_argument(
        "--report-only",
        action="store_true",
        help="Generate report only, skip interactive review",
    )
    parser.add_argument(
        "--cli",
        action="store_true",
        help="Use CLI-based interactive mode instead of Panel app",
    )
    parser.add_argument(
        "--port", type=int, default=5006, help="Port for the Panel app (default: 5006)"
    )

    args = parser.parse_args()

    root_dir = Path(args.directory).resolve()

    # Validate directory
    if not root_dir.exists():
        print(f"Error: Directory '{root_dir}' does not exist.")
        return 1

    if not root_dir.is_dir():
        print(f"Error: '{root_dir}' is not a directory.")
        return 1

    # Check for required dependencies
    do_content_hash = not args.similar_only
    do_perceptual_hash = not args.exact_only

    if do_perceptual_hash and not IMAGEHASH_AVAILABLE:
        print("Warning: imagehash/Pillow not installed. Perceptual hashing disabled.")
        print("Install with: pip install imagehash Pillow")
        do_perceptual_hash = False

    if not args.report_only and not args.cli and not INTERACTIVE_AVAILABLE:
        print("Warning: panel/plotly not installed. Falling back to CLI mode.")
        print("Install with: pip install panel plotly")
        args.cli = True

    print(f"Scanning directory: {root_dir}")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE'}")
    print()

    # Scan files
    print("Scanning files...")
    files = scan_files(root_dir)
    print(f"Found {len(files)} files.")

    if not files:
        print("No files to process.")
        return 0

    # Hash files
    print("\nCalculating hashes...")
    hash_files(files, do_content_hash, do_perceptual_hash)

    # Find duplicates
    groups = []

    if do_content_hash:
        print("\nFinding exact duplicates...")
        exact_groups = find_exact_duplicates(files)
        print(f"Found {len(exact_groups)} group(s) of exact duplicates.")
        groups.extend(exact_groups)

    if do_perceptual_hash:
        print("\nFinding similar images...")
        similar_groups = find_similar_images(files, args.threshold)
        print(f"Found {len(similar_groups)} group(s) of similar images.")
        groups.extend(similar_groups)

    if not groups:
        print("\nNo duplicates found!")
        return 0

    # Generate report
    report_path = root_dir / "duplicates_report.txt"
    generate_report(groups, report_path)

    if args.report_only:
        print("\nReport-only mode. Skipping interactive review.")
        return 0

    # Interactive review
    if args.cli:
        print("\nStarting CLI interactive review...")
        stats = interactive_cli_review(groups, root_dir, args.dry_run)
    else:
        print("\nStarting Panel app for interactive review...")
        app = DuplicateReviewApp(groups, root_dir, args.dry_run)
        app.serve(args.port)
        stats = app.stats

    # Print summary
    print("\n" + "=" * 50)
    print("SUMMARY")
    print("=" * 50)
    print(f"Groups reviewed: {stats['reviewed']}")
    print(f"Groups skipped:  {stats['skipped']}")
    print(f"Files moved:     {stats['moved']}")
    print(f"Files deleted:   {stats['deleted']}")

    print("\nDone!")
    return 0


if __name__ == "__main__":
    exit(main())
