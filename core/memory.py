from collections import deque


class ConversationMemory:

    def __init__(
        self,
        max_messages=10
    ):

        self.messages = deque(
            maxlen=max_messages
        )


    # =========================================================
    # USER
    # =========================================================

    def add_user(
        self,
        text
    ):

        if not text:

            return


        self.messages.append(
            {
                "role": "user",
                "content": str(text)
            }
        )


    # =========================================================
    # ASSISTANT
    # =========================================================

    def add_assistant(
        self,
        text
    ):

        if not text:

            return


        self.messages.append(
            {
                "role": "assistant",
                "content": str(text)
            }
        )


    # =========================================================
    # LIST
    # =========================================================

    def get_messages(
        self
    ):

        return list(
            self.messages
        )


    # =========================================================
    # CLEAR
    # =========================================================

    def clear(
        self
    ):

        self.messages.clear()