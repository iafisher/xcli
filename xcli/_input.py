import readline  # noqa: F401


def input2(prompt, *, choices=None, normalize=True, type=None, verify=None):
    """
    Prompts the user for input until their response satisfies the parameters.

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

    while True:
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
