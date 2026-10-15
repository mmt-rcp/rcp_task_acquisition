import os
import sqlite3
from pathlib import Path

from rcp_task_acquisition.models.participant import Participant, ParticipantIdType
from rcp_task_acquisition.utils.logger import get_logger

logger = get_logger(__name__)


class ParticipantDatabase:
    cursor: sqlite3.Cursor  # forcing as present for now.

    def __init__(self) -> None:
        self.connection: sqlite3.Connection | None = None
        self.cursor: sqlite3.Cursor = None  # type: ignore

    def connect(self, filepath: Path, filename):
        db_path = Path(filepath)
        db_path.mkdir(parents=True, exist_ok=True)
        file = os.path.join(db_path, filename)
        conn = self.connection = sqlite3.connect(file)
        self.cursor = conn.cursor()

        # if table doesn't exist, create it
        create_table = """
        CREATE TABLE IF NOT EXISTS Participants (
            ParticipantId VARCHAR(255) PRIMARY KEY,
            LastName VARCHAR(255),
            FirstName VARCHAR(255),
            Age VARCHAR(255),
            Diagnosis VARCHAR(255)
            );
        """
        self.cursor.execute(create_table)
        conn.commit()

    def get_participants_list(self) -> list[Participant]:
        select = "SELECT ParticipantId AS id, FirstName AS first_name, LastName AS last_name FROM Participants;"
        query = self.cursor.execute(select)
        col_names = [d[0] for d in query.description]
        participants = [
            Participant(**dict((col_names[i], r[i]) for i in range(len(col_names))))
            for r in query.fetchall()
        ]
        return participants

    def remove_participant(self, participant_id: ParticipantIdType) -> None:
        assert self.connection is not None
        remove = f"DELETE FROM Participants WHERE ParticipantId = ?;"
        self.cursor.execute(remove, (participant_id,))
        self.connection.commit()

    def add_participant(self, participant_id, first_name, last_name, age, diagnosis):
        assert self.connection is not None
        row_str = ""
        col_str = "ParticipantId"
        row_str += "'" + participant_id + "'"

        if first_name != "":
            row_str += ",'" + first_name + "'"
            col_str += ",FirstName"
        if last_name != "":
            row_str += ",'" + last_name + "'"
            col_str += ",LastName"
        if age != "":
            row_str += ",'" + age + "'"
            col_str += ",Age"
        if diagnosis != "":
            row_str += ",'" + diagnosis + "'"
            col_str += ",Diagnosis"

        insert = f"INSERT INTO Participants ({col_str}) VALUES ({row_str});"

        try:
            self.cursor.execute(insert)
            self.connection.commit()
            logger.info("sucessfully added row to DB")
            return True, participant_id
        except Exception as e:
            logger.info(f"error adding to db: {e}")
            return False, ""

    def close(self):
        self.cursor.close()
        if self.connection is not None:
            self.connection.close()
            self.connection = None
