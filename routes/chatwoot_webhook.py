import asyncio
import hashlib
import hmac
import json
import logging
import time
import traceback
from typing import Any, Dict

from langchain_core.messages import AIMessage, HumanMessage
from quart import Blueprint, current_app, jsonify, request

from config import (
    CHATWOOT_NOI_CER_BOT_TOKEN,
    CHATWOOT_NOI_CER_INBOX_ID,
    CHATWOOT_NOI_CER_WEBHOOK_SECRET,
    CHATWOOT_NOI_ENERGIA_BOT_TOKEN,
    CHATWOOT_NOI_ENERGIA_INBOX_ID,
    CHATWOOT_NOI_ENERGIA_WEBHOOK_SECRET,
)
from services.chatwoot import send_chatwoot_message
from services.supabase_client import supabase_store
from services.voice_transcription import process_message_attachments

logger = logging.getLogger(__name__)
chatwoot_webhook_bp = Blueprint("chatwoot_webhook_bp", __name__)


def _mask_sensitive_value(value: Any) -> str:
    if not isinstance(value, str):
        return str(value)
    val = value
    if value.lower().startswith("bearer "):
        token_part = value.split(" ", 1)[1]
        return "Bearer " + _mask_sensitive_value(token_part)
    if len(val) <= 8:
        return "*" * len(val)
    return f"{val[:4]}...{val[-4:]}"


def _scrub_headers_for_logging(headers) -> Dict[str, str]:
    sensitive_keywords = {"authorization", "token", "signature", "api_access_token"}
    scrubbed: Dict[str, str] = {}
    try:
        for k, v in headers.items():
            key_lower = str(k).lower()
            if any(sk in key_lower for sk in sensitive_keywords):
                scrubbed[k] = _mask_sensitive_value(v)
            else:
                scrubbed[k] = v
    except Exception:
        try:
            return {str(k): _mask_sensitive_value(v) for k, v in dict(headers).items()}
        except Exception:
            return {"error": "could_not_scrub_headers"}
    return scrubbed


def _is_authorized(
    raw_body: bytes, headers, webhook_secret: str, bot_token: str, args=None
) -> bool:
    try:
        parsed = json.loads(raw_body.decode("utf-8"))
        is_account_webhook = bool(parsed.get("event"))
    except Exception:
        is_account_webhook = False

    want_hmac = bool(webhook_secret)
    want_token = bool(bot_token)

    ok_sig = False
    received = headers.get("X-Chatwoot-Signature")
    if want_hmac and received:
        digest = hmac.new(
            webhook_secret.encode("utf-8"), raw_body, hashlib.sha256
        ).hexdigest()
        try:
            ok_sig = hmac.compare_digest(digest, received)
        except Exception:
            ok_sig = False

    ok_token = False
    if want_token:
        candidate_headers = [
            "X-Chatwoot-Bot-Token",
            "X-Chatwoot-Webhook-Token",
            "X-Chatwoot-Token",
            "X-Chatwoot-Api-Access-Token",
            "Api-Access-Token",
            "X-Api-Access-Token",
            "api_access_token",
            "Authorization",
        ]
        for name in candidate_headers:
            val = headers.get(name)
            if not val:
                continue
            if name.lower() == "authorization" and isinstance(val, str):
                low = val.lower()
                if low.startswith("bearer "):
                    val = val.split(" ", 1)[1]
                elif low.startswith("token "):
                    rest = val.split(" ", 1)[1]
                    if "token=" in rest:
                        val = rest.split("token=", 1)[1].strip()
                    else:
                        val = rest.strip()
            if val == bot_token:
                ok_token = True
                break

        if not ok_token and args is not None:
            try:
                for qname in ("api_access_token", "access_token", "token", "bot_token"):
                    qval = args.get(qname)
                    if qval and qval == bot_token:
                        ok_token = True
                        break
            except Exception:
                pass

    if is_account_webhook:
        if want_hmac:
            return ok_sig
        return True
    else:
        if want_token:
            return ok_token
        return True


