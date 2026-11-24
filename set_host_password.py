"""Create the line for the host password, to paste into the .env file.

Run with:  python set_host_password.py

The password itself is never saved anywhere: only its hash (made with Werkzeug's
generate_password_hash) goes into .env. At login, the app checks the typed password
against that hash with check_password_hash.
"""

from getpass import getpass

from werkzeug.security import generate_password_hash

MIN_LENGTH = 10


def make_env_line(password):
    """The line for .env. Single quotes stop the '$' signs in the hash from being read as variables."""
    return f"HOST_PASSWORD_HASH='{generate_password_hash(password)}'"


def main():
    password = getpass(f"New host password (at least {MIN_LENGTH} characters): ")
    if len(password) < MIN_LENGTH:
        print(f"Too short: use at least {MIN_LENGTH} characters.")
        return
    if getpass("Type it again: ") != password:
        print("The two passwords are different. Nothing was changed.")
        return

    print("\nPut this line in the .env file (replace the old HOST_PASSWORD_HASH line):\n")
    print(make_env_line(password))
    print("\nThen restart the app (on PythonAnywhere: the Reload button on the Web tab).")


if __name__ == "__main__":
    main()
