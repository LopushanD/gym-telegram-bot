from pathlib import Path
TUTORIALS_INFO_TUTORIAL = "tutorials"
REGESTRATION_TUTORIAL = "regestrationtutorial"
GET_KEY_TUTORIAL = "getkeytutorial"
GIVE_KEY_TUTORIAL = "givekeytutorial"
RETURN_KEY_TUTORIAL = "returnkeytutorial"

HELP_USER_COMMAND = "help"
CLEAR_USER_COMMAND = "clear"
GET_TG_ID_USER_COMMAND = "mytelegramid"
START_USER_COMMAND = "start"
SHOW_ADMINS_USER_COMMAND = "admins"
HELP_TEXT = f"""Available commands:

/mytelegramid
Shows your Telegram user ID\.

/clear
Delete all messages from the chat\. In some cases Telegram does not allow to delete messages\. In this case use _'clear history'_ in your chat settings\.

/{TUTORIALS_INFO_TUTORIAL}
Shows all available tutorials\.

/start
Get starting message and buttons\.

/admins
Shows list of all bot admins\.
"""

TURORIALS_ROOT = Path(__file__).resolve().parents[1] / "assets" / "user_tutorials"
TUTORIAL_PATHS = {
    TUTORIALS_INFO_TUTORIAL: TURORIALS_ROOT / "tutorial_about_tutorials.md",
    REGESTRATION_TUTORIAL: TURORIALS_ROOT / "registration.md",
    GET_KEY_TUTORIAL: TURORIALS_ROOT / "get_key.md",
    GIVE_KEY_TUTORIAL: TURORIALS_ROOT / "give_key.md",
    RETURN_KEY_TUTORIAL: TURORIALS_ROOT / "return_key.md",
}

def load_user_tutorial(tutorial_name: str) -> str:
    try:
        tutorial_path = TUTORIAL_PATHS[tutorial_name]
    except KeyError as exc:
        raise ValueError(f"Unknown user tutorial: {tutorial_name}") from exc

    try:
        return tutorial_path.read_text(encoding="utf-8").strip()
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"Tutorial asset not found: {tutorial_path}") from exc