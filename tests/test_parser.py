import textwrap
import unittest
from unittest.mock import Mock

from xcli._exception import XCliError
from xcli._parser import Arg
from xcli._parser import ArgumentParser as RealArgumentParser
from xcli._parser import Flag, Schema, Subcommand, UsageBuilder


# Patch the ArgumentParser class to set `interactive=False` by default.
class ArgumentParser(RealArgumentParser):
    def parse(self, *args, interactive=False, **kwargs):
        return super().parse(*args, interactive=interactive, **kwargs)

    def dispatch(self, *args, interactive=False, **kwargs):
        return super().dispatch(*args, interactive=interactive, **kwargs)


class ParserTests(unittest.TestCase):
    def test_positional_argument(self):
        parser = ArgumentParser([Arg("file")])
        self.assertEqual(parser.parse(["hosts.txt"]), {"file": "hosts.txt"})

    def test_flag(self):
        parser = ArgumentParser([Flag("--verbose")])
        self.assertEqual(parser.parse(["--verbose"]), {"--verbose": True})
        self.assertEqual(parser.parse([]), {"--verbose": False})

    def test_flag_with_arg(self):
        parser = ArgumentParser([Flag("--name", arg=True)])
        self.assertEqual(parser.parse(["--name", "john"]), {"--name": "john"})
        self.assertEqual(parser.parse(["--name=john"]), {"--name": "john"})

    def test_flag_with_arg_and_default(self):
        parser = ArgumentParser([Flag("--name", arg=True, default="susan")])
        self.assertEqual(parser.parse(["--name", "john"]), {"--name": "john"})
        self.assertEqual(parser.parse([]), {"--name": "susan"})

    def test_flag_with_short_and_long_names(self):
        parser = ArgumentParser([Flag("-v", "--verbose")])
        self.assertEqual(parser.parse(["-v"]), {"--verbose": True})
        self.assertEqual(parser.parse(["--verbose"]), {"--verbose": True})
        self.assertEqual(parser.parse([]), {"--verbose": False})

    def test_positional_arguments_and_flags(self):
        parser = ArgumentParser([Arg("infile"), Arg("outfile"), Flag("--dry-run")])
        self.assertEqual(
            parser.parse(["a.txt", "b.txt"]),
            {"infile": "a.txt", "outfile": "b.txt", "--dry-run": False},
        )
        self.assertEqual(
            parser.parse(["--dry-run", "a.txt", "b.txt"]),
            {"infile": "a.txt", "outfile": "b.txt", "--dry-run": True},
        )

    def test_optional_positional(self):
        parser = ArgumentParser([Arg("path"), Arg("name", default=None)])
        self.assertEqual(parser.parse(["a.txt", "b"]), {"path": "a.txt", "name": "b"})
        self.assertEqual(parser.parse(["a.txt"]), {"path": "a.txt", "name": None})

    def test_typed_positional(self):
        parser = ArgumentParser([Arg("age", type=int)])
        self.assertEqual(parser.parse(["10"]), {"age": 10})

    def test_typed_flag(self):
        parser = ArgumentParser([Flag("--age", arg=True, type=int)])
        self.assertEqual(parser.parse(["--age=10"]), {"--age": 10})

    def test_dash_separator(self):
        parser = ArgumentParser([Arg("a"), Arg("b"), Flag("-c")])
        self.assertEqual(
            parser.parse(["aaa", "--", "-b"]), {"a": "aaa", "b": "-b", "-c": False}
        )
        self.assertEqual(
            parser.parse(["aaa", "-c", "--", "-b"]), {"a": "aaa", "b": "-b", "-c": True}
        )

    def test_subcommands(self):
        parser = ArgumentParser(
            [
                Subcommand("new", [Arg("path")]),
                Subcommand("move", [Flag("--from", arg=True), Flag("--to", arg=True)]),
            ]
        )

        result = parser.parse(["new", "x.txt"])
        self.assertEqual(result, {"path": "x.txt"})
        self.assertEqual(result.subcommand, "new")

        result = parser.parse(["move", "--from", "x.txt", "--to", "y.txt"])
        self.assertEqual(result, {"--from": "x.txt", "--to": "y.txt"})
        self.assertEqual(result.subcommand, "move")

    def test_help_flag(self):
        result = ArgumentParser().parse(["--help"])
        self.assertEqual(result, {})
        self.assertTrue(result.help)

    def test_help_flag_with_subcommand(self):
        parser = ArgumentParser([Subcommand("new")])

        result = parser.parse(["--help"])
        self.assertEqual(result, {})
        self.assertTrue(result.help)
        self.assertEqual(result.subcommand, None)

        result = parser.parse(["--help", "new"])
        self.assertEqual(result, {})
        self.assertTrue(result.help)
        self.assertEqual(result.subcommand, None)

        result = parser.parse(["new", "--help"])
        self.assertEqual(result, {})
        self.assertTrue(result.help)
        self.assertEqual(result.subcommand, "new")

    def test_help_flag_manual_override(self):
        parser = ArgumentParser([Flag("--help")])
        result = parser.parse(["--help"])
        self.assertEqual(result, {"--help": True})
        self.assertFalse(result.help)


