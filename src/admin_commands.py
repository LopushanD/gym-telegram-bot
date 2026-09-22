from pathlib import Path

ALL_COMMANDS_ADMIN_COMMAND = "commands"
GIVE_KEY_ADMIN_COMMAND = "givekey"
CHANGE_KEY_OWNER_ADMIN_COMMAND = "keychangeowner"
ADD_USER_ADMIN_COMMAND = "adduser"
UPDATE_USER_ADMIN_COMMAND = "updateuser"
SHOW_USERS_ADMIN_COMMAND = "users"
SHOW_KEY_HISTORY_ADMIN_COMMAND = "keyhistory"
SHOW_KEY_STATUS_ADMIN_COMMAND = "keystatus"
ACTIVATE_KEY_ADMIN_COMMAND = "activatekey"
DEACTIVATE_KEY_ADMIN_COMMAND = "deactivatekey"
COMMAND_DOCS_ROOT = Path(__file__).resolve().parents[1] / "assets" / "admin_docs"
COMMAND_DOC_PATHS = {
    ALL_COMMANDS_ADMIN_COMMAND: COMMAND_DOCS_ROOT / "commands.md",
    GIVE_KEY_ADMIN_COMMAND: COMMAND_DOCS_ROOT / "givekey.md",
    CHANGE_KEY_OWNER_ADMIN_COMMAND: COMMAND_DOCS_ROOT / "keychangeowner.md",
    ADD_USER_ADMIN_COMMAND: COMMAND_DOCS_ROOT / "adduser.md",
    UPDATE_USER_ADMIN_COMMAND: COMMAND_DOCS_ROOT / "updateuser.md",
    SHOW_USERS_ADMIN_COMMAND: COMMAND_DOCS_ROOT / "users.md",
    SHOW_KEY_HISTORY_ADMIN_COMMAND: COMMAND_DOCS_ROOT / "keyhistory.md",
    SHOW_KEY_STATUS_ADMIN_COMMAND: COMMAND_DOCS_ROOT / "keystatus.md",
    ACTIVATE_KEY_ADMIN_COMMAND: COMMAND_DOCS_ROOT / "activatekey.md",
    DEACTIVATE_KEY_ADMIN_COMMAND: COMMAND_DOCS_ROOT / "deactivatekey.md",
}
def load_command_documentation(command_name) -> str:
    try:
        command_doc_path = COMMAND_DOC_PATHS[command_name]
    except KeyError as exc:
        raise ValueError(f"Unknown admin command: {command_name}") from exc

    try:
        return command_doc_path.read_text(encoding="utf-8").strip()
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"Admin doc asset not found: {command_doc_path}") from exc
