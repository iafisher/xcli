"""
Autocompletion in the terminal.

Use the `input2` function with the `autocomplete` parameter instead of using this module
directly.

Author: Ian Fisher (iafisher@fastmail.com)
Version: October 2020
"""
import sys
import termios
import tty

UP = (27, 91, 65)
DOWN = (27, 91, 66)


class Autocomplete:
    """
    Autocompletion in the terminal.

    Use it like this:

        with Autocomplete(completer) as ac:
            response = ac.input("? ")

    Autocompletion requires changing some terminal settings. The context manager will
    automatically restore the previous settings on exit.

    If you don't use the context manager, make sure you call `Autocomplete.close` before
    you try to write to or read from the terminal, and note that the terminal settings
    are changed as soon as Autocomplete is initialized.
    """

    def __init__(self, completer):
        self.completer = completer
        self.cursor_pos = 0
        self.displayed_choices = []
        self.selected = None

        # Initialize the terminal.
        self.old_settings = termios.tcgetattr(sys.stdout.fileno())
        tty.setcbreak(sys.stdout.fileno())

    def input(self, prompt):
        sys.stdout.write(prompt)
        sys.stdout.flush()
        actual_chars = []
        chars = []
        self.cursor_pos = len(prompt)
        while True:
            c = sys.stdin.read(1)
            if c == "\n":
                break

            choices_for_empty_string = False
            # TODO: Support Tab key.
            if c == chr(127):
                self.unselect()
                chars = actual_chars[:]
                if chars:
                    actual_chars.pop()
                    chars.pop()
            elif c == chr(27):
                # TODO: Support Tab and Right Arrow keys.
                c2, c3 = sys.stdin.read(2)
                sequence = (ord(c), ord(c2), ord(c3))
                if sequence == UP:
                    self.select_up()
                elif sequence == DOWN:
                    choices_for_empty_string = True
                    if self.selected is None:
                        actual_chars = chars

                    self.select_down()
                else:
                    continue

                if self.selected is not None:
                    chars = list(self.displayed_choices[self.selected])
                else:
                    chars = actual_chars[:]
            else:
                self.unselect()
                chars.append(c)
                actual_chars.append(c)

            clear_line()
            return_to_start()
            sys.stdout.write(prompt)
            sys.stdout.write("".join(chars))
            sys.stdout.flush()
            self.cursor_pos = len(prompt) + len(chars)

            relevant = self.get_relevant_choices(
                "".join(actual_chars), empty_string=choices_for_empty_string
            )
            self.clear_choices()
            self.display_choices(relevant)
            cursor_right(self.cursor_pos)

        self.clear_choices()
        cursor_down_and_start()
        return "".join(chars)

    def close(self):
        termios.tcsetattr(sys.stdout.fileno(), termios.TCSADRAIN, self.old_settings)

    def unselect(self):
        self.selected = None

    def select_up(self):
        if self.selected is None:
            return

        if self.selected == 0:
            self.unselect()
            return

        self.selected -= 1

    def select_down(self):
        if (
            self.selected is not None
            and self.selected >= len(self.displayed_choices) - 1
        ):
            return

        if not self.displayed_choices:
            return

        if self.selected is None:
            self.selected = 0
        else:
            self.selected += 1

    def get_relevant_choices(self, chars, *, empty_string=False):
        if not empty_string and not chars:
            return []

        return self.completer(chars)

    def clear_choices(self):
        n = len(self.displayed_choices)
        cursor_down()
        for _ in range(n):
            clear_line()
            cursor_down()

        for _ in range(n + 1):
            cursor_up()

        self.displayed_choices.clear()

    def display_choices(self, choices):
        cursor_down_and_start()
        for i, choice in enumerate(choices):
            if self.selected == i:
                sys.stdout.write("\033[7m")
                sys.stdout.write(choice + "\n")
                sys.stdout.write("\033[0m")
            else:
                sys.stdout.write(choice + "\n")

        for _ in range(len(choices) + 1):
            cursor_up()

        self.displayed_choices = choices

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()


def sequence_to_autocomplete(sequence, *, fuzzy=False):
    """
    Converts a sequence into an autocomplete function.

    By default, matching is at the front only, i.e. if I type 'Af' it will suggest
    'Afghanistan' but not 'Central African Republic'. To match anywhere in the input,
    set the `fuzzy` parameter to True.

    Matching is case-insensitive.
    """
    sequence = [x.lower() for x in sequence]
    if fuzzy:
        return lambda chars: [x for x in sequence if x in chars.lower()]
    else:
        return lambda chars: [x for x in sequence if x.startswith(chars.lower())]


def backspace():
    cursor_left()
    sys.stdout.write(" ")
    cursor_left()


def clear_line():
    csi("2K")


def return_to_start():
    csi("G")


def cursor_down():
    csi("B")


def cursor_left(n=1):
    csi(str(n) + "D")


def cursor_right(n=1):
    csi(str(n) + "C")


def cursor_up_and_start():
    csi("F")


def cursor_down_and_start():
    csi("E")


def cursor_up():
    csi("A")


def csi(code):
    sys.stdout.write("\x1b[" + code)
    sys.stdout.flush()


def d(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)
    sys.stderr.flush()