async def _process_incoming(
    payload: Dict[str, Any], agent_name: str, inbox_id: str, bot_token: str
) -> None:
    start_time = time.time()
    conversation_id = None
    contact_identifier = None

    try:
        event = payload.get("event")
        logger.info(f"[cw:{agent_name}] Processing started - Event: {event}")

        if event is not None and event != "message_created":
            logger.info(
                f"[cw:{agent_name}] Skipping non-message_created event: {event}"
            )
            return

        data = payload.get("data") or payload
        message_type = data.get("message_type")
        sender_obj = data.get("sender") or {}
        sender_type = (
            sender_obj.get("type") or sender_obj.get("sender_type") or ""
        ).lower()
        private_flag = bool(data.get("private"))

        is_incoming = (
            message_type == "incoming"
            or (
                message_type is None
                and sender_type in {"contact", "customer", "visitor"}
            )
            or (message_type is None and not private_flag)
        )

        if not is_incoming:
            logger.info(f"[cw:{agent_name}] Skipping non-incoming message")
            return

        conversation = data.get("conversation") or {}
        conversation_id = conversation.get("id")
        inbox_id_from_payload = conversation.get("inbox_id") or (
            data.get("inbox") or {}
        ).get("id")
        contact = data.get("sender") or {}
        contact_inbox = conversation.get("contact_inbox") or {}
        source_id = contact_inbox.get("source_id")

        contact_identifier = str(
            source_id
            or contact.get("phone_number")
            or contact.get("identifier")
            or contact.get("id")
            or ""
        )

        content = (
            data.get("content")
            or (data.get("message", {}) or {}).get("content")
            or data.get("processed_message_content")
            or ""
        )

        attachments = (
            data.get("attachments")
            or (data.get("message", {}) or {}).get("attachments")
            or []
        )

        attachment_result = await process_message_attachments(attachments, content)
        final_content = attachment_result["final_content"]

        logger.info(
            f"[cw:{agent_name}:{contact_identifier}] convo_id={conversation_id} inbox_id={inbox_id_from_payload} "
            f"content_len={len(final_content)} has_voice={attachment_result['has_voice']}"
        )

        if not (conversation_id and final_content and contact_identifier):
            logger.warning(
                f"[cw:{agent_name}:{contact_identifier}] Missing required fields. convo_id={conversation_id}, content_len={len(final_content)}, contact_id={contact_identifier}"
            )
            return

        session_id = f"{agent_name}:{contact_identifier}"

        save_start = time.time()
        try:
            await supabase_store.save_chat_message(session_id, "user", final_content)
            save_time = time.time() - save_start
            logger.info(
                f"[cw:{agent_name}:{contact_identifier}] User message saved - Time: {save_time:.3f}s"
            )
        except Exception as e:
            save_time = time.time() - save_start
            logger.warning(
                f"[cw:{agent_name}:{contact_identifier}] Failed saving user message - Time: {save_time:.3f}s - Error: {e}"
            )

        agent = current_app.config.get(
            "NOI_CER_CHATBOT" if agent_name == "noi_cer" else "NOI_ENERGIA_CHATBOT"
        )
        if not agent:
            logger.error(
                f"[cw:{agent_name}:{contact_identifier}] Agent not initialized"
            )
            return

        history_start = time.time()
        try:
            chat_history = await supabase_store.get_chat_history(session_id, limit=20)
            history_time = time.time() - history_start
            logger.info(
                f"[cw:{agent_name}:{contact_identifier}] Loaded {len(chat_history)} messages from history - Time: {history_time:.3f}s"
            )
        except Exception as e:
            history_time = time.time() - history_start
            logger.error(
                f"[cw:{agent_name}:{contact_identifier}] Failed loading chat history - Time: {history_time:.3f}s - Error: {e}"
            )
            return

        messages = []
        for msg in chat_history:
            if msg["role"] == "user":
                messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "assistant":
                messages.append(AIMessage(content=msg["content"]))

        if not any(
            isinstance(m, HumanMessage) and m.content == final_content for m in messages
        ):
            messages.append(HumanMessage(content=final_content))

        agent_start = time.time()
        logger.info(
            f"[cw:{agent_name}:{contact_identifier}] Invoking agent with {len(messages)} messages. Session: {session_id}"
        )
        try:
            result = await agent.ainvoke(
                {"messages": messages, "failed_document_ids": set()},
                config={
                    "configurable": {"thread_id": session_id},
                    "recursion_limit": 30,
                },
            )
            agent_time = time.time() - agent_start
            logger.info(
                f"[cw:{agent_name}:{contact_identifier}] Agent invocation completed - Time: {agent_time:.3f}s"
            )
        except Exception as invoke_err:
            agent_time = time.time() - agent_start
            logger.error(
                f"[cw:{agent_name}:{contact_identifier}] Agent invoke error - Time: {agent_time:.3f}s - Error: {invoke_err}",
                exc_info=True,
            )
            return

        messages_this_turn = (
            result.get("messages", []) if isinstance(result, dict) else []
        )

        if messages_this_turn:
            to_log = messages_this_turn[-10:]
            for i, msg_obj in enumerate(to_log, start=1):
                try:
                    msg_type = type(msg_obj).__name__
                    content_preview = (
                        str(msg_obj.content)[:100]
                        if hasattr(msg_obj, "content")
                        else "No content"
                    )
                    logger.info(
                        f"[cw:{agent_name}:{contact_identifier}] Response msg {i}: {msg_type} - {content_preview}"
                    )
                except Exception as e:
                    logger.warning(
                        f"[cw:{agent_name}:{contact_identifier}] Failed to log response message {i}: {e}"
                    )

        final_text = None
        for msg in reversed(messages_this_turn):
            if isinstance(msg, AIMessage) and not getattr(msg, "tool_calls", None):
                final_text = msg.content
                break
            if isinstance(msg, dict) and msg.get("role") == "assistant":
                tool_calls = msg.get("tool_calls") or (
                    msg.get("additional_kwargs", {}) or {}
                ).get("tool_calls")
                if not tool_calls:
                    final_text = msg.get("content")
                    break

        if final_text:
            cleaned = str(final_text).strip()
            try:
                conv_id_int = int(conversation_id)
            except (ValueError, TypeError) as e:
                logger.warning(
                    f"[cw:{agent_name}:{contact_identifier}] Invalid conversation ID: {conversation_id} - {e}"
                )
                conv_id_int = None

            if conv_id_int is not None and cleaned:
                save_assistant_start = time.time()
                try:
                    await supabase_store.save_chat_message(
                        session_id, "assistant", cleaned
                    )
                    save_assistant_time = time.time() - save_assistant_start
                    logger.info(
                        f"[cw:{agent_name}:{contact_identifier}] Assistant message saved - Time: {save_assistant_time:.3f}s"
                    )
                except Exception as e:
                    save_assistant_time = time.time() - save_assistant_start
                    logger.warning(
                        f"[cw:{agent_name}:{contact_identifier}] Failed saving assistant message - Time: {save_assistant_time:.3f}s - Error: {e}"
                    )

                await asyncio.sleep(3)

                send_start = time.time()
                logger.debug(
                    f"[cw:{agent_name}:{contact_identifier}] Sending reply to Chatwoot..."
                )
                try:
                    send_res = await send_chatwoot_message(
                        conv_id_int,
                        contact_identifier,
                        text=cleaned,
                        bot_token=bot_token,
                    )
                    send_time = time.time() - send_start

                    if send_res and send_res.get("status") == "success":
                        logger.info(
                            f"[cw:{agent_name}:{contact_identifier}] AI reply sent successfully - Time: {send_time:.3f}s"
                        )
                    else:
                        logger.warning(
                            f"[cw:{agent_name}:{contact_identifier}] Failed sending AI reply - Time: {send_time:.3f}s - Response: {send_res}"
                        )
                except Exception as e:
                    send_time = time.time() - send_start
                    logger.error(
                        f"[cw:{agent_name}:{contact_identifier}] Error sending reply - Time: {send_time:.3f}s - Error: {e}",
                        exc_info=True,
                    )

        total_time = time.time() - start_time
        logger.info(
            f"[cw:{agent_name}:{contact_identifier}] Processing completed successfully - Total time: {total_time:.3f}s"
        )

    except Exception as e:
        total_time = time.time() - start_time
        logger.error(
            f"[cw:{agent_name}:{contact_identifier or 'unknown'}] Unhandled processing error - Time: {total_time:.3f}s - Error: {e}",
            exc_info=True,
        )


