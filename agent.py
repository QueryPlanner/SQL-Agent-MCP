# agent.py

from typing import Literal

from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain_community.utilities import SQLDatabase
from langchain_core.messages import AIMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode

def create_sql_agent(db_uri: str):
    """
    Factory function to create and compile a LangGraph SQL agent on-the-fly.

    Args:
        db_uri (str): The PostgreSQL database connection URI.

    Returns:
        A compiled LangGraph runnable.
    """
    # 1. Initialize the LLM
    # We use Google's Gemini model. `convert_system_message_to_human` is
    # needed for some system prompts to work correctly with the Gemini API.
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", convert_system_message_to_human=True)

    # 2. Configure the database connection
    # SQLDatabase uses SQLAlchemy to connect to any supported database
    db = SQLDatabase.from_uri(db_uri)

    # 3. Create the SQL toolkit
    toolkit = SQLDatabaseToolkit(db=db, llm=llm)
    tools = toolkit.get_tools()

    # Isolate specific tools for our graph nodes
    get_schema_tool = next(t for t in tools if t.name == "sql_db_schema")
    run_query_tool = next(t for t in tools if t.name == "sql_db_query")

    # 4. Define Graph Nodes
    list_tables_tool = next(t for t in tools if t.name == "sql_db_list_tables")
    get_schema_node = ToolNode([get_schema_tool], name="get_schema")
    run_query_node = ToolNode([run_query_tool], name="run_query")

    def list_tables(state: MessagesState):
        """A predetermined node to always list tables first."""
        tool_call = AIMessage(
            content="",
            tool_calls=[{"name": "sql_db_list_tables", "args": {}, "id": "list_tables"}]
        )
        tool_message = list_tables_tool.invoke(tool_call.tool_calls[0])
        response = AIMessage(f"The following tables are available: {tool_message.content}")
        return {"messages": [tool_call, tool_message, response]}

    def call_get_schema(state: MessagesState):
        """Forces the model to get the schema of relevant tables."""
        llm_with_tools = llm.bind_tools([get_schema_tool], tool_choice="any")
        response = llm_with_tools.invoke(state["messages"])
        return {"messages": [response]}

    generate_query_system_prompt = f"""
    You are a PostgreSQL expert agent. Given a question, create a syntactically correct
    PostgreSQL query. Always limit results to 5 unless specified otherwise.
    Only query for relevant columns.

    DO NOT make any DML statements (INSERT, UPDATE, DELETE, DROP).
    You MUST double check your query before executing it.
    """

    def generate_query(state: MessagesState):
        system_message = {"role": "system", "content": generate_query_system_prompt}
        llm_with_tools = llm.bind_tools([run_query_tool])
        response = llm_with_tools.invoke([system_message] + state["messages"])
        return {"messages": [response]}
    
    check_query_system_prompt = f"""
    You are a PostgreSQL expert. Double-check the query for common mistakes.
    If there are no mistakes, reproduce the original query. Otherwise, correct it.
    You will call the tool to execute the query after this check.
    """
    
    def check_query(state: MessagesState):
        system_message = {"role": "system", "content": check_query_system_prompt}
        tool_call = state["messages"][-1].tool_calls[0]
        user_message = {"role": "user", "content": f"Please check this query: {tool_call['args']['query']}"}
        llm_with_tools = llm.bind_tools([run_query_tool], tool_choice="any")
        response = llm_with_tools.invoke([system_message, user_message])
        # Preserve the original tool call ID for routing
        response.id = state["messages"][-1].id
        return {"messages": [response]}

    def should_continue(state: MessagesState) -> Literal[END, "check_query"]:
        return "check_query" if state["messages"][-1].tool_calls else END

    # 5. Build the graph
    builder = StateGraph(MessagesState)
    builder.add_node("list_tables", list_tables)
    builder.add_node("call_get_schema", call_get_schema)
    builder.add_node("get_schema", get_schema_node)
    builder.add_node("generate_query", generate_query)
    builder.add_node("check_query", check_query)
    builder.add_node("run_query", run_query_node)

    builder.add_edge(START, "list_tables")
    builder.add_edge("list_tables", "call_get_schema")
    builder.add_edge("call_get_schema", "get_schema")
    builder.add_edge("get_schema", "generate_query")
    builder.add_conditional_edges("generate_query", should_continue)
    builder.add_edge("check_query", "run_query")
    builder.add_edge("run_query", "generate_query") # Loop back to refine or answer

    return builder.compile()