import streamlit as st
from langchain_core.messages import AIMessage, HumanMessage

from agent import AgentState, get_last_ai_message, graph, is_collecting_lead


def initial_state() -> AgentState:
	return {
		"messages": [],
		"intent": None,
		"lead_name": None,
		"lead_email": None,
		"lead_platform": None,
		"lead_captured": False,
	}


if "agent_state" not in st.session_state:
	st.session_state["agent_state"] = initial_state()

state: AgentState = st.session_state["agent_state"]

for msg in state["messages"]:
	if isinstance(msg, HumanMessage):
		with st.chat_message("user"):
			st.write(msg.content)
	elif isinstance(msg, AIMessage):
		with st.chat_message("assistant"):
			st.write(msg.content)


prompt = st.chat_input("Message AutoStream agent", disabled=state.get("lead_captured", False))

if prompt:
	with st.chat_message("user"):
		st.write(prompt)

	# Keep lead capture slot-filling behavior consistent with the CLI flow.
	if is_collecting_lead(state):
		if not state["lead_name"]:
			state["lead_name"] = prompt
		elif not state["lead_email"]:
			state["lead_email"] = prompt
		elif not state["lead_platform"]:
			state["lead_platform"] = prompt

	state["messages"].append(HumanMessage(content=prompt))
	state = graph.invoke(state)
	st.session_state["agent_state"] = state

	reply = get_last_ai_message(state)
	if reply:
		with st.chat_message("assistant"):
			st.write(reply)

if state.get("lead_captured"):
	st.success("Lead captured successfully.")
