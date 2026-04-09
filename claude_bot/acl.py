from .config import cfg


def is_owner(chat_id: int) -> bool:
    return chat_id == cfg.owner_chat_id


def is_allowed_group(chat_id: int) -> bool:
    return chat_id in cfg.allowed_group_ids
