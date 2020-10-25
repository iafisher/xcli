import textwrap
import unittest
from unittest.mock import MagicMock

from xcli import Arg, Flag, Parser, XCliError


class ParserTests(unittest.TestCase):
    def test_one_positional(self):
        args = Parser(args=["username"])._parse(["ian"])
        self.assertEqual(args, {"username": "ian"})

    def test_two_positionals(self):
        args = Parser(args=["username", "office"])._parse(["ian", "sfo"])
        self.assertEqual(args, {"username": "ian", "office": "sfo"})

    def test_too_many_positionals(self):
        with self.assertRaisesRegex(XCliError, "^extra argument: 23$"):
            Parser(args=["username"])._parse(["ian", "23"])

    def test_missing_positional(self):
        with self.assertRaisesRegex(XCliError, "^missing argument: username$"):
            Parser(args=["username"])._parse([])

    def test_positional_with_default(self):
        args = Parser(args=["username", Arg("office", default="sfo")])._parse(["ian"])
        self.assertEqual(args, {"username": "ian", "office": "sfo"})

    def test_positional_with_none_as_default(self):
        args = Parser(args=["username", Arg("office", default=None)])._parse(["ian"])
        self.assertEqual(args, {"username": "ian", "office": None})

    def test_cannot_have_positional_with_default_after_one_without(self):
        with self.assertRaisesRegex(
            XCliError, "^argument without default may not follow one with default$"
        ):
            Parser(args=[Arg("name", default="ian"), "age"])

    def test_positional_name_cannot_start_with_dash(self):
        with self.assertRaisesRegex(
            XCliError, "^positional name may not start with dash: -q$"
        ):
            Parser(args=["-q"])

    def test_typed_positional(self):
        args = Parser(args=[Arg("age", type=int)])._parse(["15"])
        self.assertEqual(args, {"age": 15})

    def test_wrongly_typed_positional(self):
        parser = Parser(args=[Arg("age", type=int)])
        with self.assertRaisesRegex(XCliError, "^could not parse typed argument: a$"):
            parser._parse(["a"])

    def test_flag(self):
        args = Parser(flags=["-q"])._parse(["-q"])
        self.assertEqual(args, {"-q": True})

    def test_missing_flag(self):
        args = Parser(flags=["-q"])._parse([])
        self.assertEqual(args, {"-q": False})

    def test_flag_with_long_name(self):
        parser = Parser(flags=[Flag("-q", "--quiet")])
        self.assertEqual(parser._parse(["-q"]), {"--quiet": True})
        self.assertEqual(parser._parse(["--quiet"]), {"--quiet": True})
        self.assertEqual(parser._parse([]), {"--quiet": False})

    def test_unknown_flag(self):
        parser = Parser(flags=["-q"])
        with self.assertRaisesRegex(XCliError, "^unknown flag: -r$"):
            parser._parse(["-r"])

    def test_cannot_have_two_flags_with_same_name(self):
        with self.assertRaisesRegex(XCliError, "^duplicate flag: -q$"):
            Parser(flags=["-q", "-q"])

    def test_flag_with_argument(self):
        parser = Parser(flags=[Flag("-p", arg=True)])
        self.assertEqual(parser._parse(["-p", "whatever"]), {"-p": "whatever"})

    def test_flag_with_argument_alternative_syntax(self):
        parser = Parser(flags=[Flag("-p", arg=True)])
        self.assertEqual(parser._parse(["-p=whatever"]), {"-p": "whatever"})

    def test_missing_flag_with_argument(self):
        parser = Parser(flags=[Flag("-p", arg=True)])
        self.assertEqual(parser._parse([]), {"-p": None})

    def test_required_flag(self):
        parser = Parser(flags=[Flag("-p", arg=True, required=True)])
        self.assertEqual(parser._parse(["-p", "whatever"]), {"-p": "whatever"})

    def test_required_flag_with_missing_value(self):
        parser = Parser(flags=[Flag("-p", arg=True, required=True)])
        with self.assertRaisesRegex(XCliError, "^missing required flag: -p$"):
            parser._parse([])

    def test_cannot_have_required_flag_without_argument(self):
        with self.assertRaisesRegex(
            XCliError, "^flag cannot be required without an arg: -p$"
        ):
            Parser(flags=[Flag("-p", required=True)])

    def test_flag_with_argument_with_default(self):
        parser = Parser(flags=[Flag("-p", arg=True, default="whatever")])
        self.assertEqual(parser._parse([]), {"-p": "whatever"})

    def test_subcommands(self):
        parser = Parser(subcommands={"list": Parser(), "new": Parser()})

        args = parser._parse(["list"])
        self.assertEqual(args, {})
        self.assertEqual(args.subcommand, "list")

        args = parser._parse(["new"])
        self.assertEqual(args, {})
        self.assertEqual(args.subcommand, "new")

    def test_cannot_have_nested_subcommands(self):
        with self.assertRaisesRegex(
            XCliError, "subcommand cannot have subcommands of its own"
        ):
            Parser(subcommands={"one": Parser(subcommands={"two": Parser()})})

    def test_missing_subcommand(self):
        parser = Parser(subcommands={"list": Parser(), "new": Parser()})
        with self.assertRaisesRegex(XCliError, "^missing subcommand$"):
            parser._parse([])

    def test_cannot_have_two_args_with_same_name(self):
        with self.assertRaisesRegex(XCliError, "^duplicate argument: username$"):
            Parser(args=["username", "username"])

    def test_cannot_have_subcommand_and_args(self):
        with self.assertRaisesRegex(
            XCliError, "^cannot have both arguments and subcommands$"
        ):
            Parser(args=["path"], subcommands={"list": Parser(), "new": Parser()})

    def test_help_flag(self):
        args = Parser()._parse(["--help"])
        self.assertTrue(args.help)

    def test_no_help_flag_with_helpless_setting(self):
        parser = Parser(helpless=True)
        with self.assertRaisesRegex(XCliError, "^unknown flag: --help$"):
            parser._parse(["--help"])

    def test_explicit_help_flag_with_helpless_setting(self):
        parser = Parser(flags=["--help"], helpless=True)
        self.assertEqual(parser._parse(["--help"]), {"--help": True})
        self.assertEqual(parser._parse([]), {"--help": False})

    def test_help_subcommand(self):
        args = Parser(subcommands={"test": Parser()})._parse(["help"])
        self.assertTrue(args.help)

    def test_help_subcommand_for_another_subcommand(self):
        args = Parser(subcommands={"test": Parser()})._parse(["help", "test"])
        self.assertEqual(args.help, "test")

    def test_dispatch(self):
        dispatch_edit = MagicMock()
        dispatch_new = MagicMock()

        parser = Parser(
            subcommands={
                "edit": Parser(args=["path"], dispatch=dispatch_edit),
                "new": Parser(
                    args=["title", "path"], flags=["--verbose"], dispatch=dispatch_new
                ),
            }
        )
        parser.dispatch(["new", "Lorem ipsum", "lol.txt"])

        dispatch_new.assert_called_with("Lorem ipsum", "lol.txt", verbose=False)
        dispatch_edit.assert_not_called()

    def test_dispatch_with_invalid_identifier_as_flag(self):
        parser = Parser(subcommands={"cmd": Parser(flags=["-0"], dispatch=MagicMock())})
        with self.assertRaisesRegex(
            XCliError, r"^flag name is not a valid Python identifier: 0$"
        ):
            parser.dispatch(["cmd"])

    def test_dispatch_with_python_keyword_as_flag(self):
        parser = Parser(
            subcommands={"cmd": Parser(flags=["--if"], dispatch=MagicMock())}
        )
        with self.assertRaisesRegex(XCliError, r"^flag name is a Python keyword: if$"):
            parser.dispatch(["cmd"])

    def test_dispatch_without_subcommands(self):
        parser = Parser()
        with self.assertRaisesRegex(XCliError, "^cannot dispatch without subcommands$"):
            parser.dispatch()

    def test_dispatch_with_undefined_dispatch_function(self):
        parser = Parser(subcommands={"cmd": Parser()})
        with self.assertRaisesRegex(
            XCliError, "^no dispatch function defined for subcommand: cmd$"
        ):
            parser.dispatch(["cmd"])


