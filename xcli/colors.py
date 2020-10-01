"""
Helper functions for displaying colored text using ANSI escape codes.

Often, programs want to turn off colored output in some circumstances, e.g. when writing
to a pipe or when the user specifies --no-color on the command-line. This module
supports turning off colored output globally with the `off` function, which causes all
the color functions to return their input unchanged. Thus, you can use the color
functions throughout your program without qualification, and disable them with a call to
`off` at start-up if necessary.

Author: Ian Fisher (iafisher@fastmail.com)
Version: September 2020
"""


_ON = True


def on():
    """
    Turns on colored text globally, so that subsequent calls to the color functions in
    this module will return text colored with ANSI escape codes.
    """
    global _ON
    _ON = True


def off():
    """
    Turns off colored text globally, so that subsequent calls to the color functions in
    this module will return regular text without color codes.
    """
    global _ON
    _ON = False


def black(text, *, bright=True):
    return _color(_COLOR_BLACK, text, bright=bright)


def red(text, *, bright=True):
    return _color(_COLOR_RED, text, bright=bright)


def green(text, *, bright=True):
    return _color(_COLOR_GREEN, text, bright=bright)


def yellow(text, *, bright=True):
    return _color(_COLOR_YELLOW, text, bright=bright)


def blue(text, *, bright=True):
    return _color(_COLOR_BLUE, text, bright=bright)


def magenta(text, *, bright=True):
    return _color(_COLOR_MAGENTA, text, bright=bright)


def cyan(text, *, bright=True):
    return _color(_COLOR_CYAN, text, bright=bright)


def white(text, *, bright=True):
    return _color(_COLOR_WHITE, text, bright=bright)


def rgb(text, red, blue, green):
    """
    Colors the text with the given RGB value.

    Note that arbitrary RGB colors are only supported on newer terminals. For better
    portability, consider using one of the named color functions instead.
    """
    return _color(f"38;2;{red};{green};{blue}", text, bright=False)


_COLOR_BLACK = 30
_COLOR_RED = 31
_COLOR_GREEN = 32
_COLOR_YELLOW = 33
_COLOR_BLUE = 34
_COLOR_MAGENTA = 35
_COLOR_CYAN = 36
_COLOR_WHITE = 37
_COLOR_RESET = 0


def _color(colorcode, text, *, bright):
    if bright:
        colorcode += 60

    if _ON:
        return f"\033[{colorcode}m{text}\033[{_COLOR_RESET}m"
    else:
        return text
