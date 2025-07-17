# main.py (Corrected)

import os
import asyncio
from dotenv import load_dotenv

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from langchain_core.messages import AIMessage

from agent import create_sql_agent

load_dotenv()

mcp = FastMCP(
    name="DynamicSQLAgentServer",
    instructions="A server that can answer questions about a PostgreSQL database provided by the user."
)

@mcp.tool(
    name="query_postgres_database",
    description="Connects to a user-provided PostgreSQL database to answer a natural language question."
)
async def query_database(db_uri: str, question: str) -> str:
    """
    The main tool exposed by the MCP server.
    """
    if not os.getenv("GOOGLE_API_KEY"):
        raise ToolError("Server-side configuration error: GOOGLE_API_KEY is not set.")

    print(f"Received request for database: {db_uri.split('@')[-1]}")
    print(f"Question: {question}")
    
    try:
        agent_runnable = create_sql_agent(db_uri)
        initial_state = {"messages": [("user", question)]}
        final_answer = None

        # --- THE DEFINITIVE FIX ---
        # The 'step' object is a dict with the node name as the key. We need to get the value.
        async for step in agent_runnable.astream(initial_state, config={"stream_mode": "values"}):
            # Print the step to see its structure - an invaluable debugging tool
            print(f"--- Agent Step ---\n{step}\n------------------")

            # Get the value from the step dictionary, which is the actual state
            if not step:
                continue
            
            # The step dictionary has one key: the name of the node that just ran
            node_name = list(step.keys())[0]
            current_state = step[node_name]

            # Now, safely access the messages from the state dictionary
            if "messages" in current_state and current_state["messages"]:
                last_message = current_state["messages"][-1]
                if isinstance(last_message, AIMessage) and not last_message.tool_calls:
                    final_answer = last_message.content
                    print(f"✅ Agent produced a potential final answer: {final_answer}")
        # --- END FIX ---

        if final_answer:
            print("Agent finished. Returning final answer.")
            return final_answer
        else:
            raise ToolError("The agent completed its work but did not produce a final answer.")

    except ImportError as e:
        if "psycopg2" in str(e):
             raise ToolError("Database driver error. Ensure 'psycopg2-binary' is installed.")
        raise ToolError(f"An unexpected import error occurred: {e}")
    except Exception as e:
        print(f"An error occurred during agent execution: {e}")
        # Include the traceback in the server log for easier debugging
        import traceback
        traceback.print_exc()
        raise ToolError(f"Failed to query the database. Reason: {e}")

if __name__ == "__main__":
    mcp.run(transport="http", host="127.0.0.1", port=8001)