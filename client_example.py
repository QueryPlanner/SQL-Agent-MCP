# client_example.py (Corrected)

import asyncio
from fastmcp import Client
# No longer need to import SQLQueryRequest or models

# --- IMPORTANT ---
# Replace this with the actual connection URI for your PostgreSQL database (like your Neon DB URI)
# Format: postgresql://user:password@host:port/dbname
DB_CONNECTION_URI = "postgresql://legodb_owner:npg_niqN6m9SIjtA@ep-lucky-sun-a8d6gska-pooler.eastus2.azure.neon.tech/legodb?sslmode=require&channel_binding=require"
# The question to ask the agent
USER_QUESTION = "Find total number of unique valid names avaialble in colors table"

async def main():
    mcp_server_url = "http://127.0.0.1:8000/mcp/"
    
    # --- FIX IS HERE: Create a simple dictionary for the payload ---
    request_payload = {
        "db_uri": DB_CONNECTION_URI,
        "question": USER_QUESTION
    }
    # --- END FIX ---

    print(f"Connecting to MCP server at {mcp_server_url}...")
    
    try:
        async with Client(mcp_server_url) as client:
            print("Listing available tools...")
            tools = await client.list_tools()
            print(f"Found tools: {[tool.name for tool in tools]}")
            
            print(f"\nCalling tool 'query_postgres_database' with question: '{USER_QUESTION}'")
            
            # Pass the simple dictionary directly
            result = await client.call_tool(
                "query_postgres_database",
                request_payload 
            )
            
            print("\n✅ Agent's Final Answer:")
            print("-------------------------")
            print(result)
            print("-------------------------")

    except Exception as e:
        print(f"\n❌ An error occurred:")
        print(e)

if __name__ == "__main__":
    asyncio.run(main())