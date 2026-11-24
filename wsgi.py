"""Entry point for the production server (PythonAnywhere runs the app through WSGI).

On this computer, use `python app.py` instead (Flask's development server).

On PythonAnywhere, the Web tab has a link to a WSGI configuration file
(/var/www/<account>_pythonanywhere_com_wsgi.py). Replace its whole content with these
three lines, with the real folder of the project:

    import sys
    sys.path.insert(0, "/home/<account>/Chatbot")
    from wsgi import application

Then press "Reload". PythonAnywhere's server imports `application` from here.
"""

from pathlib import Path

from dotenv import load_dotenv

from app import create_app

PROJECT_FOLDER = Path(__file__).resolve().parent

# The server does not start in the project folder, so .env is found by its full path
load_dotenv(PROJECT_FOLDER / ".env")

# production=True: the session cookie only travels over HTTPS. Debug stays off.
application = create_app(production=True)
