import logging
from typing import Optional

from langchain_core.messages import AIMessage, HumanMessage
from quart import Blueprint, current_app, jsonify, request

from services.supabase_client import supabase_store

logger = logging.getLogger(__name__)
local_test_bp = Blueprint("local_test_bp", __name__)


@local_test_bp.route("/local-chat", methods=["POST"])
async def local_chat_route():
    try:
        data = await request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "Empty request body"}), 400

        user_id = data.get("user_id")
        message = data.get("message")
        chatbot = data.get("chatbot", "noi_cer")

        if not user_id or not isinstance(user_id, str):
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": "'user_id' is required and must be a string",
                    }
                ),
                400,
            )
        if not message or not isinstance(message, str):
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": "'message' is required and must be a string",
                    }
                ),
                400,
            )

        if chatbot == "noi_cer":
            agent = current_app.config.get("NOI_CER_CHATBOT")
        elif chatbot == "noi_energia":
            agent = current_app.config.get("NOI_ENERGIA_CHATBOT")
        else:
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": "Invalid chatbot. Use 'noi_cer' or 'noi_energia'",
                    }
                ),
                400,
            )

        if not agent:
            logger.error(f"[local:{user_id}] {chatbot} chatbot not initialized.")
            return (
                jsonify({"status": "error", "message": "Chatbot not initialized"}),
                500,
            )

        try:
            await supabase_store.save_chat_message(user_id, "user", message)
        except Exception as e:
            logger.warning(f"[local:{user_id}] Failed saving user message: {e}")

        session_id = user_id

        try:
            logger.info(
                f"[local:{user_id}] Invoking {chatbot} agent. Session: {session_id}"
            )
            result = await agent.ainvoke(
                {"messages": [HumanMessage(content=message)]},
                config={"configurable": {"thread_id": session_id}},
            )
        except Exception as invoke_err:
            logger.error(
                f"[local:{user_id}] Error during agent invocation: {invoke_err}",
                exc_info=True,
            )
            return (
                jsonify({"status": "error", "message": "Agent invocation failed"}),
                500,
            )

        messages_this_turn = (
            result.get("messages", []) if isinstance(result, dict) else []
        )

        final_agent_message = None
        for msg in reversed(messages_this_turn):
            if isinstance(msg, AIMessage) and not getattr(msg, "tool_calls", None):
                final_agent_message = msg.content
                break
            if isinstance(msg, dict) and msg.get("role") == "assistant":
                tool_calls = msg.get("tool_calls") or (
                    msg.get("additional_kwargs", {}) or {}
                ).get("tool_calls")
                if not tool_calls:
                    final_agent_message = msg.get("content")
                    break

        cleaned_response = (
            str(final_agent_message) if final_agent_message is not None else ""
        )

        if cleaned_response:
            try:
                await supabase_store.save_chat_message(
                    user_id, "assistant", cleaned_response
                )
            except Exception as e:
                logger.warning(
                    f"[local:{user_id}] Failed saving assistant message: {e}"
                )

        return (
            jsonify(
                {
                    "status": "success",
                    "user_id": user_id,
                    "session_id": session_id,
                    "chatbot": chatbot,
                    "response": cleaned_response,
                    "messages_returned": len(messages_this_turn),
                }
            ),
            200,
        )
    except Exception as e:
        logger.error(f"[local] Unexpected error: {e}", exc_info=True)
        return jsonify({"status": "error", "message": "Internal server error"}), 500


@local_test_bp.route("/local-chat/reset", methods=["POST"])
async def local_chat_reset_route():
    try:
        data = await request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "Empty request body"}), 400
        user_id = data.get("user_id")
        if not user_id or not isinstance(user_id, str):
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": "'user_id' is required and must be a string",
                    }
                ),
                400,
            )

        logger.info(f"[local:{user_id}] Reset requested (no-op)")
        return (
            jsonify(
                {
                    "status": "success",
                    "user_id": user_id,
                    "message": "Reset completed",
                }
            ),
            200,
        )
    except Exception as e:
        logger.error(f"[local] Error during reset: {e}", exc_info=True)
        return jsonify({"status": "error", "message": "Internal server error"}), 500
