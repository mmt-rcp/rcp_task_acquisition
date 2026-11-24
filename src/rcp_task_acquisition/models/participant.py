import dataclasses
import typing


ParticipantIdType: typing.TypeAlias = str


@dataclasses.dataclass
class Participant:
    id: ParticipantIdType = ""
    first_name: str = ""
    last_name: str = ""

    def __repr__(self) -> str:
        return f"Participant(id={self.id!r})"


no_participant = Participant(id="no_participant")
