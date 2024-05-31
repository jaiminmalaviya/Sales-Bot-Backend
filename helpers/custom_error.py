class CustomEmbedError(Exception):
    """Custom error class."""
    def __init__(self, message):
        self.message = message
        super().__init__(self.message)