# Helper function to let me write multi-line strings more readably.
s = lambda string: textwrap.dedent(string).lstrip("\n")  # noqa: E731


class UsageTests(unittest.TestCase):
    def test_one_positional(self):
        parser = Parser(program="itest", args=["firstname"])
        self.assertEqual(
            parser.usage(),
            s(
                """
                Usage: itest <firstname>

                Positional arguments:
                  firstname"""
            ),
        )

    def test_positional_and_flag(self):
        parser = Parser(program="itest", args=["firstname"], flags=["--verbose"])
        self.assertEqual(
            parser.usage(),
            s(
                """
                Usage: itest <firstname>

                Positional arguments:
                  firstname

                Flags:
                  --verbose"""
            ),
        )

    def test_positional_and_required_flag_with_arg(self):
        parser = Parser(
            program="itest",
            args=["firstname"],
            flags=[Flag("--verbose", arg=True, required=True)],
        )
        self.assertEqual(
            parser.usage(),
            s(
                """
                Usage: itest --verbose=<arg> <firstname>

                Positional arguments:
                  firstname

                Flags:
                  --verbose <arg>"""
            ),
        )

    def test_flag_with_long_name(self):
        parser = Parser(program="itest", flags=[Flag("-v", "--verbose")])
        self.assertEqual(
            parser.usage(),
            s(
                """
                Usage: itest

                Flags:
                  -v, --verbose"""
            ),
        )

    def test_flag_with_help_text(self):
        parser = Parser(program="itest", flags=[Flag("-v", help="Set verbosity.")])
        self.assertEqual(
            parser.usage(),
            s(
                """
                Usage: itest

                Flags:
                  -v    Set verbosity."""
            ),
        )

    def test_subcommand(self):
        parser = Parser(
            program="itest",
            subcommands={"edit": Parser(args=["file"]), "new": Parser(args=["file"])},
        )
        self.assertEqual(
            parser.usage(),
            s(
                """
                Usage: itest <subcommand>

                Subcommands:
                  edit <file>
                  new <file>

                Run `itest help <subcommand>` for detailed help."""
            ),
        )


