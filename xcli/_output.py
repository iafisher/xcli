import enum
import random
import shutil
import string
import textwrap

from ._exception import XCliError


class Alignment(enum.Enum):
    LEFT = enum.auto()
    RIGHT = enum.auto()
    CENTER = enum.auto()


class Table:
    """
    Content-aligned textual tables.

        table = Table(columns=2, alignment=[Alignment.LEFT, Alignment.RIGHT])
        table.add_row("Revenue: ", revenue)
        table.add_row("Expenses: ", expenses)
        table.add_row("Profit: ", revenue - expenses)
        print(table)
    """

    def __init__(self, *, columns, padding=0, alignment=None):
        self.columns = columns
        self.padding = padding
        self.rows = []

        if alignment is None:
            self.alignment = [Alignment.LEFT] * self.columns
        elif isinstance(alignment, Alignment):
            self.alignment = [alignment] * self.columns
        else:
            if len(alignment) != self.columns:
                raise XCliError("length of alignment does not equal number of columns")

            self.alignment = alignment

    def add_row(self, *items):
        items = [str(item) for item in items]
        if len(items) > self.columns:
            raise XCliError(
                f"can't fit {len(items)} item(s) in {self.columns} column(s)"
            )

        if len(items) < self.columns:
            items.extend([""] * (self.columns - len(items)))

        self.rows.append(items)

    def __str__(self):
        return self.as_string()

    def as_string(self, *, width=None, allow_empty=False):
        if not self.rows:
            if allow_empty:
                return ""
            else:
                raise XCliError("table is empty")

        if width is None:
            width = shutil.get_terminal_size().columns

        column_widths = []
        for i in range(self.columns):
            column_widths.append(max(len(row[i]) for row in self.rows))

        actual_width = sum(column_widths) + (self.padding * (self.columns - 1))
        if actual_width > width:
            column_widths = self.distribute_width(column_widths, width)

        builder = []
        for row in self.rows:
            cells = []
            for cell, width, alignment in zip(row, column_widths, self.alignment):
                cells.append(self.format_cell(cell, width, alignment))

            height = max(map(len, cells))
            for cell, width in zip(cells, column_widths):
                while len(cell) < height:
                    cell.append(" " * width)

            builder.append(self.combine_cells(cells, padding=self.padding))

        return "\n".join(builder)

    def distribute_width(self, column_widths, width):
        # Identify "problematic" columns that are wider than the even width, and keep
        # track of an allowance of extra width from columns that are narrower than the
        # even width.
        column_widths = column_widths.copy()
        even = width // self.columns
        problematic = []
        allowance = 0
        for i, column_width in enumerate(column_widths):
            if column_width < even:
                allowance += even - column_width
            elif column_width > even:
                problematic.append(i)

        # Distribute the extra width from narrow columns evenly among the problematic
        # columns.
        allowance += len(problematic) * even
        allowance_split = allowance // len(problematic)
        for index in problematic:
            column_widths[index] = allowance_split

        return column_widths

    @staticmethod
    def format_cell(text, width, alignment):
        if len(text) <= width:
            return [align(text, width, alignment)]
        else:
            lines = textwrap.wrap(text, width)
            return [align(line, width, alignment) for line in lines]

    @staticmethod
    def combine_cells(cells, *, padding):
        lines = []
        for cell in cells:
            for i, line in enumerate(cell):
                if i == len(lines):
                    lines.append([])

                lines[i].append(line)

        spaces = " " * padding
        return "\n".join(spaces.join(cells) for cells in lines)


def lorem_ipsum(words=100):
    return " ".join(
        "".join(
            random.choice(string.ascii_lowercase) for _ in range(random.randint(2, 10))
        )
        for _ in range(words)
    )


def align(text, width, alignment):
    if alignment == Alignment.RIGHT:
        return text.rjust(width)
    elif alignment == Alignment.CENTER:
        return text.center(width)
    else:
        return text.ljust(width)
