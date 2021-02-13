import keyword
import sys
from collections import OrderedDict

from ._exception import XCliError


class NothingCls:
    def __repr__(self):
        return "<Nothing>"


# Singleton object to distinguish between passing `None` as a parameter and not passing
# anything at all.
Nothing = NothingCls()


class ArgumentParser:
    def __init__(self, args=None, *, helpless=False, name=None, description=None):
        self.schema = Schema.from_args(args or [], helpless=helpless)
        self.name = name or sys.argv[0]
        self.description = description

    def parse(self, args=None, *, interactive=True):
        if args is None:
            args = sys.argv[1:]

        try:
            result = ParserImpl(self.schema, args).parse()
        except XCliError as e:
            if interactive:
                print("Error: " + str(e), file=sys.stderr)
                sys.exit(1)
            else:
                raise e

        if interactive and result.help:
            if result.subcommand:
                subcommand = self.schema.subcommands[result.subcommand]
                print(
                    UsageBuilder().build(
                        subcommand.schema,
                        name=self.name,
                        subcommand=subcommand.name,
                        description=self.description,
                    ),
                    file=sys.stderr,
                )
            else:
                print(
                    UsageBuilder().build(
                        self.schema, name=self.name, description=self.description
                    ),
                    file=sys.stderr,
                )
            sys.exit(0)
        else:
            return result

    def dispatch(self, args=None, dispatch=None, *, interactive=True):
        if dispatch is None:
            if not self.schema.subcommands:
                raise XCliError("no dispatch function")

            for name, subcommand in self.schema.subcommands.items():
                if not subcommand.dispatch:
                    raise XCliError(f"no dispatch function for subcommand: {name}")

        result = self.parse(args=args, interactive=interactive)
        if result.subcommand:
            dispatch = self.schema.subcommands[result.subcommand].dispatch

        args = []
        kwargs = {}
        # This loop relies on the fact that `result` is an ordered dictionary so that
        # the positional arguments are passed to the dispatch function in the correct
        # order.
        for name, value in result.items():
            if name.startswith("-"):
                kwarg_name = name.lstrip("-").replace("-", "_")
                if not kwarg_name.isidentifier():
                    raise XCliError(
                        f"flag name is not a valid Python identifier: {name}"
                    )

                if keyword.iskeyword(kwarg_name):
                    kwarg_name = kwarg_name + "_"

                kwargs[kwarg_name] = value
            else:
                args.append(value)

        dispatch(*args, **kwargs)


class Arg:
    def __init__(self, name, *, default=Nothing, help="", type=None):
        self.name = name
        self.default = default
        self.help = help
        self.type = type

    def __repr__(self):
        return f"Arg({self.name!r}, default={self.default!r}, type={self.type!r})"


class Flag:
    def __init__(
        self, name, longname="", *, arg=False, default=Nothing, help="", type=None
    ):
        if not arg:
            if type is not None:
                raise XCliError("flag with `arg=False` cannot have `type`")

            if default is not Nothing:
                raise XCliError("flag with `arg=False` cannot have default value")

        self.name = name
        self.longname = longname
        self.arg = arg
        self.default = default
        self.help = help
        self.type = type

    def get_name(self):
        return self.name if not self.longname else self.longname

    def __repr__(self):
        return (
            f"Flag({self.name!r}, longname={self.longname!r}, "
            + f"arg={self.arg!r}, default={self.default!r}, type={self.type!r})"
        )


class Subcommand:
    def __init__(self, name, args=None, *, dispatch=None, help=""):
        self.name = name
        self.schema = Schema.from_args(args or [], is_subcommand=True)
        self.dispatch = dispatch
        self.help = help

    def __repr__(self):
        return f"Subcommand({self.name!r}, {self.args!r}, dispatch={self.dispatch!r})"


