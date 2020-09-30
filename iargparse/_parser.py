import sys


class Parser:
    def __init__(self, *, helpless=False, optional_subcommands=False):
        self.positionals = []
        self.flags = {}
        self.subcommands = {}
        self.helpless = helpless
        self.optional_subcommands = optional_subcommands

    def arg(self, name, *, default=None, type=None):
        # TODO: Help text.
        if name.startswith("-"):
            raise IargparseError(f"argument name cannot start with dash: {name}")

        if default is None and any(p.default is not None for p in self.positionals):
            raise IargparseError(
                "argument without default may not follow one with default"
            )

        if any(p.name == name for p in self.positionals):
            raise IargparseError(f"duplicate argument name: {name}")

        if name in self.subcommands:
            raise IargparseError("argument cannot have same name as subcommand")

        self.positionals.append(ArgSpec(name, default=default, type=type))
        return self

    def flag(self, name, longname=None, *, arg=False, default=None, required=False):
        if required is True and arg is False:
            raise IargparseError("flag without an argument cannot be required")

        if not name.startswith("-"):
            raise IargparseError(f"flag name must start with dash: {name}")

        if name in self.flags:
            raise IargparseError(f"duplicate flag name: {name}")

        spec = FlagSpec(longname or name, arg=arg, default=default, required=required)
        self.flags[name] = spec
        if longname:
            self.flags[longname] = spec
        return self

    def subcommand(self, name):
        if any(p.name == name for p in self.positionals):
            raise IargparseError("subcommand cannot have same name as argument")

        subparser = Parser()
        self.subcommands[name] = subparser
        return subparser

    def parse(self, args):
        if args is None:
            args = sys.argv[1:]

        try:
            return self._parse(args)
        except IargparseError as e:
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
            raise IargparseError("too few arguments")

        # Check for missing flags and set to False or default value if not required.
        for flag in self.flags.values():
            if flag.name not in self.parsed_args:
                if flag.required and flag.default is None:
                    raise IargparseError(f"missing flag: {flag.name}")

                self.parsed_args[flag.name] = (
                    False if flag.default is None else flag.default
                )

        return self.parsed_args

    def _handle_arg(self):
        arg = self.args[self.args_index]
        if self.positionals_index >= len(self.positionals):
            raise IargparseError(f"extra argument: {arg}")

        spec = self.positionals[self.positionals_index]
        if spec.type is not None:
            try:
                arg = spec.type(arg)
            except Exception as e:
                raise IargparseError(f"could not parse typed argument: {arg}") from e

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
        elif flag in self.flags:
            spec = self.flags[flag]
            if spec.arg:
                # Value may be provided as part of the flag string, e.g. `--x=y`.
                if value is not None:
                    self.parsed_args[spec.name] = value
                    self.args_index += 1
                    return

                if self.args_index == len(self.args) - 1:
                    raise IargparseError(f"expected argument for {flag}")

                self.parsed_args[spec.name] = self.args[self.args_index + 1]
                self.args_index += 2
            else:
                self.parsed_args[spec.name] = True
                self.args_index += 1
        else:
            raise IargparseError(f"unknown flag: {flag}")

    def _handle_subcommand(self):
        arg = self.args[self.args_index]
        if arg not in self.subcommands:
            if self.optional_subcommands:
                self._handle_arg()
                return
            else:
                raise IargparseError(f"unknown subcommand: {arg}")

        self.parsed_args.subcommand = arg
        subparser = self.subcommands[arg]
        self.parsed_args[arg] = subparser._parse(self.args[self.args_index + 1 :])
        # Set `args_index` to the length of `args` so that parsing ends after this
        # method returns.
        self.args_index = len(self.args)

    def usage(self):
        # TODO: Unit tests for usage string.
        builder = []
        builder.append("Usage:\n")
        if self.positionals:
            builder.append("  Positional arguments:\n")
            for positional in self.positionals:
                builder.append(f"    {positional.name}\n")

        if self.positionals and self.flags:
            builder.append("\n")

        if self.flags:
            builder.append("  Flags:\n")
            # TODO: This will print duplicates for flags with long names.
            for spec in sorted(self.flags.values(), key=lambda spec: spec.name):
                if spec.arg:
                    builder.append(f"    {spec.name} <arg>\n")
                else:
                    builder.append(f"    {spec.name}\n")

        # TODO: Show subcommands.

        return "".join(builder)


class Args(dict):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.subcommand = None


class IargparseError(Exception):
    pass


class ArgSpec:
    def __init__(self, name, *, default, type):
        self.name = name
        self.default = default
        self.type = type


class FlagSpec:
    def __init__(self, name, *, arg, default, required):
        self.name = name
        self.arg = arg
        self.default = default
        self.required = required
