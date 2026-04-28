from langchain_core.messages import HumanMessage, SystemMessage

_SYSTEM = """You are the RE Lore Oracle, an expert on the Resident Evil franchise.
Answer questions using only the provided evidence. Be concise and accurate.
If the evidence does not contain enough information, say so honestly.
Do not invent lore that is not supported by the evidence."""


def build_prompt(query: str, evidence: str) -> list:
    return [
        SystemMessage(content=_SYSTEM),
        HumanMessage(content=f"Evidence:\n{evidence}\n\nQuestion: {query}"),
    ]
