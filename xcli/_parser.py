import os
import sys


class Parser:
    def __init__(self, program=None, *, helpless=False, optional_subcommands=False):
        self.program = os.path.basename(sys.argv[0]) if not program else program
        self.positionals = []
        self.flag_nicknames = {}
        self.flags = {}
        self.subcommands = {}
        self.helpless = helpless
        self.optional_subcommands = optional_subcommands

    def arg(self, name, *, default=None, type=None):
        # TODO: Help text.
        if name.startswith("-"):
            raise XCliError(f"argument name cannot start with dash: {name}")

        if default is None and any(p.default is not None for p in self.positionals):
            raise XCliError("argument without default may not follow one with default")

        if any(p.name == name for p in self.positionals):
            raise XCliError(f"duplicate argument name: {name}")

        if name in self.subcommands:
            raise XCliError("argument cannot have same name as subcommand")

        self.positionals.append(ArgSpec(name, default=default, type=type))
        return self

    def flag(self, name, longname=None, *, arg=False, default=None, required=False):
        if required is True and arg is False:
            raise XCliError("flag without an argument cannot be required")

        if not name.startswith("-"):
            raise XCliError(f"flag name must start with dash: {name}")

        if name in self.flags:
            raise XCliError(f"duplicate flag name: {name}")

        spec = FlagSpec(name, longname, arg=arg, default=default, required=required)
        if longname:
            self.flags[longname] = spec
            self.flag_nicknames[name] = longname
        else:
            self.flags[name] = spec

        return self

    def subcommand(self, name):
        if any(p.name == name for p in self.positionals):
            raise XCliError("subcommand cannot have same name as argument")

        subparser = Parser()
        self.subcommands[name] = subparser
        return subparser

    def parse(self, args=None):
        if args is None:
            args = sys.argv[1:]

        try:
            return self._parse(args)
        except XCliError as e:
            print(f"Error: {e}\n", file=sys.stderr)
            # TODO: Use textwrap.
            print(self.usage(), file=sys.stderr)
            sys.exit(1)

        # TODO: Handle --help.

    def _parse(self, args):
        self.args = args
        self.parsed_args = Args()
        self.positionals_index = 0
        self.args_index = 0

        while self.args_index < len(self.args):
            arg = self.args[self.args_index]
            if arg.startswith("-"):
                self._handle_flag()
            elif self.positionals_index == 0 and self.subcommands:
                self._handle_subcommand()
            else:
                self._handle_arg()

        # Try to satisfy any missing positionals with default values.
        while self.positionals_index < len(self.positionals):
            spec = self.positionals[self.positionals_index]
            if spec.default is None:
                break

            self.parsed_args[spec.name] = spec.default
            self.positionals_index += 1

        if self.positionals_index < len(self.positionals):
            raise XCliError("too few arguments")

        # Check for missing flags and set to False or default value if not required.
        for flag in self.flags.values():
            if flag.get_name() not in self.parsed_args:
                if flag.required and flag.default is None:
                    raise XCliError(f"missing flag: {flag.get_name()}")

                self.parsed_args[flag.get_name()] = (
                    False if flag.default is None else flag.default
                )

        return self.parsed_args

    def _handle_arg(self):
        arg = self.args[self.args_index]
        if self.positionals_index >= len(self.positionals):
            raise XCliError(f"extra argument: {arg}")

        spec = self.positionals[self.positionals_index]
        if spec.type is not None:
            try:
                arg = spec.type(arg)
            except Exception as e:
                raise XCliError(f"could not parse typed argument: {arg}") from e

        self.parsed_args[self.positionals[self.positionals_index].name] = arg
        self.positionals_index += 1
        self.args_index += 1

    def _handle_flag(self):
        # TODO: Allow subcommands to start with dashes.
        flag = self.args[self.args_index]

        if "=" in flag:
            flag, value = flag.split("=", maxsplit=1)
        else:
            value = None

        if not self.helpless and flag == "--help":
            self.parsed_args["--help"] = True
            self.args_index += 1
        else:
            if flag in self.flag_nicknames:
                spec = self.flags[self.flag_nicknames[flag]]
            elif flag in self.flags:
                spec = self.flags[flag]
            else:
                raise XCliError(f"unknown flag: {flag}")

            if spec.arg:
                # Value may be provided as part of the flag string, e.g. `--x=y`.
                if value is not None:
                    self.parsed_args[spec.get_name()] = value
                    self.args_index += 1
                    return

                if self.args_index == len(self.args) - 1:
                    raise XCliError(f"expected argument for {flag}")

                self.parsed_args[spec.get_name()] = self.args[self.args_index + 1]
                self.args_index += 2
            else:
                self.parsed_args[spec.get_name()] = True
                self.args_index += 1

    def _handle_subcommand(self):
        arg = self.args[self.args_index]
        if arg not in self.subcommands:
            if self.optional_subcommands:
                self._handle_arg()
                return
            else:
                raise XCliError(f"unknown subcommand: {arg}")

        self.parsed_args.subcommand = arg
        subparser = self.subcommands[arg]
        self.parsed_args[arg] = subparser._parse(self.args[self.args_index + 1 :])
        # Set `args_index` to the length of `args` so that parsing ends after this
        # method returns.
        self.args_index = len(self.args)

    def usage(self):
        # TODO: Unit tests for usage string.
        builder = []
        builder.append("Usage: ")
        builder.append(self.program)
        for positional in self.positionals:
            builder.append(" ")
            if positional.default:
                builder.append("[" + positional.name + "]")
            else:
                builder.append(positional.name)

        builder.append("\n\n")

        if self.positionals:
            builder.append("Positional arguments:\n")
            for positional in self.positionals:
                builder.append(f"  {positional.name}\n")

        if self.positionals and self.flags:
            builder.append("\n")

        if self.flags:
            builder.append("Flags:\n")
            # TODO: This will print duplicates for flags with long names.
            for spec in sorted(self.flags.values(), key=lambda spec: spec.name):
                if spec.longname:
                    name = spec.name + ", " + spec.longname
                else:
                    name = spec.name

                if spec.arg:
                    builder.append(f"  {name} <arg>\n")
                else:
                    builder.append(f"  {name}\n")

        # TODO: Show subcommands.

        return "".join(builder)


class Args(dict):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.subcommand = None


class XCliError(Exception):
    pass


class ArgSpec:
    def __init__(self, name, *, default, type):
        self.name = name
        self.default = default
        self.type = type


class FlagSpec:
    def __init__(self, name, longname, *, arg, default, required):
        self.name = name
        self.longname = longname
        self.arg = arg
        self.default = default
        self.required = required

    def get_name(self):
        return self.longname if self.longname else self.name
