class MyLangRuntimeError(Exception):

    def __init__(
        self,
        message,
        line=None
    ):

        self.message = message
        self.line = line

        if line is not None:

            super().__init__(
                f"Line {line}: {message}"
            )

        else:

            super().__init__(message)