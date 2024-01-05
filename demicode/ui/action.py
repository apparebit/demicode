from enum import Enum


class Action(Enum):
    """A pager action: Go Forward or Backward; Done; or User Error."""

    ERROR = 665
    BACKWARD = -1
    TERMINATE = 0
    FORWARD = 1

    def flip(self) -> "Action":
        if self is Action.FORWARD:
            return Action.BACKWARD
        elif self is Action.BACKWARD:
            return Action.FORWARD
        else:
            raise ValueError(f"unable to flip {self}")