@chatwoot_webhook_bp.route("/chatwoot/webhook/noi-cer", methods=["POST"])
async def chatwoot_webhook_noi_cer():
    start_time = time.time()
    request_id = f"req_{int(time.time()*1000)}_{id(asyncio.current_task()) % 1000}"

    try:
        raw = await request.get_data()
        processing_time = time.time() - start_time

        logger.info(
            f"[{request_id}] [cw:noi_cer] Webhook request started - Method: {request.method}, Content-Length: {len(raw)}, Processing time: {processing_time:.3f}s"
        )

        logger.info(
            f"[{request_id}] [cw:noi_cer] Headers: {_scrub_headers_for_logging(request.headers)}"
        )

        if request.args:
            logger.info(
                f"[{request_id}] [cw:noi_cer] Query params: "
                f"{json.dumps({k: _mask_sensitive_value(v) for k, v in request.args.items()})}"
            )

        try:
            payload_str = raw.decode("utf-8")
            preview = json.loads(payload_str)
            logger.info(
                f"[{request_id}] [cw:noi_cer] Payload preview - event: {preview.get('event')}, message_type: {preview.get('message_type')}"
            )
        except Exception as e:
            logger.warning(
                f"[{request_id}] [cw:noi_cer] Failed to parse payload preview: {e}"
            )

        auth_start = time.time()
        is_authorized = _is_authorized(
            raw,
            request.headers,
            CHATWOOT_NOI_CER_WEBHOOK_SECRET or "",
            CHATWOOT_NOI_CER_BOT_TOKEN or "",
            request.args,
        )
        auth_time = time.time() - auth_start

        if not is_authorized:
            logger.warning(
                f"[{request_id}] [cw:noi_cer] Authorization failed! Auth time: {auth_time:.3f}s"
            )
            return jsonify({"status": "forbidden", "error": "Unauthorized"}), 403

        logger.info(
            f"[{request_id}] [cw:noi_cer] Authorization successful - Time: {auth_time:.3f}s"
        )

        try:
            payload = json.loads(payload_str)
        except json.JSONDecodeError as e:
            logger.error(f"[{request_id}] [cw:noi_cer] Invalid JSON payload: {e}")
            return jsonify({"status": "bad_request", "error": "Invalid JSON"}), 400
        except Exception as e:
            logger.error(
                f"[{request_id}] [cw:noi_cer] Payload parsing error: {e}", exc_info=True
            )
            return (
                jsonify({"status": "bad_request", "error": "Payload parsing failed"}),
                400,
            )

        logger.info(
            f"[{request_id}] [cw:noi_cer] Starting async processing for payload with event: {payload.get('event')}"
        )
        task = asyncio.create_task(
            _process_incoming(
                payload,
                "noi_cer",
                CHATWOOT_NOI_CER_INBOX_ID,
                CHATWOOT_NOI_CER_BOT_TOKEN,
            )
        )

        def log_task_completion(task_result):
            try:
                if task_result.exception():
                    logger.error(
                        f"[{request_id}] [cw:noi_cer] Async processing task failed: {task_result.exception()}",
                        exc_info=True,
                    )
                else:
                    logger.info(
                        f"[{request_id}] [cw:noi_cer] Async processing completed successfully"
                    )
            except Exception as e:
                logger.error(
                    f"[{request_id}] [cw:noi_cer] Task completion logging failed: {e}"
                )

        task.add_done_callback(log_task_completion)

        total_time = time.time() - start_time
        logger.info(
            f"[{request_id}] [cw:noi_cer] Webhook processed successfully - Total time: {total_time:.3f}s"
        )
        return jsonify({"status": "accepted", "request_id": request_id}), 202

    except Exception as e:
        total_time = time.time() - start_time
        logger.error(
            f"[{request_id}] [cw:noi_cer] Webhook processing failed - Time: {total_time:.3f}s - Error: {e}",
            exc_info=True,
        )
        return (
            jsonify(
                {
                    "status": "internal_server_error",
                    "error": "Internal server error",
                    "request_id": request_id,
                }
            ),
            500,
        )


