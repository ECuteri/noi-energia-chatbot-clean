import logging
import os

from chatbots.common.agent_factory import create_chatbot_agent
from chatbots.common.tools.get_file_contents import create_get_file_contents_tool
from chatbots.common.tools.list_documents import create_list_documents_tool
from chatbots.common.tools.vector_search import create_vector_search_tool

logger = logging.getLogger(__name__)


def load_system_prompt():
    prompt_file_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "prompts",
        "noi_cer_chatbot.txt",
    )

    try:
        with open(prompt_file_path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        logger.error(f"Prompt file not found: {prompt_file_path}")
        raise
    except Exception as e:
        logger.error(f"Error loading prompt file: {e}")
        raise


async def create_noi_cer_chatbot_agent():
    list_documents = create_list_documents_tool(
        table_name="noi_cer_documents",
        metadata_table_name="noi_cer_documents_metadata",
        chatbot_name="Noi CER",
    )

    get_file_contents = create_get_file_contents_tool(
        table_name="noi_cer_documents",
        metadata_table_name="noi_cer_documents_metadata",
        chatbot_name="Noi CER",
    )

    vector_search = create_vector_search_tool(
        table_name="noi_cer_documents", chatbot_name="Noi CER"
    )

    tools = [list_documents, get_file_contents, vector_search]
    system_prompt = load_system_prompt()

    return await create_chatbot_agent(
        chatbot_name="Noi CER Chatbot",
        model_name="openai/gpt-oss-120b",
        tools=tools,
        system_prompt=system_prompt,
        temperature=0.2,
    )
