import io
import unittest

from xcli._autocomplete import Autocomplete, sequence_to_autocomplete

BACKSPACE = "\x7f"
UP = "\x1b\x5b\x41"
DOWN = "\x1b\x5b\x42"
RIGHT = "\x1b\x5b\x43"
LEFT = "\x1b\x5b\x44"
HOME = "\x1b\x5b\x48"
END = "\x1b\x5b\x46"
ENTER = "\n"


class AutocompleteTests(unittest.TestCase):
    def setUp(self):
        options = ["albania", "brazil", "chad", "namibia", "nauru", "zambia"]
        self.completer = sequence_to_autocomplete(options)
        self.fake_stdout = io.StringIO()
        self.fake_stdout.fileno = lambda: None

    def test_simple_input(self):
        fake_stdin = io.StringIO("abc" + ENTER)
        with Autocomplete(self.fake_stdout, fake_stdin, self.completer) as ac:
            response = ac.input("? ")

        self.assertEqual(response, "abc")

    def test_selection(self):
        fake_stdin = io.StringIO("alb" + DOWN + ENTER)
        with Autocomplete(self.fake_stdout, fake_stdin, self.completer) as ac:
            response = ac.input("? ")

        self.assertEqual(response, "albania")

    def test_select_from_multiple_options(self):
        fake_stdin = io.StringIO("na" + DOWN + DOWN + ENTER)
        with Autocomplete(self.fake_stdout, fake_stdin, self.completer) as ac:
            response = ac.input("? ")

        self.assertEqual(response, "nauru")

    def test_down_key_with_no_selection(self):
        fake_stdin = io.StringIO("leb" + DOWN + ENTER)
        with Autocomplete(self.fake_stdout, fake_stdin, self.completer) as ac:
            response = ac.input("? ")

        self.assertEqual(response, "leb")

    def test_force_selection_with_no_input(self):
        fake_stdin = io.StringIO(DOWN + DOWN + DOWN + ENTER)
        with Autocomplete(self.fake_stdout, fake_stdin, self.completer) as ac:
            response = ac.input("? ")

        self.assertEqual(response, "brazil")

    def test_backspace(self):
        fake_stdin = io.StringIO("a" + BACKSPACE + "b" + ENTER)
        with Autocomplete(self.fake_stdout, fake_stdin, self.completer) as ac:
            response = ac.input("? ")

        self.assertEqual(response, "b")

    def test_backspace_with_selection(self):
        fake_stdin = io.StringIO("za" + DOWN + BACKSPACE + ENTER)
        with Autocomplete(self.fake_stdout, fake_stdin, self.completer) as ac:
            response = ac.input("? ")

        self.assertEqual(response, "zambi")

    def test_press_key_with_selection(self):
        fake_stdin = io.StringIO("za" + DOWN + "s" + ENTER)
        with Autocomplete(self.fake_stdout, fake_stdin, self.completer) as ac:
            response = ac.input("? ")

        self.assertEqual(response, "zambias")

    def test_select_then_unselect(self):
        fake_stdin = io.StringIO("na" + DOWN + DOWN + UP + UP + ENTER)
        with Autocomplete(self.fake_stdout, fake_stdin, self.completer) as ac:
            response = ac.input("? ")

        self.assertEqual(response, "na")

    def test_press_up_without_selection(self):
        fake_stdin = io.StringIO("na" + UP + UP + ENTER)
        with Autocomplete(self.fake_stdout, fake_stdin, self.completer) as ac:
            response = ac.input("? ")

        self.assertEqual(response, "na")

    def test_home_key(self):
        fake_stdin = io.StringIO("lb" + HOME + "a" + DOWN + ENTER)
        with Autocomplete(self.fake_stdout, fake_stdin, self.completer) as ac:
            response = ac.input("? ")

        self.assertEqual(response, "albania")

    def test_end_key(self):
        fake_stdin = io.StringIO("lb" + HOME + "a" + END + "an" + ENTER)
        with Autocomplete(self.fake_stdout, fake_stdin, self.completer) as ac:
            response = ac.input("? ")

        self.assertEqual(response, "alban")

    def test_left_and_right_keys(self):
        fake_stdin = io.StringIO("la" + LEFT + "b" + RIGHT + RIGHT + "n" + ENTER)
        with Autocomplete(self.fake_stdout, fake_stdin, self.completer) as ac:
            response = ac.input("? ")

        self.assertEqual(response, "lban")

    def test_handle_backspace_in_middle_of_word(self):
        fake_stdin = io.StringIO("lorim" + LEFT + BACKSPACE + "e" + ENTER)
        with Autocomplete(self.fake_stdout, fake_stdin, self.completer) as ac:
            response = ac.input("? ")

        self.assertEqual(response, "lorem")
