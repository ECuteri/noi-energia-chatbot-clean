import operator
from typing import Annotated, Sequence, Set

from langchain_core.messages import BaseMessage


class ChatbotState(dict):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    failed_document_ids: Set[str]
