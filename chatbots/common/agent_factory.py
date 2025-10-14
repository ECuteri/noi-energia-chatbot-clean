import logging
from typing import Callable, List

from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq
from langgraph.graph import StateGraph
from langgraph.prebuilt import ToolNode

from chatbots.common.schemas import ChatbotState
from config import GROQ_API_KEY

logger = logging.getLogger(__name__)


async def create_chatbot_agent(
    chatbot_name: str,
    model_name: str,
    tools: List[Callable],
    system_prompt: str,
    temperature: float = 0.2,
):
    if not GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY is not configured.")

    model = ChatGroq(model=model_name, temperature=temperature, api_key=GROQ_API_KEY)

    logger.info(f"🤖 {chatbot_name.upper()} CONFIG:")
    logger.info(f"   Model: {model_name}")
    logger.info(f"   Temperature: {temperature}")
    logger.info(
        f"   API Key: {'***' + GROQ_API_KEY[-4:] if GROQ_API_KEY else 'NOT_SET'}"
    )

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            ("placeholder", "{messages}"),
        ]
    )

    agent_runnable = prompt | model.bind_tools(tools)

    builder = StateGraph(ChatbotState)

    async def run_agent(state):
        messages = state.get("messages", [])
        failed_ids = state.get("failed_document_ids", set())
        logger.info(
            f"{chatbot_name} processing {len(messages)} messages, {len(failed_ids)} failed IDs tracked"
        )

        try:
            result = await agent_runnable.ainvoke({"messages": messages})
            logger.info(
                f"{chatbot_name} generated response with tool_calls: {bool(getattr(result, 'tool_calls', None))}"
            )
            return {"messages": [result]}
        except Exception as e:
            logger.error(f"Error in {chatbot_name}: {e}")
            error_msg = "I apologize, but I encountered an error while processing your request. Please try again."
            return {"messages": [{"role": "assistant", "content": error_msg}]}

    builder.add_node("agent", run_agent)
    tool_node = ToolNode(tools)
    builder.add_node("tools", tool_node)

    def should_continue(state):
        messages = state.get("messages", [])
        if not messages:
            return "__end__"

        last_message = messages[-1]
        has_tool_calls = bool(getattr(last_message, "tool_calls", None))

        tool_call_count = sum(
            1 for msg in messages if hasattr(msg, "tool_calls") and msg.tool_calls
        )

        recent_tool_calls = sum(
            1 for msg in messages[-8:] if hasattr(msg, "tool_calls") and msg.tool_calls
        )

        recent_errors = sum(
            1
            for msg in messages[-10:]
            if hasattr(msg, "content")
            and isinstance(msg.content, str)
            and ("not found" in msg.content.lower() or "error" in msg.content.lower())
        )

        if tool_call_count >= 15:
            logger.warning(
                f"{chatbot_name} reached {tool_call_count} total tool calls. Forcing stop to prevent infinite loop."
            )
            return "__end__"

        if recent_tool_calls >= 6:
            logger.warning(
                f"{chatbot_name} made {recent_tool_calls} tool calls in recent messages. Forcing stop."
            )
            return "__end__"

        if recent_errors >= 3:
            logger.warning(
                f"{chatbot_name} detected {recent_errors} consecutive errors. Stopping to prevent loop."
            )
            return "__end__"

        logger.debug(
            f"Should continue: has_tool_calls={has_tool_calls}, total_calls={tool_call_count}, recent_calls={recent_tool_calls}, recent_errors={recent_errors}"
        )
        if has_tool_calls:
            return "tools"
        return "__end__"

    builder.set_entry_point("agent")
    builder.add_conditional_edges("agent", should_continue)
    builder.add_edge("tools", "agent")

    graph = builder.compile()

    logger.info(
        f"{chatbot_name} agent created successfully with aggressive loop prevention"
    )
    return graph
