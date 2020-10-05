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
BACKSPACE = chr(127)
ESCAPE = chr(27)
CTRL_D = chr(4)


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

    def __init__(self, completer, *, max_options=20):
        self.completer = completer
        self.max_options = max_options

        self.prompt = None
        # The horizontal position of the cursor.
        self.cursor_pos = 0
        self.chars = []
        # The choices, if any, currently displayed to the user.
        self.displayed_choices = []
        self.lines_below_cursor = 0
        # The index of the currently selected choice. If no choice is selected, then
        # `self.selected` is None.
        self.selected = None

        # Initialize the terminal.
        self.old_settings = termios.tcgetattr(sys.stdout.fileno())
        tty.setcbreak(sys.stdout.fileno())

    def input(self, prompt):
        self.prompt = prompt
        sys.stdout.write(self.prompt)
        sys.stdout.flush()
        self.chars.clear()
        self.cursor_pos = len(self.prompt)
        while True:
            c = sys.stdin.read(1)
            if c == "\n":
                break

            choices_for_empty_string = False
            # TODO: Support Tab key.
            if c == BACKSPACE:
                if self.selected is not None:
                    self.set_chars_to_selection()
                    self.unselect()

                if self.chars:
                    self.chars.pop()
            elif c == ESCAPE:
                # TODO: Support Tab and Right Arrow keys.
                c2, c3 = sys.stdin.read(2)
                sequence = (ord(c), ord(c2), ord(c3))
                if sequence == UP:
                    self.select_up()
                elif sequence == DOWN:
                    choices_for_empty_string = True
                    self.select_down()
                else:
                    continue
            elif c == CTRL_D:
                raise EOFError
            else:
                if self.selected is not None:
                    self.set_chars_to_selection()
                    self.unselect()
                self.chars.append(c)

            if self.selected is None:
                self.displayed_choices = self.get_relevant_choices(
                    "".join(self.chars), empty_string=choices_for_empty_string
                )

            self.handle_current_input()

        self.clear_choices()
        cursor_down_and_start()
        return "".join(self.chars)

    def close(self):
        termios.tcsetattr(sys.stdout.fileno(), termios.TCSADRAIN, self.old_settings)

    def handle_current_input(self):
        clear_line()
        return_to_start()
        sys.stdout.write(self.prompt)

        if self.selected is None:
            chars = "".join(self.chars)
        else:
            chars = self.displayed_choices[self.selected]

        sys.stdout.write(chars)
        self.cursor_pos = len(self.prompt) + len(chars)

        self.clear_choices()
        self.display_choices()
        sys.stdout.flush()

    def set_chars_to_selection(self):
        self.chars = list(self.displayed_choices[self.selected])

    def unselect(self):
        self.selected = None
        self.displayed_choices.clear()

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

        options = self.completer(chars)

        if self.max_options is not None:
            return options[: self.max_options]
        else:
            return options

    def clear_choices(self):
        n = self.lines_below_cursor
        cursor_down()
        for _ in range(n):
            clear_line()
            cursor_down()

        for _ in range(n + 1):
            cursor_up()

    def display_choices(self):
        cursor_down_and_start()

        for i, choice in enumerate(self.displayed_choices):
            if self.selected == i:
                sys.stdout.write("\033[7m")
                sys.stdout.write(choice + "\n")
                sys.stdout.write("\033[0m")
            else:
                sys.stdout.write(choice + "\n")

        self.lines_below_cursor = len(self.displayed_choices)

        for _ in range(len(self.displayed_choices) + 1):
            cursor_up()

        cursor_right(self.cursor_pos)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.clear_choices()
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
