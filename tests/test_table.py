import textwrap
import unittest

from xcli import Table


class TableTests(unittest.TestCase):
    def test_small_table(self):
        t = Table(padding=1)
        t.row("Alabama", "Montgomery")
        t.row("Alaska", "Juneau")
        self.assertEqual(
            str(t),
            s(
                """
            Alabama Montgomery
            Alaska  Juneau
            """
            ),
        )

    def test_overflow(self):
        t = Table(padding=1)
        t.row("Sri Lanka", "Sri Jayawardenepura Kotte")
        t.row("Laos", "Vientiane")
        self.assertEqual(
            t.as_string(width=30),
            s(
                """
            Sri Lanka Sri Jayawardenepura
                      Kotte
            Laos      Vientiane
            """
            ),
        )

    def test_alignment(self):
        t = Table(padding=3, alignment="lr")
        t.row("Revenue:", 12500)
        t.row("Expenses:", 600)
        t.row("Profit:", 11900)
        self.assertEqual(
            str(t),
            s(
                """
            Revenue:    12500
            Expenses:     600
            Profit:     11900
            """
            ),
        )


# Helper function to let me write multi-line strings more readably.
s = lambda string: textwrap.dedent(string).strip("\n")  # noqa: E731