class ParsedArguments(OrderedDict):
    def __init__(self, *args, help=False, subcommand=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.help = help
        self.subcommand = subcommand

    def __repr__(self):
        items = ", ".join(
            "({!r}, {!r})".format(key, value) for key, value in self.items()
        )
        return (
            "ParsedArguments(["
            + items
            + f"], help={self.help!r}, subcommand={self.subcommand!r})"
        )


class ParserImpl:
    def __init__(self, schema, args):
        self.schema = schema
        self.args = args
        self.index = 0
        self.schema_index = 0
        self.result = ParsedArguments()

    def parse(self):
        seen_dash_separator = False
        while self.index < len(self.args):
            arg = self.args[self.index]
            if not self.schema.helpless and arg == "--help":
                self.result.help = True
                return self.result
            elif arg == "--":
                seen_dash_separator = True
                self.index += 1
            elif not seen_dash_separator and arg.startswith("-"):
                self._handle_flag()
            elif self.schema.subcommands:
                self._handle_subcommand()
            else:
                self._handle_positional()

        self._handle_missing_args()
        return self.result

    def _handle_positional(self):
        arg = self.args[self.index]
        if self.schema_index < len(self.schema.positionals):
            spec = self.schema.positionals[self.schema_index]
            if spec.type is not None:
                try:
                    arg = spec.type(arg)
                except Exception as e:
                    raise XCliError(
                        f"could not parse value for `{spec.name}`: {arg}"
                    ) from e

            self.result[spec.name] = arg
            self.schema_index += 1
            self.index += 1
        else:
            raise XCliError(f"extra argument: {arg}")

    def _handle_flag(self):
        flag = self.args[self.index]
        if "=" in flag:
            flag, flag_arg = flag.split("=", maxsplit=1)
        else:
            flag_arg = None

        spec = self.schema.get_flag(flag)
        if spec is not None:
            if spec.arg:
                if flag_arg is None:
                    if self.index + 1 >= len(self.args):
                        raise XCliError(f"expected argument to flag: {flag}")

                    flag_arg = self.args[self.index + 1]
                    self.index += 1

                if spec.type is not None:
                    try:
                        flag_arg = spec.type(flag_arg)
                    except Exception as e:
                        raise XCliError(
                            f"could not parse value for `{flag}`: {flag_arg}"
                        ) from e

                self.result[spec.get_name()] = flag_arg
                self.index += 1
            else:
                if flag_arg is not None:
                    raise XCliError(f"flag does not take argument: {flag}")

                self.result[spec.get_name()] = True
                self.index += 1
        else:
            raise XCliError(f"unknown flag: {flag}")

    def _handle_subcommand(self):
        subcommand = self.args[self.index]
        spec = self.schema.subcommands.get(subcommand)
        subresult = ParserImpl(spec.schema, self.args[self.index + 1 :]).parse()
        self.result.update(subresult)
        self.result.subcommand = subcommand
        self.result.help = subresult.help
        self.index = len(self.args)

    def _handle_missing_args(self):
        while self.schema_index < len(self.schema.positionals):
            missing = self.schema.positionals[self.schema_index]
            if missing.default is not Nothing:
                self.result[missing.name] = missing.default
                self.schema_index += 1
            else:
                raise XCliError(f"missing argument: {missing.name}")

        for flag in self.schema.flags.values():
            if flag.get_name() not in self.result:
                if flag.arg:
                    if flag.default is not Nothing:
                        self.result[flag.get_name()] = flag.default
                    else:
                        raise XCliError(f"missing flag: {flag.get_name()}")
                else:
                    self.result[flag.get_name()] = False


class Schema:
    def __init__(
        self, positionals, flags, subcommands, *, dispatch=None, helpless=False
    ):
        self.positionals = positionals
        self.flags = flags
        self.flag_nicknames = {
            flag.name: flag for flag in self.flags.values() if flag.longname
        }
        self.subcommands = subcommands
        self.dispatch = dispatch
        self.helpless = helpless

    @classmethod
    def from_args(cls, args, *, dispatch=None, helpless=False, is_subcommand=False):
        names_taken = set()
        seen_optional_positional = False
        positionals = []
        flags = {}
        subcommands = {}
        for arg in args:
            if isinstance(arg, Arg):
                if arg.name in names_taken:
                    raise XCliError(f"duplicate argument name: {arg.name}")

                if arg.name.startswith("-"):
                    raise XCliError(
                        f"argument name must not begin with dash: {arg.name}"
                    )

                if arg.default is not Nothing:
                    seen_optional_positional = True
                elif seen_optional_positional:
                    raise XCliError(
                        f"required argument cannot follow optional one: {arg.name}"
                    )

                positionals.append(arg)
                names_taken.add(arg.name)
            elif isinstance(arg, Flag):
                if arg.name in names_taken:
                    raise XCliError(f"duplicate flag name: {arg.name}")

                if not arg.name.startswith("-"):
                    raise XCliError(f"flag name must begin with dash: {arg.name}")

                if arg.longname:
                    if arg.name.startswith("--"):
                        raise XCliError(
                            f"short flag name must begin with single dash: {arg.name}"
                        )

                    if not arg.longname.startswith("--"):
                        raise XCliError(
                            f"long flag name must begin with double dash: {arg.longname}"
                        )

                    if arg.longname in names_taken:
                        raise XCliError(f"duplicate flag name: {arg.longname}")

                flags[arg.get_name()] = arg
                names_taken.add(arg.name)
                if arg.longname:
                    names_taken.add(arg.longname)

                if arg.get_name() == "--help":
                    helpless = True
            elif isinstance(arg, Subcommand):
                if is_subcommand:
                    raise XCliError("subcommands cannot be nested")

                if arg.name in subcommands:
                    raise XCliError(f"duplicate subcommand name: {arg.name}")

                subcommands[arg.name] = arg
            else:
                raise XCliError(
                    f"expected Arg, Flag or Subcommand instance, got: {arg!r}"
                )

        if positionals and subcommands:
            raise XCliError("Arg and Subcommand objects cannot both be present")

        return cls(
            positionals=positionals,
            flags=flags,
            subcommands=subcommands,
            dispatch=dispatch,
            helpless=helpless,
        )

    def get_flag(self, name):
        return self.flags.get(name, self.flag_nicknames.get(name))


class UsageBuilder:
    # TODO(2021-02-11): Fixed-width

    def __init__(self):
        self.sections = []

    def build(self, schema, *, name, description=None, subcommand=None):
        args = self._get_true_args(schema)
        flags = self._get_true_flags(schema)

        self._build_lead_section(name, subcommand, schema, description)

        if schema.subcommands:
            self._build_subcommands_section(list(schema.subcommands.values()))

        if args:
            self._build_args_section(args)

        if flags:
            self._build_flags_section(flags)

        if schema.subcommands:
            self.sections.append([f"Run `{name} subcommand --help` for detailed help."])

        if subcommand:
            self.sections.append([f"Run `{name} --help` for general help."])

        if not schema.positionals and not schema.flags and not schema.subcommands:
            self.sections.append(["This program accepts no flags or arguments."])

        return "\n\n".join("\n".join(section) for section in self.sections)

    def _build_lead_section(self, name, subcommand, schema, description):
        section = []
        if description and not subcommand:
            section.append(name + ": " + description)
            section.append("")

        if subcommand:
            name = name + " " + subcommand

        section.append("Usage: " + self._get_usage_string(name, schema))
        self.sections.append(section)

    def _get_usage_string(self, name, schema):
        args = self._get_true_args(schema)
        arg_string = " ".join(
            "<" + spec.name + ">"
            if isinstance(spec, Arg)
            else spec.get_name() + " <arg>"
            for spec in args
            if spec.default is Nothing
        )
        if arg_string:
            return f"{name} {arg_string}"
        elif schema.subcommands:
            return f"{name} <subcommand>"
        else:
            return name

    def _build_subcommands_section(self, subcommands):
        section = ["Subcommands:"]
        table_builder = TableBuilder()
        for spec in sorted(subcommands, key=lambda spec: spec.name):
            table_builder.add_row(
                self._get_usage_string(spec.name, spec.schema), spec.help
            )

        section.extend(table_builder.build())
        self.sections.append(section)

    def _build_args_section(self, args):
        section = ["Arguments:"]
        table_builder = TableBuilder()
        for spec in args:
            if isinstance(spec, Arg):
                table_builder.add_row("<" + spec.name + ">", spec.help)
            else:
                if spec.longname:
                    table_builder.add_row(
                        spec.name + ", " + spec.longname + " <arg>", spec.help
                    )
                else:
                    table_builder.add_row(spec.name + " <arg>", spec.help)

        section.extend(table_builder.build())
        self.sections.append(section)

    def _build_flags_section(self, flags):
        section = ["Flags:"]
        table_builder = TableBuilder()
        for spec in sorted(flags, key=lambda spec: spec.get_name()):
            if spec.longname:
                table_builder.add_row(spec.name + ", " + spec.longname, spec.help)
            else:
                table_builder.add_row(spec.name, spec.help)

        section.extend(table_builder.build())
        self.sections.append(section)

    def _get_true_args(self, schema):
        return schema.positionals + [spec for spec in schema.flags.values() if spec.arg]

    def _get_true_flags(self, schema):
        return [spec for spec in schema.flags.values() if not spec.arg]


class TableBuilder:
    def __init__(self, *, indent=2):
        self.indent = indent
        self.rows = []
        self.max_width = 0

    def add_row(self, left, right):
        self.max_width = max(self.max_width, len(left))
        self.rows.append((left, right))

    def build(self):
        rows = []
        for left, right in self.rows:
            row = (" " * self.indent) + left.ljust(self.max_width) + "    " + right
            row = row.rstrip()
            rows.append(row)
        return rows
