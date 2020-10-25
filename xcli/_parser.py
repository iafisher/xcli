import keyword
import os
import sys
from collections import OrderedDict

from ._exception import XCliError
from ._output import Table

# Singleton object to distinguish between passing `None` as a parameter and not passing
# anything at all.
Nothing = object()


def parse_args(*args, **kwargs):
    """
    Helper function to construct a Parser instance and immediately parse the command-
    line arguments.
    """
    parser = Parser(*args, **kwargs)
    return parser.parse()


def dispatch(*args, **kwargs):
    """
    Helper function to construct a Parser instance and immediately dispatch on the
    command-line arguments.
    """
    parser = Parser(*args, **kwargs)
    parser.dispatch()


class Arg:
    """
    Represents a positional argument.
    """

    def __init__(self, name, *, help="", default=Nothing, type=None):
        """
        Parameters:
            name: The name of the argument, to be displayed in the help message.

            help: A help string describing the purpose/usage of the arg.

            default: The default value for the arg. Note that passing default=None is
                different from leaving it unspecified: if `default` is unspecified and
                the argument is omitted from the command-line, it will cause an error,
                whereas if `default` is None, the arg's value will be set to None.

            type: The type of the argument. Should be a function that accepts and
                returns a single value, e.g. `int` or `float`.
        """
        self.name = name
        self.help = help
        self.default = default
        self.type = type


class Flag:
    """
    Represents a flag argument.
    """

    def __init__(
        self, name, longname="", *, help="", arg=False, required=False, default=Nothing
    ):
        """
        Parameters:
            name: The name of the flag. Must begin with a dash.

            longname: The optional long name of the flag. Must begin with two dashes.

            help: A help string describing the purpose/usage of the flag.

            arg: Whether the flag takes an argument or not.

            required: Whether the flag is required or not. Only accepted if `arg` is
                True.

            default: The default value for the flag. Note that passing default=None is
                different from leaving it unspecified: if `default` is unspecified, the
                flag is required, and it is omitted from the command-line, it will cause
                an error, whereas if `default` is None, the flag's value will be set to
                None.
        """
        self.name = name
        self.longname = longname
        self.help = help
        self.arg = arg
        self.required = required
        self.default = default

    def get_name(self):
        return self.longname or self.name


