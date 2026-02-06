"""
Password Generator Script

Reads processed names and generates secure passwords output to CSV.
"""

import csv
import secrets
import string


def generate_password(length: int = 12) -> str:
    """
    Generate a cryptographically secure random password.

    Password will contain at least 3 of 4 character types:
    - Uppercase letters
    - Lowercase letters
    - Numbers
    - Special characters (!@#$%^&*)

    Args:
        length: Password length (default 12)

    Returns:
        A secure random password string
    """
    uppercase = string.ascii_uppercase
    lowercase = string.ascii_lowercase
    digits = string.digits
    special = "!@#$%^&*"

    # Ensure we have at least one of each required type (guarantees 4 of 4)
    password_chars = [
        secrets.choice(uppercase),
        secrets.choice(lowercase),
        secrets.choice(digits),
        secrets.choice(special),
    ]

    # Fill remaining characters from all character sets
    all_chars = uppercase + lowercase + digits + special
    remaining_length = length - len(password_chars)

    for _ in range(remaining_length):
        password_chars.append(secrets.choice(all_chars))

    # Shuffle to avoid predictable positions
    secrets.SystemRandom().shuffle(password_chars)

    return "".join(password_chars)


def validate_password(password: str, first: str, last: str, domain: str) -> bool:
    """
    Validate that password doesn't contain personal information.

    Checks that the password doesn't contain (case-insensitive):
    - First name
    - Last name
    - Domain parts (split by '.')

    Args:
        password: The password to validate
        first: First name
        last: Last name
        domain: Email domain

    Returns:
        True if password is valid (no personal info), False otherwise
    """
    password_lower = password.lower()

    # Check first name (minimum 2 chars to avoid false positives)
    if len(first) >= 2 and first.lower() in password_lower:
        return False

    # Check last name
    if len(last) >= 2 and last.lower() in password_lower:
        return False

    # Check domain parts
    domain_parts = domain.lower().split(".")
    for part in domain_parts:
        if len(part) >= 2 and part in password_lower:
            return False

    return True


def generate_valid_password(first: str, last: str, domain: str, length: int = 12, max_attempts: int = 100) -> str:
    """
    Generate a password that meets all requirements including no personal info.

    Args:
        first: First name
        last: Last name
        domain: Email domain
        length: Password length
        max_attempts: Maximum generation attempts

    Returns:
        A valid password

    Raises:
        RuntimeError: If unable to generate valid password within max_attempts
    """
    for _ in range(max_attempts):
        password = generate_password(length)
        if validate_password(password, first, last, domain):
            return password

    raise RuntimeError(f"Unable to generate valid password after {max_attempts} attempts")


def main():
    """Main entry point for the password generator."""
    # Prompt for email domain
    domain = input("Enter email domain (e.g., company.com): ").strip()
    if not domain:
        print("Error: Domain cannot be empty")
        return

    # Prompt for input file
    input_file = input("Enter input file path [processed_names.txt]: ").strip()
    if not input_file:
        input_file = "processed_names.txt"

    # Prompt for output file
    output_file = input("Enter output CSV file path [passwords.csv]: ").strip()
    if not output_file:
        output_file = "passwords.csv"

    # Read names from input file
    try:
        with open(input_file, "r", encoding="utf-8") as f:
            names = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        print(f"Error: Input file '{input_file}' not found")
        return
    except Exception as e:
        print(f"Error reading input file: {e}")
        return

    # Generate passwords and write to CSV
    count = 0
    try:
        with open(output_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["name", "email", "password"])

            for name in names:
                # Parse first.last format
                if "." not in name:
                    print(f"Warning: Skipping invalid name format '{name}' (expected first.last)")
                    continue

                parts = name.split(".", 1)
                first = parts[0]
                last = parts[1]

                # Generate email
                email = f"{name}@{domain}"

                # Generate valid password
                try:
                    password = generate_valid_password(first, last, domain)
                except RuntimeError as e:
                    print(f"Error generating password for {name}: {e}")
                    continue

                # Write row
                writer.writerow([name, email, password])
                count += 1

    except Exception as e:
        print(f"Error writing output file: {e}")
        return

    print(f"\nPassword generation complete!")
    print(f"Generated {count} passwords")
    print(f"Output saved to: {output_file}")


if __name__ == "__main__":
    main()
