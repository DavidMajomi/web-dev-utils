#!/usr/bin/env python3
"""
File Directory Renaming Script

Recursively scans directories at any depth, identifies all files,
and renames them using the full path hierarchy with zero-padded numbering.

Example: Okpedafe/NY_reunion_2023/Day1/photo.jpeg -> Okpedafe_NY_reunion_2023_Day1_001.jpeg
"""

import os
import argparse
from pathlib import Path


# Files to exclude from renaming (the script itself and other utility scripts)
EXCLUDED_FILES = {"rename_files.py", "unzip_all.py", "find_duplicates.py"}

# Directories to exclude from renaming (code-related directories)
EXCLUDED_DIRS = {
    ".venv",
    "venv",
    "__pycache__",
    ".git",
    "node_modules",
    ".idea",
    ".vscode",
}

# File extensions to exclude from renaming (code and documentation files)
EXCLUDED_EXTENSIONS = {
    ".py",
    ".pyc",
    ".pyo",
    ".pyd",  # Python
    ".js",
    ".ts",
    ".jsx",
    ".tsx",  # JavaScript/TypeScript
    ".md",
    ".rst",
    ".txt",  # Documentation
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".cfg",  # Config files
    ".html",
    ".css",
    ".scss",
    ".sass",  # Web files
    ".sh",
    ".bat",
    ".ps1",  # Scripts
    ".c",
    ".cpp",
    ".h",
    ".hpp",  # C/C++
    ".java",
    ".kt",  # Java/Kotlin
    ".go",
    ".rs",  # Go/Rust
    ".rb",
    ".php",  # Ruby/PHP
    ".sql",  # SQL
    ".gitignore",
    ".gitattributes",  # Git files
    ".env",
    ".lock",  # Environment and lock files
}


def get_files_in_directory(directory: Path) -> list[Path]:
    """
    Get all files in a directory (non-recursive, files only).
    Excludes files in EXCLUDED_FILES and files with EXCLUDED_EXTENSIONS.
    """
    files = []
    for item in directory.iterdir():
        if item.is_file():
            if item.name in EXCLUDED_FILES:
                continue
            if item.suffix.lower() in EXCLUDED_EXTENSIONS:
                continue
            files.append(item)
    # Sort files for consistent ordering
    return sorted(files, key=lambda f: f.name.lower())


def build_path_prefix(root_dir: Path, current_dir: Path) -> str:
    """
    Build the underscore-separated path prefix from root to current directory.

    Example: If root is 'Okpedafe' and current_dir is 'Okpedafe/NY_reunion_2023/Day1',
    returns 'Okpedafe_NY_reunion_2023_Day1'
    """
    # Get relative path from root's parent to include root name
    try:
        relative = current_dir.relative_to(root_dir.parent)
    except ValueError:
        # Fallback: just use the directory name
        relative = Path(current_dir.name)

    # Convert path separators to underscores
    parts = relative.parts
    return "_".join(parts)


def calculate_padding(count: int) -> int:
    """
    Calculate the number of digits needed for zero-padding based on total count.
    """
    if count <= 0:
        return 1
    return len(str(count))


def generate_new_filename(prefix: str, index: int, padding: int, extension: str) -> str:
    """
    Generate the new filename with path prefix, zero-padded index, and extension.

    Example: generate_new_filename('Okpedafe_Photos', 1, 3, '.jpeg') -> 'Okpedafe_Photos_001.jpeg'
    """
    padded_index = str(index).zfill(padding)
    return f"{prefix}_{padded_index}{extension}"


def rename_files_in_directory(
    root_dir: Path, current_dir: Path, dry_run: bool = True
) -> list[tuple[Path, Path]]:
    """
    Rename all files in a single directory according to the naming convention.

    Returns a list of (old_path, new_path) tuples.
    """
    files = get_files_in_directory(current_dir)
    if not files:
        return []

    prefix = build_path_prefix(root_dir, current_dir)
    padding = calculate_padding(len(files))

    renames = []

    for index, file_path in enumerate(files, start=1):
        extension = file_path.suffix
        new_name = generate_new_filename(prefix, index, padding, extension)
        new_path = file_path.parent / new_name

        renames.append((file_path, new_path))

    return renames


def process_directory_tree(
    root_dir: Path, dry_run: bool = True
) -> list[tuple[Path, Path]]:
    """
    Process the entire directory tree recursively.

    Returns a list of all (old_path, new_path) tuples.
    """
    all_renames = []

    # Walk through all directories
    for dirpath, dirnames, filenames in os.walk(root_dir):
        # Skip excluded directories
        dirnames[:] = [d for d in dirnames if d not in EXCLUDED_DIRS]

        current_dir = Path(dirpath)
        renames = rename_files_in_directory(root_dir, current_dir, dry_run)
        all_renames.extend(renames)

    return all_renames


def execute_renames(renames: list[tuple[Path, Path]], dry_run: bool = True) -> None:
    """
    Execute the file renames. Uses a two-phase approach to handle conflicts:
    1. First rename all files to temporary names
    2. Then rename from temporary to final names
    """
    if not renames:
        print("No files to rename.")
        return

    if dry_run:
        print("\n=== DRY RUN - No files will be renamed ===\n")
        for old_path, new_path in renames:
            print(f"  {old_path.name}")
            print(f"    -> {new_path.name}")
            print()
        print(f"Total: {len(renames)} file(s) would be renamed.")
    else:
        print("\n=== Renaming files ===\n")

        # Phase 1: Rename to temporary names to avoid conflicts
        temp_renames = []
        for i, (old_path, new_path) in enumerate(renames):
            temp_name = f"__temp_rename_{i}_{old_path.suffix}"
            temp_path = old_path.parent / temp_name
            temp_renames.append((old_path, temp_path, new_path))

            try:
                old_path.rename(temp_path)
            except OSError as e:
                print(f"Error renaming {old_path} to temp: {e}")
                # Try to rollback
                for j in range(i):
                    orig, temp, _ = temp_renames[j]
                    try:
                        temp.rename(orig)
                    except OSError:
                        pass
                raise

        # Phase 2: Rename from temporary to final names
        success_count = 0
        for old_path, temp_path, new_path in temp_renames:
            try:
                temp_path.rename(new_path)
                print(f"  {old_path.name} -> {new_path.name}")
                success_count += 1
            except OSError as e:
                print(f"Error renaming {temp_path} to {new_path}: {e}")

        print(f"\nTotal: {success_count} file(s) renamed successfully.")


def main():
    parser = argparse.ArgumentParser(
        description="Rename files recursively using directory path as prefix with zero-padded numbering."
    )
    parser.add_argument(
        "--path",
        type=str,
        default=".",
        help="Root directory to process (default: current directory)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without actually renaming files",
    )

    args = parser.parse_args()

    root_dir = Path(args.path).resolve()

    if not root_dir.exists():
        print(f"Error: Directory '{root_dir}' does not exist.")
        return 1

    if not root_dir.is_dir():
        print(f"Error: '{root_dir}' is not a directory.")
        return 1

    print(f"Processing directory: {root_dir}")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE'}")

    # Collect all renames
    renames = process_directory_tree(root_dir, args.dry_run)

    # Execute renames
    execute_renames(renames, args.dry_run)

    return 0


if __name__ == "__main__":
    exit(main())
