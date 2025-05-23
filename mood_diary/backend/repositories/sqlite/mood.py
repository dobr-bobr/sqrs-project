import sqlite3
import bleach
from datetime import datetime, date
from typing import Union
from uuid import UUID, uuid4

from mood_diary.backend.exceptions.mood import MoodStampAlreadyExistsErrorRepo
from mood_diary.backend.repositories.mood import MoodStampRepository
from mood_diary.backend.repositories.sсhemas.mood import (
    MoodStamp,
    CreateMoodStamp,
    UpdateMoodStamp,
    MoodStampFilter,
)


class SQLiteMoodRepository(MoodStampRepository):
    def __init__(self, connection):
        self.connection = connection
        self.connection.row_factory = sqlite3.Row

    def init_db(self):
        cursor = self.connection.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS moodstamps (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                date DATE NOT NULL,
                value INT NOT NULL,
                note TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
                UNIQUE (user_id, date)
            )
            """
        )
        self.create_indexes()
        self.connection.commit()

    def create_indexes(self):
        cursor = self.connection.cursor()

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_moodstamps_user_date
            ON moodstamps (user_id, date)
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_moodstamps_user
            ON moodstamps (user_id)
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_moodstamps_date
            ON moodstamps (date)
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_moodstamps_value
            ON moodstamps(value)
            """
        )

    async def get(self, user_id: UUID, date: date) -> MoodStamp | None:
        cursor = self.connection.cursor()
        cursor.execute(
            "SELECT * FROM moodstamps WHERE date = ? AND user_id = ?",
            (date, str(user_id)),
        )
        row = cursor.fetchone()
        if row:
            return MoodStamp(
                id=UUID(row["id"]),
                user_id=row["user_id"],
                date=row["date"],
                value=row["value"],
                note=bleach.clean(row["note"]),
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
        return None

    async def get_many(
        self, user_id: UUID, body: MoodStampFilter
    ) -> list[MoodStamp]:
        cursor = self.connection.cursor()
        query = "SELECT * FROM moodstamps WHERE user_id = ?"
        params: list[Union[str, date, int]] = [str(user_id)]

        if body.start_date is not None:
            query += " AND date >= ?"
            params.append(body.start_date)
        if body.end_date is not None:
            query += " AND date <= ?"
            params.append(body.end_date)
        if body.value is not None:
            query += " AND value = ?"
            params.append(body.value)

        query += " ORDER BY date DESC"

        cursor.execute(query, params)
        rows = cursor.fetchall()

        return [
            MoodStamp(
                id=UUID(row["id"]),
                user_id=row["user_id"],
                date=row["date"],
                value=row["value"],
                note=bleach.clean(row["note"]),
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in rows
        ]

    async def create(self, user_id: UUID, body: CreateMoodStamp) -> MoodStamp:
        """
        Create new moodstamp.
        Returns None if moodstamp with the same entry date already exists
        """

        cursor = self.connection.cursor()

        cursor.execute(
            "SELECT id FROM moodstamps WHERE user_id = ? AND date = ?",
            (str(user_id), body.date),
        )
        if cursor.fetchone():
            raise MoodStampAlreadyExistsErrorRepo()

        stamp_id = uuid4()
        created_at = updated_at = datetime.now()
        sanitized_note = bleach.clean(body.note)
        cursor.execute(
            """INSERT INTO moodstamps
            (id, user_id, date, value, note, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                str(stamp_id),
                str(user_id),
                body.date,
                body.value,
                sanitized_note,
                created_at,
                updated_at,
            ),
        )
        self.connection.commit()

        return MoodStamp(
            id=stamp_id,
            user_id=user_id,
            date=body.date,
            value=body.value,
            note=sanitized_note,
            created_at=created_at,
            updated_at=updated_at,
        )

    async def update(
        self, user_id: UUID, date: date, body: UpdateMoodStamp
    ) -> MoodStamp | None:
        """Update moodstamp by date. Returns None if moodstamp not found"""
        cursor = self.connection.cursor()

        cursor.execute(
            "SELECT * FROM moodstamps WHERE user_id = ? AND date = ?",
            (str(user_id), date),
        )
        row = cursor.fetchone()
        if not row:
            return None

        updated_at = datetime.now()
        sanitized_note = bleach.clean(
            body.note if body.note is not None else row["note"]
        )
        update_values = {
            "value": body.value if body.value is not None else row["value"],
            "note": sanitized_note,
            "updated_at": updated_at,
        }

        cursor.execute(
            """UPDATE moodstamps
            SET value = ?, note = ?, updated_at = ?
            WHERE user_id = ? AND date = ?""",
            (
                update_values["value"],
                update_values["note"],
                update_values["updated_at"],
                str(user_id),
                date,
            ),
        )
        self.connection.commit()

        return MoodStamp(
            id=UUID(row["id"]),
            user_id=user_id,
            date=date,
            value=update_values["value"],
            note=update_values["note"],
            created_at=row["created_at"],
            updated_at=updated_at,
        )

    async def delete(self, user_id: UUID, date: date) -> MoodStamp | None:
        """Delete moodstamp by date. Returns None if stamp not found"""
        cursor = self.connection.cursor()

        cursor.execute(
            "SELECT * FROM moodstamps WHERE user_id = ? AND date = ?",
            (str(user_id), date),
        )
        row = cursor.fetchone()
        if not row:
            return None

        cursor.execute(
            "DELETE FROM moodstamps WHERE user_id = ? AND date = ?",
            (str(user_id), date),
        )
        self.connection.commit()

        return MoodStamp(
            id=UUID(row["id"]),
            user_id=user_id,
            date=date,
            value=row["value"],
            note=bleach.clean(row["note"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
