"""Dashboard entry point supporting both Python and Streamlit launches."""

if __name__ == "__main__":
    from src.dashboard_launcher import launch_if_needed

    launch_if_needed(__file__)

from streamlit_app import *  # noqa: F403
