import json
import os
from typing import Annotated, Optional

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_groq import ChatGroq
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

from tools import mock_lead_capture

with open("knowledge.json") as f:
	KNOWLEDGE = json.dumps(json.load(f), indent=2)


class AgentState(TypedDict):
	messages: Annotated[list, add_messages]  # append-only via reducer
	intent: Optional[str]  # "greeting" | "product_inquiry" | "high_intent"
	lead_name: Optional[str]
	lead_email: Optional[str]
	lead_platform: Optional[str]
	lead_captured: bool


load_dotenv()
llm = ChatGroq(model="llama-3.1-8b-instant", api_key=os.getenv("GROQ_API_KEY"), temperature=0.3)
intent_llm = ChatGroq(model="llama-3.1-8b-instant", api_key=os.getenv("GROQ_API_KEY"), temperature=0)


def detect_intent_node(state: AgentState) -> dict:
	last_message = state["messages"][-1].content

	response = intent_llm.invoke([
		SystemMessage(content="""Classify the user message into exactly one of:
- greeting
- product_inquiry
- high_intent

Rules:
- high_intent = user wants to sign up, try, buy, want to, subscribe, or mentions my YouTube, my channel, my Instagram
- product_inquiry = questions about pricing, features, plans
- greeting = hello, hi, general chat

Respond with ONLY the label. No explanation."""),
		HumanMessage(content=last_message),
	])

	intent = response.content.strip().lower()
	if intent not in ["greeting", "product_inquiry", "high_intent"]:
		intent = "product_inquiry"

	return {"intent": intent}


def rag_node(state: AgentState) -> dict:
	messages = state["messages"]

	response = llm.invoke([
		SystemMessage(content=f"""You are a helpful sales assistant for AutoStream, a SaaS video editing tool for content creators.

Answer questions using ONLY the following knowledge base:
{KNOWLEDGE}

Be friendly and concise. If asked about pricing, give exact numbers."""),
		*messages,
	])

	return {"messages": [response]}


def lead_collection_node(state: AgentState) -> dict:
	if not state.get("lead_name"):
		return {"messages": [AIMessage(content="Great! I'd love to get you started. Could you share your name?")]}

	if not state.get("lead_email"):
		return {"messages": [AIMessage(content=f"Thanks {state['lead_name']}! What's your email address?")]}

	if not state.get("lead_platform"):
		return {
			"messages": [
				AIMessage(content="Perfect! Which platform do you create content on? (e.g. YouTube, Instagram, TikTok)")
			]
		}

	return {"intent": "trigger_capture"}


def tool_execution_node(state: AgentState) -> dict:
	name = state["lead_name"]
	email = state["lead_email"]
	platform = state["lead_platform"]

	mock_lead_capture(name, email, platform)

	return {
		"messages": [AIMessage(content=f"You're all set, {name}! We'll reach out to {email} shortly. Welcome to AutoStream!")],
		"lead_captured": True,
	}


def is_collecting_lead(state: AgentState) -> bool:
	has_any_field = bool(state.get("lead_name") or state.get("lead_email") or state.get("lead_platform"))
	return not state.get("lead_captured") and (state.get("intent") == "high_intent" or has_any_field)


def route_by_intent(state: AgentState) -> str:
	if is_collecting_lead(state):
		return "lead_collection"
	return "rag"


def route_lead_flow(state: AgentState):
	name = state.get("lead_name")
	email = state.get("lead_email")
	platform = state.get("lead_platform")

	if name and email and platform:
		return "tool_execution"
	return END


builder = StateGraph(AgentState)
builder.add_node("detect_intent", detect_intent_node)
builder.add_node("rag", rag_node)
builder.add_node("lead_collection", lead_collection_node)
builder.add_node("tool_execution", tool_execution_node)

builder.add_edge(START, "detect_intent")
builder.add_conditional_edges("detect_intent", route_by_intent, {
	"rag": "rag",
	"lead_collection": "lead_collection",
})
builder.add_edge("rag", END)
builder.add_conditional_edges("lead_collection", route_lead_flow, {
	"tool_execution": "tool_execution",
	END: END,
})
builder.add_edge("tool_execution", END)

graph = builder.compile()


def get_last_ai_message(state: AgentState) -> str:
	for msg in reversed(state["messages"]):
		if isinstance(msg, AIMessage):
			return msg.content
	return ""


def run():
	state: AgentState = {
		"messages": [],
		"intent": None,
		"lead_name": None,
		"lead_email": None,
		"lead_platform": None,
		"lead_captured": False,
	}

	print("AutoStream Agent — type 'quit' to exit\n")

	while not state.get("lead_captured"):
		user_input = input("You: ").strip()
		if user_input.lower() in ("quit", "exit"):
			break

		# If in lead collection flow, save input to the right state field
		if is_collecting_lead(state):
			if not state["lead_name"]:
				state["lead_name"] = user_input
			elif not state["lead_email"]:
				state["lead_email"] = user_input
			elif not state["lead_platform"]:
				state["lead_platform"] = user_input

		state["messages"].append(HumanMessage(content=user_input))
		state = graph.invoke(state)

		reply = get_last_ai_message(state)
		if reply:
			print(f"Agent: {reply}\n")

	print("Session ended.")


if __name__ == "__main__":
	run()