class RealParserTests(unittest.TestCase):
    def test_medium_parser(self):
        p = Parser(
            subcommands={
                "edit": Parser(args=["file"]),
                "new": Parser(args=["file"]),
                "list": Parser(flags=["--sorted"]),
            },
            flags=["--verbose"],
        )

        args = p.parse(["edit", "a.txt"])
        self.assertEqual(args, {"file": "a.txt", "--verbose": False})
        self.assertEqual(args.subcommand, "edit")

        args = p.parse(["new", "a.txt"])
        self.assertEqual(args, {"file": "a.txt", "--verbose": False})
        self.assertEqual(args.subcommand, "new")

        args = p.parse(["list"])
        self.assertEqual(args, {"--sorted": False, "--verbose": False})
        self.assertEqual(args.subcommand, "list")

    def test_hera_parser(self):
        # Based on https://github.com/iafisher/hera-py/blob/master/hera/main.py
        p = Parser(
            subcommands={
                "debug": Parser(args=["path"], flags=[Flag("--throttle", arg=True)]),
                "assemble": Parser(args=["path"], flags=["--code", "--data"]),
                "preprocess": Parser(args=["path"]),
                "disassemble": Parser(args=["path"]),
                "run": Parser(args=["path"]),
            },
            flags=[Flag("-v", "--version"), "--credits", "--no-color"],
            default_subcommand="run",
        )

        args = p.parse(["a.txt"])
        self.assertEqual(
            args,
            {
                "path": "a.txt",
                "--credits": False,
                "--no-color": False,
                "--version": False,
            },
        )

        args = p.parse(["--no-color", "debug", "a.txt", "--throttle=10"])
        self.assertEqual(
            args,
            {
                "path": "a.txt",
                "--throttle": "10",
                "--credits": False,
                "--no-color": True,
                "--version": False,
            },
        )
        self.assertEqual(args.subcommand, "debug")
