#!/usr/bin/env python3
"""
Convert names from 'last_name first_name' or 'last_name mid_name first_name' format
to 'first_name.last_name' format.
"""

import argparse
import sys
from pathlib import Path


def convert_name(name: str) -> str | None:
    """
    Convert a name from 'last [middle...] first' to 'first.last' format.

    Args:
        name: Input name string

    Returns:
        Converted name in 'first.last' format, or None if invalid
    """
    # Sanitize: strip whitespace and normalize internal spaces
    cleaned = " ".join(name.strip().split())

    if not cleaned:
        return None

    parts = cleaned.split()

    if len(parts) < 2:
        # Single word - can't determine first/last
        print(f"Warning: Skipping single-word name: '{cleaned}'", file=sys.stderr)
        return None

    # First part is last name, final part is first name
    # Everything in between is ignored (middle names)
    last_name = parts[0]
    first_name = parts[-1]

    # Sanitize: remove any non-alphanumeric chars except hyphen
    last_name = "".join(c for c in last_name if c.isalnum() or c == "-")
    first_name = "".join(c for c in first_name if c.isalnum() or c == "-")

    if not first_name or not last_name:
        print(f"Warning: Invalid name after sanitization: '{cleaned}'", file=sys.stderr)
        return None

    return f"{first_name}.{last_name}".lower()


def process_file(input_path: Path, output_path: Path | None = None) -> list[str]:
    """
    Process a file of names and convert them.

    Args:
        input_path: Path to input file with one name per line
        output_path: Optional path to write results (if None, prints to stdout)

    Returns:
        List of converted names
    """
    results = []

    with open(input_path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            # Skip empty lines and comments
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue

            converted = convert_name(stripped)
            if converted:
                results.append(converted)
            else:
                print(f"Warning: Line {line_num} skipped", file=sys.stderr)

    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(results) + "\n")
        print(f"Wrote {len(results)} names to {output_path}", file=sys.stderr)
    else:
        for name in results:
            print(name)

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Convert names from 'last first' or 'last middle first' to 'first.last' format"
    )
    parser.add_argument(
        "input_file",
        type=Path,
        help="Input file with one name per line"
    )
    parser.add_argument(
        "-o", "--output",
        type=Path,
        help="Output file (default: print to stdout)"
    )

    args = parser.parse_args()

    if not args.input_file.exists():
        print(f"Error: Input file not found: {args.input_file}", file=sys.stderr)
        sys.exit(1)

    process_file(args.input_file, args.output)


if __name__ == "__main__":
    main()
