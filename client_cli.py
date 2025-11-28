import argparse
import asyncio
import json
import sys

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from config import setup_logging

setup_logging()


THINKING_MESSAGE = "Sto cercando le informazioni..."


def print_tool_call(tool_call: dict) -> None:
    name = tool_call.get("name", "unknown")
    args = tool_call.get("args", {})
    print(f"\n  [TOOL CALL] {name}")
    for key, value in args.items():
        display_value = str(value)[:50] + "..." if len(str(value)) > 50 else str(value)
        print(f"    {key}: {display_value}")


def print_tool_result(name: str, content: str) -> None:
    print(f"\n  [TOOL RESULT] ({name})")
    preview = content[:200] + "..." if len(content) > 200 else content
    for line in preview.split("\n")[:10]:
        print(f"    {line}")


async def run_cli(chatbot_name: str) -> None:
    if chatbot_name == "noi_energia":
        from chatbots.noi_energia_chatbot.agent import create_noi_energia_chatbot_agent

        print("\nInitializing NOI Energia Chatbot...")
        agent = await create_noi_energia_chatbot_agent()
        title = "NOI ENERGIA CHATBOT CLI"
    elif chatbot_name == "noi_cer":
        from chatbots.noi_cer_chatbot.agent import create_noi_cer_chatbot_agent

        print("\nInitializing NOI CER Chatbot...")
        agent = await create_noi_cer_chatbot_agent()
        title = "NOI CER CHATBOT CLI"
    else:
        print(f"Unknown chatbot: {chatbot_name}")
        sys.exit(1)

    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print("=" * 60)
    print("Commands: /quit, /exit, /clear, /history")
    print("=" * 60)

    messages = []
    session_id = f"cli_{chatbot_name}"

    while True:
        try:
            user_input = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\nGoodbye!")
            break

        if not user_input:
            continue

        if user_input.lower() in ("/quit", "/exit"):
            print("\nGoodbye!")
            break

        if user_input.lower() == "/clear":
            messages = []
            print("Conversation cleared.")
            continue

        if user_input.lower() == "/history":
            if not messages:
                print("No messages in history.")
            else:
                print(f"\n--- History ({len(messages)} messages) ---")
                for i, msg in enumerate(messages, 1):
                    role = type(msg).__name__
                    content_preview = (
                        str(msg.content)[:100] if hasattr(msg, "content") else "N/A"
                    )
                    print(f"{i}. [{role}] {content_preview}")
            continue

        messages.append(HumanMessage(content=user_input))
        print("\nProcessing...")

        thinking_shown = False
        tool_calls_this_turn = []
        final_response = None

        try:
            async for event in agent.astream_events(
                {"messages": messages, "failed_document_ids": set()},
                config={
                    "configurable": {"thread_id": session_id},
                    "recursion_limit": 30,
                },
                version="v2",
            ):
                event_type = event.get("event")
                event_name = event.get("name", "")

                if event_type == "on_chain_start" and event_name == "tools":
                    if not thinking_shown:
                        thinking_shown = True
                        print(f"\n{THINKING_MESSAGE}")

                if event_type == "on_tool_start":
                    if not thinking_shown:
                        thinking_shown = True
                        print(f"\n{THINKING_MESSAGE}")

                if event_type == "on_chain_end":
                    output = event.get("data", {}).get("output", {})
                    if isinstance(output, dict) and "messages" in output:
                        final_response = output

            if final_response:
                response_messages = final_response.get("messages", [])
            else:
                result = await agent.ainvoke(
                    {"messages": messages, "failed_document_ids": set()},
                    config={
                        "configurable": {"thread_id": session_id},
                        "recursion_limit": 30,
                    },
                )
                response_messages = (
                    result.get("messages", []) if isinstance(result, dict) else []
                )

            for msg in response_messages:
                if isinstance(msg, AIMessage) and getattr(msg, "tool_calls", None):
                    for tc in msg.tool_calls:
                        print_tool_call(tc)
                        tool_calls_this_turn.append(tc.get("name", "unknown"))

                if isinstance(msg, ToolMessage):
                    tool_name = (
                        getattr(msg, "name", None) or tool_calls_this_turn.pop(0)
                        if tool_calls_this_turn
                        else "unknown"
                    )
                    content = (
                        msg.content
                        if isinstance(msg.content, str)
                        else json.dumps(msg.content, indent=2)
                    )
                    print_tool_result(tool_name, content)

            final_text = None
            for msg in reversed(response_messages):
                if isinstance(msg, AIMessage) and not getattr(msg, "tool_calls", None):
                    final_text = msg.content
                    break

            if final_text:
                messages.append(AIMessage(content=final_text))
                print(f"\nAssistant:\n  {final_text}")
            else:
                print("\nAssistant: [No response generated]")

        except Exception as e:
            print(f"\nError: {e}")


def main():
    parser = argparse.ArgumentParser(description="Chatbot CLI Client")
    parser.add_argument(
        "-c",
        "--chatbot",
        choices=["noi_energia", "noi_cer"],
        required=True,
        help="Chatbot to use (noi_energia or noi_cer)",
    )
    args = parser.parse_args()

    asyncio.run(run_cli(args.chatbot))


if __name__ == "__main__":
    main()