class Args(OrderedDict):
    """
    Represents a program's parsed command-line arguments.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.subcommand = None
        self.help = False


class Parser:
    def __init__(
        self,
        *,
        program=None,
        args=None,
        flags=None,
        subcommands=None,
        default_subcommand=None,
        helpless=False,
        dispatch=None,
    ):
        """
        Parameters:
            program: The name of the program, to display in the help string. Defaults to
                `sys.argv[0]`.

            args: The program's positional arguments, as a list of strings and Arg
                instances. If this parameter is specified, then `subcommands` must be
                None.

            flags: The program's flags, as a list of strings and Flag instances.

            subcommands: The program's subcommands, as a map from strings to Parser
                instances. If this parameter is specified, then `args` must be None.

            default_subcommand: The default subcommand to use, if no subcommand was
                specified on the command line.

            helpless: If True, the parser will not recognize --help as a special flag or
                help as a special subcommand.

            dispatch: A function to dispatch to. Should only be specified for Parsers
                for a subcommand.
        """

        if args is None:
            args = []
        else:
            args = [Arg(arg) if isinstance(arg, str) else arg for arg in args]

        if flags is None:
            flags = []
        else:
            flags = [Flag(flag) if isinstance(flag, str) else flag for flag in flags]

        if subcommands is None:
            subcommands = {}

        if default_subcommand is not None and default_subcommand not in subcommands:
            raise XCliError("default subcommand does not match any known subcommands")

        self.verify_args(args)
        self.verify_flags(flags)

        if args and subcommands:
            raise XCliError("cannot have both arguments and subcommands")

        self.args = args
        self.flags = {}
        self.flag_nicknames = {}
        for flag in flags:
            self.flags[flag.get_name()] = flag
            if flag.name and flag.longname:
                self.flag_nicknames[flag.name] = flag.get_name()

        for subcommand, subparser in subcommands.items():
            if subparser.subcommands:
                raise XCliError("subcommand cannot have subcommands of its own")

            subparser.parent_parser = self
            subparser.parent_parser_subcommand = subcommand

        self.program = os.path.basename(sys.argv[0]) if program is None else program
        self.subcommands = subcommands
        self.default_subcommand = default_subcommand
        self.helpless = helpless
        # It can't be called `dispatch` because that would conflict with the method.
        self.dispatch_function = dispatch
        self.parent_parser = None
        self.parent_parser_subcommand = None

    def dispatch(self, args=None):
        # NOTE: This method can raise an exception when the parser is mis-configured,
        # but for any errors caused by the actual command-line arguments that are being
        # parsed, it should print an error message instead.

        if not self.subcommands:
            raise XCliError("cannot dispatch without subcommands")

        result = self.parse(args)
        dispatch_function = self.subcommands[result.subcommand].dispatch_function

        if not dispatch_function:
            raise XCliError(
                f"no dispatch function defined for subcommand: {result.subcommand}"
            )

        args = []
        kwargs = {}
        # This loop relies on the fact that `result` is an ordered dictionary so that
        # the positional arguments are passed to the dispatch function in the correct
        # order.
        for name, value in result.items():
            if name.startswith("-"):
                name = name.lstrip("-").replace("-", "_")
                if not name.isidentifier():
                    raise XCliError(
                        f"flag name is not a valid Python identifier: {name}"
                    )

                if keyword.iskeyword(name):
                    raise XCliError(f"flag name is a Python keyword: {name}")

                kwargs[name] = value
            else:
                args.append(value)

        dispatch_function(*args, **kwargs)

    def parse(self, args=None):
        if args is None:
            args = sys.argv[1:]

        try:
            result = self._parse(args)
        except XCliError as e:
            print(f"Error: {e}\n", file=sys.stderr)
            # TODO: Use textwrap.
            print(self.usage(), file=sys.stderr)
            sys.exit(1)

        if result.help:
            if result.help is True:
                print(self.usage())
            else:
                print(self.subcommands[result.help].usage())
            sys.exit(0)
        else:
            return result

        # TODO: Handle --help.

    def _parse(self, args):
        state = ParseState(args)

        while state.index < len(args):
            arg = args[state.index]

            if not self.helpless:
                if arg == "--help":
                    state.result.help = True
                    return state.result
                elif self.subcommands and arg == "help":
                    if (
                        state.index + 1 < len(args)
                        and args[state.index + 1] in self.subcommands
                    ):
                        state.result.help = args[state.index + 1]
                    else:
                        state.result.help = True
                    return state.result

            if arg.startswith("-"):
                self.handle_flag(state, arg)
            else:
                if self.subcommands:
                    self.handle_subcommand(state, arg)
                else:
                    self.handle_arg(state, arg)

        self.fill_in_default_args(state)

        if self.subcommands and state.result.subcommand is None:
            raise XCliError("missing subcommand")

        return state.result

    def handle_arg(self, state, arg):
        if state.args_index >= len(self.args):
            raise XCliError(f"extra argument: {arg}")

        argspec = self.args[state.args_index]
        if argspec.type is not None:
            try:
                arg = argspec.type(arg)
            except Exception as e:
                raise XCliError(f"could not parse typed argument: {arg}") from e

        state.result[argspec.name] = arg
        state.args_index += 1
        state.index += 1

    def handle_flag(self, state, flag):
        if "=" in flag:
            flag, arg = flag.split("=", maxsplit=1)
        else:
            arg = None

        flagspec = self.flags.get(flag)
        if flagspec is None:
            nickname = self.flag_nicknames.get(flag)
            if nickname is None:
                raise XCliError(f"unknown flag: {flag}")

            flagspec = self.flags.get(nickname)

        if flagspec.arg:
            if not arg:
                if state.index == len(state.args) - 1:
                    raise XCliError(f"missing argument for flag: {flag}")

                arg = state.args[state.index + 1]

            state.result[flagspec.get_name()] = arg
            state.index += 2
        else:
            if arg:
                raise XCliError(f"flag does not take argument: {flag}")

            state.result[flagspec.get_name()] = True
            state.index += 1

    def handle_subcommand(self, state, subcommand):
        subparser = self.subcommands.get(subcommand)
        if subparser is None:
            if self.default_subcommand is None:
                raise XCliError(f"unknown subcommand: {subcommand}")

            subcommand = self.default_subcommand
            subparser = self.subcommands[self.default_subcommand]
            start_index = state.index
        else:
            start_index = state.index + 1

        result = subparser._parse(state.args[start_index:])
        state.index = len(state.args)
        state.result.update(result)
        state.result.subcommand = subcommand

    def fill_in_default_args(self, state):
        while state.args_index < len(self.args):
            argspec = self.args[state.args_index]
            if argspec.default is not Nothing:
                state.result[argspec.name] = argspec.default
            else:
                raise XCliError(f"missing argument: {argspec.name}")

            state.args_index += 1

        for flagspec in self.flags.values():
            if flagspec.get_name() not in state.result:
                if flagspec.default is not Nothing:
                    state.result[flagspec.get_name()] = flagspec.default
                elif flagspec.required:
                    raise XCliError(f"missing required flag: {flagspec.name}")
                else:
                    state.result[flagspec.get_name()] = None if flagspec.arg else False

    def usage(self):
        builder = []
        builder.append("Usage: ")
        if not self.parent_parser:
            builder.append(self.program)
        else:
            builder.append(self.parent_parser.program)
            builder.append(" ")
            builder.append(self.parent_parser_subcommand)
        brief_usage = self.brief_usage()
        if brief_usage:
            builder.append(" ")
            builder.append(brief_usage)

        if self.subcommands:
            builder.append("\n\n")
            builder.append("Subcommands:")
            for subcommand, parser in self.subcommands.items():
                builder.append("\n")
                builder.append("  ")
                builder.append(subcommand)
                brief_usage = parser.brief_usage()
                if brief_usage:
                    builder.append(" ")
                    builder.append(brief_usage)

        if self.args:
            builder.append("\n\n")
            builder.append("Positional arguments:\n")
            table = Table(padding=4)
            for spec in self.args:
                table.row("  " + spec.name, spec.help)

            builder.append(str(table))

        if self.flags:
            builder.append("\n\n")
            builder.append("Flags:\n")
            table = Table(padding=4)
            for spec in sorted(self.flags.values(), key=lambda spec: spec.name):
                if spec.longname:
                    name = spec.name + ", " + spec.longname
                else:
                    name = spec.name

                if spec.arg:
                    table.row(f"  {name} <arg>", spec.help)
                else:
                    table.row(f"  {name}", spec.help)

                builder.append(str(table))

        if self.subcommands and not self.helpless:
            builder.append("\n\n")
            builder.append(f"Run `{self.program} help <subcommand>` for detailed help.")

        return "".join(builder)

    def brief_usage(self):
        builder = []
        for flag in sorted(self.flags.values(), key=lambda spec: spec.name):
            if flag.required and flag.arg:
                builder.append(flag.name + "=<arg>")

        for spec in self.args:
            if spec.default is not Nothing:
                builder.append("[<" + spec.name + ">]")
            else:
                builder.append("<" + spec.name + ">")

        if self.subcommands:
            builder.append("<subcommand>")

        return " ".join(builder)

    def verify_args(self, args):
        taken = set()
        seen_default = False
        for spec in args:
            if spec.default is not Nothing:
                seen_default = True

            if spec.name.startswith("-"):
                raise XCliError(f"positional name may not start with dash: {spec.name}")

            if spec.default is Nothing and seen_default:
                raise XCliError(
                    "argument without default may not follow one with default"
                )

            if spec.name in taken:
                raise XCliError(f"duplicate argument: {spec.name}")

            taken.add(spec.name)

    def verify_flags(self, flags):
        taken = set()
        for spec in flags:
            if spec.name in taken:
                raise XCliError(f"duplicate flag: {spec.name}")

            if spec.longname and spec.longname in taken:
                raise XCliError(f"duplicate flag: {spec.longname}")

            if spec.required and not spec.arg:
                raise XCliError(
                    f"flag cannot be required without an arg: {spec.get_name()}"
                )

            taken.add(spec.name)
            if spec.longname:
                taken.add(spec.longname)


class ParseState:
    def __init__(self, args):
        self.args = args
        self.index = 0
        self.args_index = 0
        self.result = Args()
