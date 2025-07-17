# models.py

from pydantic import BaseModel, Field

class SQLQueryRequest(BaseModel):
    """
    Defines the input parameters for the SQL query tool.
    """
    db_uri: str = Field(
        ...,
        description="The full PostgreSQL connection URI.",
        examples=["postgresql+psycopg2://user:password@host:port/dbname"]
    )
    question: str = Field(
        ...,
        description="The natural language question to ask the database."
    )