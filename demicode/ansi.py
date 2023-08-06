class Ansi:
    CSI = '\x1b['
    ERROR: str
    WARNING: str
    RESET: str

    class BG:
        LIGHTER_GREY: str
        LIGHT_GREY: str
        MEDIUM_GREY: str
        PINK: str
        YELLOW: str
        DEFAULT: str

    class FG:
        DARK_GREY: str
        ORANGE: str
        PURPLE: str
        RED: str
        DEFAULT: str

    class Style:
        BOLD: str

    @staticmethod
    def SGR(code: int | str) -> str:
        return f'{Ansi.CSI}{code}m'

    @staticmethod
    def CHA(column: int) -> str:
        return f'{Ansi.CSI}{column}G'

Ansi.BG.LIGHTER_GREY = Ansi.SGR('48;5;254')
Ansi.BG.LIGHT_GREY = Ansi.SGR('48;5;250')
Ansi.BG.MEDIUM_GREY = Ansi.SGR('48;5;252')
Ansi.BG.PINK = Ansi.SGR('48;5;204')
Ansi.BG.YELLOW = Ansi.SGR('48;5;220')
Ansi.BG.DEFAULT = Ansi.SGR('49')

Ansi.FG.DARK_GREY = Ansi.SGR('38;5;243')
Ansi.FG.ORANGE = Ansi.SGR('38;5;202')
Ansi.FG.PURPLE = Ansi.SGR('38;5;53')
Ansi.FG.RED = Ansi.SGR('38;5;88')
Ansi.FG.DEFAULT = Ansi.SGR('39')

Ansi.Style.BOLD = Ansi.SGR('1')

Ansi.ERROR = Ansi.SGR('1;38;5;160')
Ansi.WARNING = Ansi.SGR('1;38;5;202')
Ansi.RESET = Ansi.SGR('0')
