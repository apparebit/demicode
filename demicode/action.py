from enum import Enum

class Action(Enum):
    ERROR = 665
    BACKWARD = -1
    TERMINATE = 0
    FORWARD = 1

    def flip(self) -> 'Action':
        if self is Action.FORWARD:
            return Action.BACKWARD
        elif self is Action.BACKWARD:
            return Action.FORWARD
        else:
            raise ValueError(f'unable to flip {self}')
