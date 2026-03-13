from __future__ import annotations


class ChatError(Exception):
    def __init__(self, message: str = "Chat error") -> None:
        self.message = message
        super().__init__(self.message)


class EmptyMessageError(ChatError):
    def __init__(self, message: str = "Message content cannot be empty") -> None:
        super().__init__(message)


class MessageTooLongError(ChatError):
    def __init__(self, message: str = "Message content exceeds 5000 characters") -> None:
        super().__init__(message)


class MessageNotFoundError(ChatError):
    def __init__(self, message: str = "Message not found") -> None:
        super().__init__(message)


class ConversationNotFoundError(ChatError):
    def __init__(self, message: str = "Conversation not found") -> None:
        super().__init__(message)


class CannotMessageSelfError(ChatError):
    def __init__(self, message: str = "Cannot send message to yourself") -> None:
        super().__init__(message)
