"""create surveys and responses

Revision ID: 0001
Revises:
Create Date: 2026-10-12
"""

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE surveys (
            id          INTEGER      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            title       TEXT         NOT NULL CHECK (char_length(title) BETWEEN 1 AND 200),
            created_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE responses (
            id          BIGINT       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            survey_id   INTEGER      NOT NULL REFERENCES surveys (id),
            respondent  TEXT         NOT NULL CHECK (char_length(respondent) BETWEEN 1 AND 200),
            rating      SMALLINT     NOT NULL CHECK (rating BETWEEN 1 AND 5),
            comment     TEXT         CHECK (char_length(comment) <= 2000),
            created_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
        )
        """
    )
    # Serves GET /v1/responses?survey_id=N (filter on survey_id, ordered by id) and the foreign key:
    # rows come back already sorted, so no Sort step. See explain.py for the before/after plans.
    op.execute("CREATE INDEX idx_responses_survey_id_id ON responses (survey_id, id)")


def downgrade() -> None:
    op.execute("DROP TABLE responses")
    op.execute("DROP TABLE surveys")
