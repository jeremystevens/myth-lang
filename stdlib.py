import random


class StandardLibrary:

    def upper(self, text):

        return str(text).upper()

    def lower(self, text):

        return str(text).lower()

    def length(self, text):

        return len(str(text))

    def random(self, start, end):

        return random.randint(
            int(start),
            int(end)
        )