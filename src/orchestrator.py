"""Agent construction is lazy; every reasoning call receives the operational policy."""
import os
from functools import lru_cache
from typing import Annotated, TypedDict
from langchain_core.messages import BaseMessage, SystemMessage
from langgraph.graph import StateGraph, START
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.memory import MemorySaver
from src.agent_tools import query_telemetry_db, fetch_corridor_conditions, search_compliance_sop, assess_fresh_perishable
from src.retrieval import ROOT
from src.storage import audit

TOOLS = [query_telemetry_db, fetch_corridor_conditions, search_compliance_sop, assess_fresh_perishable]


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]


@lru_cache(maxsize=1)
def get_agent():
    provider = os.getenv('AGENT_LLM', os.getenv('Agent_llm', 'DEMO')).upper()
    model = os.getenv('LLM_MODEL')
    if provider == 'OPENAI':
        from langchain_openai import ChatOpenAI
        llm = ChatOpenAI(model=model or 'gpt-4o-mini', temperature=0, timeout=30, max_retries=1)
    elif provider == 'DEEPSEEK':
        from langchain_openai import ChatOpenAI
        llm = ChatOpenAI(model=model or 'deepseek-chat', api_key=os.getenv('DEEPSEEK_API_KEY'),
                         base_url='https://api.deepseek.com', temperature=0, timeout=30, max_retries=1)
    elif provider == 'OLLAMA':
        from langchain_ollama import ChatOllama
        llm = ChatOllama(model=model or 'qwen2.5:7b', temperature=0,
                         base_url=os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434'),
                         client_kwargs={'timeout': 30})
    else:
        raise ValueError('Choose OPENAI, OLLAMA or DEEPSEEK for chat. DEMO provides local evidence search.')
    bound = llm.bind_tools(TOOLS)
    policy = (ROOT / 'src/prompts/system_prompt.txt').read_text()

    def reason(state):
        messages = [m for m in state['messages'] if not isinstance(m, SystemMessage)]
        response = bound.invoke([SystemMessage(content=policy), *messages])
        if len(response.tool_calls) > 4:
            raise ValueError('Too many parallel tool requests. Refine the question.')
        return {'messages': [response]}

    node = ToolNode(TOOLS, handle_tool_errors=True)

    def execute(state, config):
        session = config['configurable']['thread_id']
        calls = state['messages'][-1].tool_calls
        audit(session, 'tool_requests', calls)
        result = node.invoke(state, config)
        for message in result['messages']:
            audit(session, 'tool_result', {'tool': message.name, 'content': message.content})
        return result

    builder = StateGraph(AgentState)
    builder.add_node('reasoner', reason)
    builder.add_node('tools', execute)
    builder.add_edge(START, 'reasoner')
    builder.add_conditional_edges('reasoner', tools_condition)
    builder.add_edge('tools', 'reasoner')
    return builder.compile(checkpointer=MemorySaver())
