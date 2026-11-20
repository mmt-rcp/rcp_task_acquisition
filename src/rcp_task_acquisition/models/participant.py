import dataclasses
import typing


ParticipantIdType: typing.TypeAlias = str


@dataclasses.dataclass
class Participant:
    id: ParticipantIdType = ""
    first_name: str = ""
    last_name: str = ""

    def __repr__(self) -> str:
        return f"Participant({self.id}, {self.first_name}, {self.last_name})"


no_participant = Participant(id="no_participant")
