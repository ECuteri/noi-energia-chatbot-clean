import logging

from quart import Blueprint, jsonify, request

from services.supabase_client import supabase_store

logger = logging.getLogger(__name__)
chat_history_bp = Blueprint("chat_history_bp", __name__)


@chat_history_bp.route("/chat-history/<session_id>", methods=["GET"])
async def view_chat_history_route(session_id):
    try:
        limit = request.args.get("limit", default=50, type=int)
        messages = await supabase_store.get_chat_history(session_id, limit)
        return (
            jsonify(
                {
                    "session_id": session_id,
                    "messages": messages,
                    "total_messages": len(messages),
                }
            ),
            200,
        )
    except Exception as e:
        logger.error(
            f"Error retrieving chat history for session_id {session_id}: {str(e)}",
            exc_info=True,
        )
        return (
            jsonify({"error": "Failed to retrieve chat history", "message": str(e)}),
            500,
        )
