import textwrap
import unittest

from xcli import Parser, XCliError


class ParserTests(unittest.TestCase):
    def test_one_positional(self):
        args = Parser().arg("name")._parse(["ian"])
        self.assertEqual(args, {"name": "ian"})

    def test_two_positionals(self):
        args = Parser().arg("name").arg("office")._parse(["ian", "sfo"])
        self.assertEqual(args, {"name": "ian", "office": "sfo"})

    def test_too_many_positionals(self):
        with self.assertRaises(XCliError):
            Parser().arg("name")._parse(["ian", "23"])

    def test_missing_positional(self):
        with self.assertRaises(XCliError):
            Parser().arg("name")._parse([])

    def test_positional_with_default(self):
        args = Parser().arg("name").arg("office", default="sfo")._parse(["ian"])
        self.assertEqual(args, {"name": "ian", "office": "sfo"})

    def test_cannot_have_positional_with_default_after_one_without(self):
        parser = Parser().arg("name", default="ian")
        with self.assertRaises(XCliError):
            parser.arg("age")

    def test_positional_name_cannot_start_with_dash(self):
        with self.assertRaises(XCliError):
            Parser().arg("-q")

    def test_typed_positional(self):
        args = Parser().arg("age", type=int)._parse(["15"])
        self.assertEqual(args, {"age": 15})

    def test_wrongly_typed_positional(self):
        parser = Parser().arg("age", type=int)
        with self.assertRaises(XCliError):
            parser._parse(["a"])

    def test_flag(self):
        args = Parser().flag("-q")._parse(["-q"])
        self.assertEqual(args, {"-q": True})

    def test_missing_flag(self):
        args = Parser().flag("-q")._parse([])
        self.assertEqual(args, {"-q": False})

    def test_flag_with_long_name(self):
        parser = Parser().flag("-q", "--quiet")
        self.assertEqual(parser._parse(["-q"]), {"--quiet": True})
        self.assertEqual(parser._parse(["--quiet"]), {"--quiet": True})
        self.assertEqual(parser._parse([]), {"--quiet": False})

    def test_unknown_flag(self):
        parser = Parser().flag("-q")
        with self.assertRaises(XCliError):
            parser._parse(["-r"])

    def test_cannot_have_two_flags_with_same_name(self):
        parser = Parser().flag("-q")
        with self.assertRaises(XCliError):
            parser.flag("-q")

    def test_flag_with_argument(self):
        parser = Parser().flag("-p", arg=True)
        self.assertEqual(parser._parse(["-p", "whatever"]), {"-p": "whatever"})

    def test_flag_with_argument_alternative_syntax(self):
        parser = Parser().flag("-p", arg=True)
        self.assertEqual(parser._parse(["-p=whatever"]), {"-p": "whatever"})

    def test_missing_flag_with_argument(self):
        parser = Parser().flag("-p", arg=True)
        self.assertEqual(parser._parse([]), {"-p": None})

    def test_required_flag(self):
        parser = Parser().flag("-p", arg=True, required=True)
        self.assertEqual(parser._parse(["-p", "whatever"]), {"-p": "whatever"})

    def test_required_flag_with_missing_value(self):
        parser = Parser().flag("-p", arg=True, required=True)
        with self.assertRaises(XCliError):
            parser._parse([])

    def test_cannot_have_required_flag_without_argument(self):
        with self.assertRaises(XCliError):
            Parser().flag("-p", required=True)

    def test_flag_with_argument_with_default(self):
        parser = Parser().flag("-p", arg=True, default="whatever")
        self.assertEqual(parser._parse([]), {"-p": "whatever"})

    def test_subcommands(self):
        parser = Parser()
        parser.subcommand("list")
        parser.subcommand("new")

        args = parser._parse(["list"])
        self.assertEqual(args, {"list": {}})
        self.assertEqual(args.subcommand, "list")

        args = parser._parse(["new"])
        self.assertEqual(args, {"new": {}})
        self.assertEqual(args.subcommand, "new")

    def test_cannot_have_two_args_with_same_name(self):
        parser = Parser().arg("name")
        with self.assertRaises(XCliError):
            parser.arg("name")

    def test_cannot_have_subcommand_and_argument_with_same_name(self):
        parser = Parser().arg("whatever")
        with self.assertRaises(XCliError):
            parser.subcommand("whatever")

        parser = Parser()
        parser.subcommand("whatever")
        with self.assertRaises(XCliError):
            parser.arg("whatever")

    def test_help_flag(self):
        self.assertEqual(Parser()._parse(["--help"]), {"--help": True})

    def test_no_help_flag_with_helpless_setting(self):
        parser = Parser(helpless=True)
        with self.assertRaises(XCliError):
            parser._parse(["--help"])

    def test_explicit_help_flag_with_helpless_setting(self):
        parser = Parser(helpless=True).flag("--help")
        self.assertEqual(parser._parse(["--help"]), {"--help": True})
        self.assertEqual(parser._parse([]), {"--help": False})


# Helper function to let me write multi-line strings more readably.
s = lambda string: textwrap.dedent(string).lstrip("\n")  # noqa: E731


class UsageTests(unittest.TestCase):
    def test_one_positional(self):
        parser = Parser(program="itest").arg("firstname")
        self.assertEqual(
            parser.usage(),
            s(
                """
                Usage: itest firstname

                Positional arguments:
                  firstname
                """
            ),
        )

    def test_positional_and_flag(self):
        parser = Parser(program="itest").arg("firstname").flag("--verbose")
        self.assertEqual(
            parser.usage(),
            s(
                """
                Usage: itest firstname

                Positional arguments:
                  firstname

                Flags:
                  --verbose
                """
            ),
        )

    def test_flag_with_long_name(self):
        parser = Parser(program="itest").flag("-v", "--verbose")
        self.assertEqual(
            parser.usage(),
            s(
                """
                Usage: itest

                Flags:
                  -v, --verbose
                """
            ),
        )

    # TODO: Tests for subcommands.


class RealParserTests(unittest.TestCase):
    def test_medium_parser(self):
        p = Parser()
        p.flag("--verbose")
        p.subcommand("edit").arg("file")
        p.subcommand("new").arg("file")
        p.subcommand("list").flag("--sorted")

        args = p.parse(["edit", "a.txt"])
        self.assertEqual(args, {"edit": {"file": "a.txt"}, "--verbose": False})
        self.assertEqual(args.subcommand, "edit")

        args = p.parse(["new", "a.txt"])
        self.assertEqual(args, {"new": {"file": "a.txt"}, "--verbose": False})
        self.assertEqual(args.subcommand, "new")

        args = p.parse(["list"])
        self.assertEqual(args, {"list": {"--sorted": False}, "--verbose": False})
        self.assertEqual(args.subcommand, "list")

    def test_hera_parser(self):
        # Based on https://github.com/iafisher/hera-py/blob/master/hera/main.py
        p = Parser(optional_subcommands=True)
        p.arg("path", default="")
        p.flag("-v", "--version")
        p.flag("--credits")
        p.flag("--no-color")
        p.subcommand("debug").arg("path").flag("--throttle", arg=True)
        p.subcommand("assemble").arg("path").flag("--code").flag("--data")
        p.subcommand("preprocess").arg("path")
        p.subcommand("disassemble").arg("path")

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
                "debug": {"path": "a.txt", "--throttle": "10"},
                "path": "",
                "--credits": False,
                "--no-color": True,
                "--version": False,
            },
        )
        self.assertEqual(args.subcommand, "debug")
