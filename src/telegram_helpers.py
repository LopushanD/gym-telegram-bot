from telegram import CallbackQuery, Message, Update


def get_update_user_id(update: Update) -> int | None:
    user = getattr(update, "effective_user", None)
    if user is None:
        return None
    return user.id


def get_callback_user_id(query: CallbackQuery) -> int | None:
    user = getattr(query, "from_user", None)
    if user is None:
        return None
    return user.id

def get_callback_user_display_name(query: CallbackQuery) -> str:
    user = getattr(query, "from_user", None)
    if user is None:
        return "Unknown member"

    full_name = getattr(user, "full_name", None)
    if full_name:
        return full_name

    username = getattr(user, "username", None)
    if username:
        return f"@{username}"

    user_id = getattr(user, "id", None)
    if user_id is not None:
        return f"member {user_id}"

    return "Unknown member"


def get_message_chat_id(message: Message) -> int | None:
    chat_id = getattr(message, "chat_id", None)
    if chat_id is not None:
        return chat_id
    chat = getattr(message, "chat", None)
    return getattr(chat, "id", None)


def messages_are_from_same_chat(first_message: Message, second_message: Message) -> bool:
    first_chat_id = get_message_chat_id(first_message)
    second_chat_id = get_message_chat_id(second_message)

    return first_chat_id is not None and first_chat_id == second_chat_id
