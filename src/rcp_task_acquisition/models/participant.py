import dataclasses
import typing


ParticipantIdType: typing.TypeAlias = str


@dataclasses.dataclass
class Participant:
    id: ParticipantIdType
    first_name: str
    last_name: str