class ParserDispatchTests(unittest.TestCase):
    def test_simple_dispatch(self):
        mock_dispatch = Mock()
        parser = ArgumentParser([Arg("file"), Flag("--verbose")])
        parser.dispatch(["a.txt", "--verbose"], dispatch=mock_dispatch)
        mock_dispatch.assert_called_once_with("a.txt", verbose=True)

    def test_flag_with_dashes_in_middle(self):
        mock_dispatch = Mock()
        parser = ArgumentParser([Flag("--dry-run")])
        parser.dispatch([], dispatch=mock_dispatch)
        mock_dispatch.assert_called_once_with(dry_run=False)

    def test_with_subcommands(self):
        mock_edit_dispatch = Mock()
        mock_new_dispatch = Mock()

        parser = ArgumentParser(
            [
                Subcommand("edit", [Arg("path")], dispatch=mock_edit_dispatch),
                Subcommand("new", [Arg("path")], dispatch=mock_new_dispatch),
            ]
        )
        parser.dispatch(["edit", "a.txt"])
        mock_edit_dispatch.assert_called_once_with("a.txt")
        mock_new_dispatch.assert_not_called()

    def test_flag_with_invalid_name(self):
        mock_dispatch = Mock()
        parser = ArgumentParser([Flag("--a/b")])
        with self.assertRaisesRegex(
            XCliError, "^flag name is not a valid Python identifier: --a/b$"
        ):
            parser.dispatch(["--a/b"], dispatch=mock_dispatch)

    def test_flag_that_is_python_keyword(self):
        mock_dispatch = Mock()
        parser = ArgumentParser([Flag("--if", arg=True)])
        parser.dispatch(["--if=x"], dispatch=mock_dispatch)
        mock_dispatch.assert_called_once_with(if_="x")

    def test_missing_dispatch_function(self):
        with self.assertRaisesRegex(XCliError, "^no dispatch function$"):
            ArgumentParser().dispatch([])

    def test_missing_dispatch_function_with_subcommands(self):
        with self.assertRaisesRegex(
            XCliError, "^no dispatch function for subcommand: new$"
        ):
            ArgumentParser(
                [Subcommand("edit", dispatch=Mock()), Subcommand("new")]
            ).dispatch([])


class ParserConfigErrorTests(unittest.TestCase):
    def test_duplicate_args(self):
        with self.assertRaisesRegex(XCliError, "^duplicate argument name: file$"):
            ArgumentParser([Arg("file"), Arg("file")])

    def test_duplicate_flags(self):
        with self.assertRaisesRegex(XCliError, "^duplicate flag name: -v$"):
            ArgumentParser([Flag("-v"), Flag("-v")])

        with self.assertRaisesRegex(XCliError, "^duplicate flag name: --verbose$"):
            ArgumentParser([Flag("-v", "--verbose"), Flag("--verbose")])

    def test_invalid_flag_name(self):
        with self.assertRaisesRegex(XCliError, "^flag name must begin with dash: a"):
            ArgumentParser([Flag("a")])

        with self.assertRaisesRegex(
            XCliError, "^long flag name must begin with double dash: a"
        ):
            ArgumentParser([Flag("-a", "a")])

        with self.assertRaisesRegex(
            XCliError, "^short flag name must begin with single dash: --a"
        ):
            ArgumentParser([Flag("--a", "--a")])

    def test_invalid_argument_name(self):
        with self.assertRaisesRegex(
            XCliError, "^argument name must not begin with dash: -a"
        ):
            ArgumentParser([Arg("-a")])

    def test_subcommands_with_args(self):
        with self.assertRaisesRegex(
            XCliError, "^Arg and Subcommand objects cannot both be present$"
        ):
            ArgumentParser([Subcommand("new", [Arg("path")]), Arg("path")])

    def test_string_arg(self):
        with self.assertRaisesRegex(
            XCliError, "^expected Arg, Flag or Subcommand instance, got: 'file'$"
        ):
            ArgumentParser(["file"])

    def test_duplicate_subcommands(self):
        with self.assertRaisesRegex(XCliError, "^duplicate subcommand name: edit$"):
            ArgumentParser([Subcommand("edit"), Subcommand("edit")])

    def test_nested_subcommands(self):
        with self.assertRaisesRegex(XCliError, "^subcommands cannot be nested$"):
            ArgumentParser([Subcommand("edit", [Subcommand("new")])])

    def test_flag_with_type_but_not_arg(self):
        with self.assertRaisesRegex(
            XCliError, "^flag with `arg=False` cannot have `type`$"
        ):
            Flag("--verbose", type=int)

    def test_flag_with_default_but_not_arg(self):
        with self.assertRaisesRegex(
            XCliError, "^flag with `arg=False` cannot have default value$"
        ):
            Flag("--verbose", default=False)

    def test_required_argument_following_optional(self):
        with self.assertRaisesRegex(
            XCliError, "^required argument cannot follow optional one: file2$"
        ):
            ArgumentParser([Arg("file1", default=None), Arg("file2")])


