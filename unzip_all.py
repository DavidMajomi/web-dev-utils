#!/usr/bin/env python3
"""
Recursive Unzip Script

This script recursively finds and extracts all zip files in a given directory tree,
handles nested zips (zips inside zips), and deletes the originals after successful extraction.

Usage:
    python unzip_all.py "C:\path\to\directory"
"""

import zipfile
import argparse
from pathlib import Path


def find_zip_files(directory: Path) -> list[Path]:
    """Recursively find all .zip files in directory tree.

    Args:
        directory: The root directory to search in.

    Returns:
        A list of Path objects pointing to zip files.
    """
    return list(directory.rglob("*.zip"))


def extract_zip(zip_path: Path) -> bool:
    """Extract zip to its parent directory.

    Args:
        zip_path: Path to the zip file to extract.

    Returns:
        True if extraction was successful, False otherwise.
    """
    extract_dir = zip_path.parent

    try:
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            # Check if the zip file is valid
            bad_file = zip_ref.testzip()
            if bad_file is not None:
                print(f"  Warning: Corrupted file in archive: {bad_file}")

            # Extract all contents to the same directory as the zip file
            zip_ref.extractall(extract_dir)

        return True

    except zipfile.BadZipFile:
        print(f"  Error: '{zip_path}' is not a valid zip file or is corrupted.")
        return False
    except RuntimeError as e:
        # This typically occurs with password-protected zips
        print(f"  Error: Could not extract '{zip_path}': {e}")
        return False
    except PermissionError:
        print(f"  Error: Permission denied when extracting '{zip_path}'.")
        return False
    except Exception as e:
        print(f"  Error: Unexpected error extracting '{zip_path}': {e}")
        return False


def delete_zip(zip_path: Path) -> bool:
    """Delete a zip file.

    Args:
        zip_path: Path to the zip file to delete.

    Returns:
        True if deletion was successful, False otherwise.
    """
    try:
        zip_path.unlink()
        return True
    except PermissionError:
        print(f"  Error: Permission denied when deleting '{zip_path}'.")
        return False
    except Exception as e:
        print(f"  Error: Could not delete '{zip_path}': {e}")
        return False


def process_directory(root_dir: Path) -> None:
    """Process a directory, extracting all zip files recursively.

    This function loops until no more zip files are found, which handles
    nested zips (zips that were inside other zips).

    Args:
        root_dir: The root directory to process.
    """
    pass_number = 1
    total_extracted = 0
    total_deleted = 0
    total_errors = 0

    while True:
        zip_files = find_zip_files(root_dir)

        if not zip_files:
            if pass_number == 1:
                print("No zip files found.")
            break

        print(f"\n--- Pass {pass_number}: Found {len(zip_files)} zip file(s) ---\n")

        extracted_this_pass = 0
        deleted_this_pass = 0
        errors_this_pass = 0

        for zip_path in zip_files:
            print(f"Extracting: {zip_path}")

            if extract_zip(zip_path):
                extracted_this_pass += 1
                print(f"  Successfully extracted to: {zip_path.parent}")

                # Delete the zip file after successful extraction
                if delete_zip(zip_path):
                    deleted_this_pass += 1
                    print(f"  Deleted: {zip_path.name}")
                else:
                    errors_this_pass += 1
            else:
                errors_this_pass += 1

        total_extracted += extracted_this_pass
        total_deleted += deleted_this_pass
        total_errors += errors_this_pass

        print(
            f"\nPass {pass_number} complete: {extracted_this_pass} extracted, "
            f"{deleted_this_pass} deleted, {errors_this_pass} error(s)"
        )

        pass_number += 1

        # Safety limit to prevent infinite loops in edge cases
        if pass_number > 100:
            print("\nWarning: Reached maximum pass limit (100). Stopping.")
            break

    # Print summary
    print("\n" + "=" * 50)
    print("SUMMARY")
    print("=" * 50)
    print(f"Total zip files extracted: {total_extracted}")
    print(f"Total zip files deleted:   {total_deleted}")
    print(f"Total errors:              {total_errors}")


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description="Recursively extract all zip files in a directory tree.",
        epilog='Example: python unzip_all.py "C:\\path\\to\\directory"',
    )
    parser.add_argument(
        "directory", type=str, help="The root directory to search for zip files"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without actually extracting or deleting",
    )

    args = parser.parse_args()

    root_dir = Path(args.directory)

    # Validate the directory
    if not root_dir.exists():
        print(f"Error: Directory '{root_dir}' does not exist.")
        return 1

    if not root_dir.is_dir():
        print(f"Error: '{root_dir}' is not a directory.")
        return 1

    print(f"Starting recursive unzip in: {root_dir.absolute()}")

    if args.dry_run:
        print("\n[DRY RUN MODE - No files will be extracted or deleted]\n")
        zip_files = find_zip_files(root_dir)
        if zip_files:
            print(f"Found {len(zip_files)} zip file(s):")
            for zf in zip_files:
                print(f"  - {zf}")
            print(
                "\nNote: Nested zips inside these archives are not shown in dry-run mode."
            )
        else:
            print("No zip files found.")
        return 0

    process_directory(root_dir)

    print("\nDone!")
    return 0


if __name__ == "__main__":
    exit(main())
