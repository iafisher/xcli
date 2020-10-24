import random
import shutil
import string
import textwrap

from ._exception import XCliError


class Table:
    """
    Content-aligned textual tables.

        table = Table(alignment="lr")
        table.row("Revenue: ", revenue)
        table.row("Expenses: ", expenses)
        table.row("Profit: ", revenue - expenses)
        print(table)
    """

    def __init__(self, *, padding=0, alignment=None):
        self.columns = 0
        self.padding = padding
        self.alignment = alignment
        self.rows = []

    def row(self, *items):
        items = [str(item) for item in items]
        self.columns = max(self.columns, len(items))
        self.rows.append(items)

    def __str__(self):
        return self.as_string()

    def as_string(
        self,
        *,
        width=None,
        allow_empty=False,
        final_newline=False,
        trim_whitespace=True,
    ):
        if not self.rows:
            if allow_empty:
                return ""
            else:
                raise XCliError("table is empty")

        # Make sure all rows have the same number of columns.
        for row in self.rows:
            while len(row) < self.columns:
                row.append("")

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
            for i, (cell, width) in enumerate(zip(row, column_widths)):
                alignment = self.get_alignment(i)
                cells.append(self.format_cell(cell, width, alignment))

            height = max(map(len, cells))
            for cell, width in zip(cells, column_widths):
                while len(cell) < height:
                    cell.append(" " * width)

            builder.append(
                self.combine_cells(
                    cells, padding=self.padding, trim_whitespace=trim_whitespace
                )
            )

        if trim_whitespace:
            builder = [line.rstrip() for line in builder]

        result = "\n".join(builder)
        if not final_newline and result.endswith("\n"):
            result = result[:-1]
        return result

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

    def get_alignment(self, index):
        if not self.alignment or index >= len(self.alignment):
            return "l"
        else:
            return self.alignment[index]

    @staticmethod
    def format_cell(text, width, alignment):
        if len(text) <= width:
            return [align(text, width, alignment)]
        else:
            lines = textwrap.wrap(text, width)
            return [align(line, width, alignment) for line in lines]

    @staticmethod
    def combine_cells(cells, *, padding, trim_whitespace):
        lines = []
        for cell in cells:
            for i, line in enumerate(cell):
                if i == len(lines):
                    lines.append([])

                lines[i].append(line)

        spaces = " " * padding
        lines = [spaces.join(cells) for cells in lines]
        if trim_whitespace:
            lines = [line.rstrip() for line in lines]
        return "\n".join(lines)


def lorem_ipsum(words=100):
    return " ".join(
        "".join(
            random.choice(string.ascii_lowercase) for _ in range(random.randint(2, 10))
        )
        for _ in range(words)
    )


def align(text, width, alignment):
    alignment = alignment.lower()
    if alignment == "r":
        return text.rjust(width)
    elif alignment == "c":
        return text.center(width)
    elif alignment == "l":
        return text.ljust(width)
    else:
        raise XCliError(f"invalid alignment: {alignment}")