class ParserErrorTests(unittest.TestCase):
    def test_missing_positional_argument(self):
        parser = ArgumentParser([Arg("file")])
        with self.assertRaisesRegex(XCliError, "^missing argument: file$"):
            parser.parse([])

    def test_extra_positional_argument(self):
        parser = ArgumentParser([Arg("file")])
        with self.assertRaisesRegex(XCliError, "^extra argument: extra.txt$"):
            parser.parse(["hosts.txt", "extra.txt"])

    def test_unknown_flag(self):
        parser = ArgumentParser()
        with self.assertRaisesRegex(XCliError, "^unknown flag: -v$"):
            parser.parse(["-v"])

    def test_flag_with_no_arg(self):
        parser = ArgumentParser([Flag("--name", arg=True)])
        with self.assertRaisesRegex(XCliError, "^expected argument to flag: --name$"):
            parser.parse(["--name"])

    def test_flag_with_unexpected_arg(self):
        parser = ArgumentParser([Flag("-v")])
        with self.assertRaisesRegex(XCliError, "^flag does not take argument: -v$"):
            parser.parse(["-v=yes"])

    def test_missing_flag_with_arg(self):
        parser = ArgumentParser([Flag("--name", arg=True)])
        with self.assertRaisesRegex(XCliError, "^missing flag: --name$"):
            parser.parse([])

    def test_help_flag_with_manual_override(self):
        parser = ArgumentParser(helpless=True)
        with self.assertRaisesRegex(XCliError, "^unknown flag: --help$"):
            parser.parse(["--help"])

    def test_wrongly_typed_positional(self):
        parser = ArgumentParser([Arg("age", type=int)])
        with self.assertRaisesRegex(XCliError, "^could not parse value for `age`: a$"):
            parser.parse(["a"])

    def test_wrongly_typed_flag(self):
        parser = ArgumentParser([Flag("--age", arg=True, type=int)])
        with self.assertRaisesRegex(
            XCliError, "^could not parse value for `--age`: a$"
        ):
            parser.parse(["--age", "a"])

    def test_missing_subcommand(self):
        parser = ArgumentParser([Subcommand("a"), Subcommand("b")])
        with self.assertRaisesRegex(XCliError, "^expected subcommand$"):
            parser.parse([])


# Helper function to write multi-line strings more readably.
s = lambda string: textwrap.dedent(string).strip("\n")  # noqa: E731


class UsageBuilderTests(unittest.TestCase):
    def test_no_args_or_flags(self):
        self.assertEqual(
            self.usage([]),
            s(
                """
                Usage: xyz

                This program accepts no flags or arguments.
                """
            ),
        )

    def test_one_arg(self):
        self.assertEqual(
            self.usage([Arg("path", help="Path to the file")]),
            s(
                """
                Usage: xyz <path>

                Arguments:
                  <path>    Path to the file
                """
            ),
        )

    def test_one_flag(self):
        self.assertEqual(
            self.usage([Flag("--verbose", help="Make it louder")]),
            s(
                """
                Usage: xyz

                Flags:
                  --verbose    Make it louder
                """
            ),
        )

    def test_with_description(self):
        self.assertEqual(
            self.usage([Arg("path")], description="Test description"),
            s(
                """
                xyz: Test description

                Usage: xyz <path>
                """
            ),
        )

    def test_with_required_flags(self):
        self.assertEqual(
            self.usage(
                [
                    Flag("--from", arg=True, help="path1"),
                    Flag("--to", arg=True, help="path2"),
                ]
            ),
            s(
                """
                Usage: xyz --from <arg> --to <arg>

                Arguments:
                  --from <arg>    path1
                  --to <arg>      path2
                """
            ),
        )

    def test_with_subcommands(self):
        self.assertEqual(
            self.usage(
                [
                    Subcommand("new", [Arg("path")], help="Create a new file"),
                    Subcommand("edit", [Arg("path")], help="Edit an existing file"),
                ]
            ),
            s(
                """
                Usage: xyz <subcommand>

                Subcommands:
                  edit <path>    Edit an existing file
                  new <path>     Create a new file

                Run `xyz subcommand --help` for detailed help.
                """
            ),
        )

    def usage(self, args, *, description=None):
        return UsageBuilder().build(
            Schema.from_args(args), name="xyz", description=description
        )
