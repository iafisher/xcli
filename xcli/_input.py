"""
An augmented input function.

Author: Ian Fisher (iafisher@fastmail.com)
Version: October 2020
"""
import readline  # noqa: F401
import sys
from collections.abc import Sequence

from ._autocomplete import Autocomplete, sequence_to_autocomplete


def input2(
    prompt,
    *,
    autocomplete=None,
    autocomplete_fuzzy=False,
    choices=None,
    normalize=True,
    type=None,
    verify=None
):
    """
    Prompts the user for input until their response satisfies the parameters.

    - If `autocomplete` is True, it should either be a list of autocompletion options,
      or a function that accepts the characters typed so far (as a string), and returns
      a list of autocompletion options.

    - If `normalize` is True, then leading and trailing whitespace is stripped.

    - If `type` is supplied, it should be a unary function, e.g. `int` or `float`, that
      will be applied to the response.

    - If `choices` is supplied, it should be a list or tuple. The response must be one
      of the values listed.

    - If `verify` is supplied, it should be a unary function that checks the validity
      of the response. Unlike `type`, the return value of `verify` is not assigned to
      the response.

    If the response fails any of the validation checks, the user is prompted again and
    again until they enter a valid response.
    """
    if choices is not None and verify is not None:
        raise ValueError("`choices` and `verify` may not both be specified")

    if isinstance(autocomplete, Sequence):
        autocomplete = sequence_to_autocomplete(autocomplete, fuzzy=autocomplete_fuzzy)

    while True:
        if autocomplete is not None:
            with Autocomplete(sys.stdout, sys.stdin, autocomplete) as ac:
                response = ac.input(prompt)
        else:
            response = input(prompt)

        if normalize:
            response = response.strip()

        if type is not None:
            try:
                response = type(response)
            except Exception:
                continue

        if choices is not None and response not in choices:
            continue

        if verify is not None and not verify(response):
            continue

        return response


def confirm(prompt):
    """
    Prompts the user to respond yes or no.
    """
    try:
        response = input2(prompt, verify=lambda s: s.lower().startswith(("y", "n")))
    except EOFError:
        print()
        return False
    else:
        return response.lower().startswith("y")
