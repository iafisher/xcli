import os
import sys

from ._exception import XCliError

# Singleton object to distinguish between passing `None` as a parameter and not passing
# anything at all.
Nothing = object()


class Arg:
    def __init__(self, name, *, default=Nothing, type=None):
        self.name = name
        self.default = default
        self.type = type


class Flag:
    def __init__(
        self, name, longname="", *, arg=False, required=False, default=Nothing
    ):
        self.name = name
        self.longname = longname
        self.arg = arg
        self.required = required
        self.default = default

    def get_name(self):
        return self.longname or self.name


class Args(dict):
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
    ):
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

        self.program = os.path.basename(sys.argv[0]) if program is None else program
        self.subcommands = subcommands
        self.default_subcommand = default_subcommand
        self.helpless = helpless

    def parse(self, args=None):
        if args is None:
            args = sys.argv[1:]

        try:
            result = self._parse(args)
        except XCliError as e:
            print(f"Error: {e}\n", file=sys.stderr)
            # TODO: Use textwrap.
            print(self.usage(), end="", flush=True, file=sys.stderr)
            sys.exit(1)

        if result.help:
            self.usage()
        else:
            return result

        # TODO: Handle --help.

    def _parse(self, args):
        state = ParseState(args)

        while state.index < len(args):
            arg = args[state.index]

            if arg == "--help" and not self.helpless:
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
        # TODO: Unit tests for usage string.
        builder = []
        builder.append("Usage: ")
        builder.append(self.program)
        builder.append(self._brief_usage())

        builder.append("\n\n")

        if self.subcommands:
            builder.append("Subcommands:\n")
            for subcommand, parser in self.subcommands.items():
                builder.append("  ")
                builder.append(subcommand)
                builder.append(parser._brief_usage())
                builder.append("\n")

        if self.args:
            builder.append("Positional arguments:\n")
            for spec in self.args:
                builder.append(f"  {spec.name}\n")

            if self.flags:
                builder.append("\n")

        if self.flags:
            builder.append("Flags:\n")
            # TODO: This will print duplicates for flags with long names.
            for spec in sorted(self.flags.values(), key=lambda spec: spec.get_name):
                if spec.longname:
                    name = spec.name + ", " + spec.longname
                else:
                    name = spec.name

                if spec.arg:
                    builder.append(f"  {name} <arg>\n")
                else:
                    builder.append(f"  {name}\n")

        return "".join(builder)

    def _brief_usage(self):
        builder = []
        for flag in sorted(self.flags.values(), key=lambda spec: spec.name):
            if flag.required and flag.arg:
                builder.append(" ")
                builder.append(flag.name + "=<arg>")

        for spec in self.args:
            builder.append(" ")
            if spec.default is not Nothing:
                builder.append("[<" + spec.name + ">]")
            else:
                builder.append("<" + spec.name + ">")

        if self.subcommands:
            builder.append(" <subcommand>")

        return "".join(builder)

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