@chatwoot_webhook_bp.route("/chatwoot/webhook/noi-energia", methods=["POST"])
async def chatwoot_webhook_noi_energia():
    start_time = time.time()
    request_id = f"req_{int(time.time()*1000)}_{id(asyncio.current_task()) % 1000}"

    try:
        raw = await request.get_data()
        processing_time = time.time() - start_time

        logger.info(
            f"[{request_id}] [cw:noi_energia] Webhook request started - Method: {request.method}, Content-Length: {len(raw)}, Processing time: {processing_time:.3f}s"
        )

        logger.info(
            f"[{request_id}] [cw:noi_energia] Headers: {_scrub_headers_for_logging(request.headers)}"
        )

        if request.args:
            logger.info(
                f"[{request_id}] [cw:noi_energia] Query params: "
                f"{json.dumps({k: _mask_sensitive_value(v) for k, v in request.args.items()})}"
            )

        try:
            payload_str = raw.decode("utf-8")
            preview = json.loads(payload_str)
            logger.info(
                f"[{request_id}] [cw:noi_energia] Payload preview - event: {preview.get('event')}, message_type: {preview.get('message_type')}"
            )
        except Exception as e:
            logger.warning(
                f"[{request_id}] [cw:noi_energia] Failed to parse payload preview: {e}"
            )

        auth_start = time.time()
        is_authorized = _is_authorized(
            raw,
            request.headers,
            CHATWOOT_NOI_ENERGIA_WEBHOOK_SECRET or "",
            CHATWOOT_NOI_ENERGIA_BOT_TOKEN or "",
            request.args,
        )
        auth_time = time.time() - auth_start

        if not is_authorized:
            logger.warning(
                f"[{request_id}] [cw:noi_energia] Authorization failed! Auth time: {auth_time:.3f}s"
            )
            return jsonify({"status": "forbidden", "error": "Unauthorized"}), 403

        logger.info(
            f"[{request_id}] [cw:noi_energia] Authorization successful - Time: {auth_time:.3f}s"
        )

        try:
            payload = json.loads(payload_str)
        except json.JSONDecodeError as e:
            logger.error(f"[{request_id}] [cw:noi_energia] Invalid JSON payload: {e}")
            return jsonify({"status": "bad_request", "error": "Invalid JSON"}), 400
        except Exception as e:
            logger.error(
                f"[{request_id}] [cw:noi_energia] Payload parsing error: {e}",
                exc_info=True,
            )
            return (
                jsonify({"status": "bad_request", "error": "Payload parsing failed"}),
                400,
            )

        logger.info(
            f"[{request_id}] [cw:noi_energia] Starting async processing for payload with event: {payload.get('event')}"
        )
        task = asyncio.create_task(
            _process_incoming(
                payload,
                "noi_energia",
                CHATWOOT_NOI_ENERGIA_INBOX_ID,
                CHATWOOT_NOI_ENERGIA_BOT_TOKEN,
            )
        )

        def log_task_completion(task_result):
            try:
                if task_result.exception():
                    logger.error(
                        f"[{request_id}] [cw:noi_energia] Async processing task failed: {task_result.exception()}",
                        exc_info=True,
                    )
                else:
                    logger.info(
                        f"[{request_id}] [cw:noi_energia] Async processing completed successfully"
                    )
            except Exception as e:
                logger.error(
                    f"[{request_id}] [cw:noi_energia] Task completion logging failed: {e}"
                )

        task.add_done_callback(log_task_completion)

        total_time = time.time() - start_time
        logger.info(
            f"[{request_id}] [cw:noi_energia] Webhook processed successfully - Total time: {total_time:.3f}s"
        )
        return jsonify({"status": "accepted", "request_id": request_id}), 202

    except Exception as e:
        total_time = time.time() - start_time
        logger.error(
            f"[{request_id}] [cw:noi_energia] Webhook processing failed - Time: {total_time:.3f}s - Error: {e}",
            exc_info=True,
        )
        return (
            jsonify(
                {
                    "status": "internal_server_error",
                    "error": "Internal server error",
                    "request_id": request_id,
                }
            ),
            500,
        )
