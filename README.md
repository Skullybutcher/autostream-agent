## Setup

1. Clone the repository and move into the project directory:
   ```bash
   git clone <your-repo-url>
   cd autostream-agent
   ```
2. Create and activate a Python 3.9+ virtual environment.
3. Create a `.env` file in the project root:
   ```env
   GROQ_API_KEY=your_key_here
   ```
4. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
5. Run the agent:
   ```bash
   python agent.py
   ```
6. Run the Streamlit app:
   ```bash
   streamlit run app.py
   ```

## Architecture

This project uses LangGraph because it gives an explicit state-machine structure for conversational flows. Instead of hiding control flow behind generic agent abstractions, each step is modeled as a node and each transition is modeled as an edge. That makes branching behavior predictable, easy to debug, and straightforward to extend. Conditional edges are used to route by intent and to decide when the lead-capture tool should run.

State is defined with a TypedDict (`AgentState`) so every node reads and writes the same schema. Message history uses the `add_messages` reducer, which appends new messages instead of replacing prior turns. Other fields such as `intent`, `lead_name`, `lead_email`, `lead_platform`, and `lead_captured` are overwritten as the conversation progresses. This keeps memory behavior explicit: history grows, while slot-like fields track the latest known values.

On each user turn, the flow starts with intent detection. If intent is greeting or product inquiry, the graph routes to the RAG node, which answers using only `knowledge.json`. If intent is high intent, the graph routes to lead collection, prompting for name, email, and platform in order. Once all three are present, the tool execution node calls `mock_lead_capture` and confirms completion.

## WhatsApp Integration via Webhooks (Possible Real-World implementation)

To connect this agent to WhatsApp, use the Twilio WhatsApp Sandbox and expose a FastAPI webhook endpoint. Twilio sends each inbound message as a webhook payload containing `Body` (message text) and `From` (sender identifier). Keep per-user conversation state in memory using a dictionary keyed by phone number (`From`) so each user has an independent LangGraph state. For each webhook call, load or initialize the user state, append the new `HumanMessage`, invoke the graph, store updated state, and return the agent reply. In production, replace in-memory state with persistent storage and return TwiML XML to Twilio.

```python
from fastapi import FastAPI, Form
app = FastAPI()
user_states = {}

@app.post("/webhook")
async def webhook(Body: str = Form(), From: str = Form()):
    state = user_states.get(From, initial_state())
    state["messages"].append(HumanMessage(content=Body))
    state = graph.invoke(state)
    user_states[From] = state
    reply = get_last_ai_message(state)
    return {"message": reply}
```

## Demo conversation

```text
You: Hi, tell me about your pricing.
Agent: [retrieves from knowledge.json, explains Basic $29 and Pro $79 plans]

You: That sounds good, I want to try the Pro plan for my YouTube channel.
Agent: [detects high_intent] Great! I'd love to get you started. Could you share your name?

You: Alex Johnson
Agent: Thanks Alex! What's your email address?

You: alex@example.com
Agent: Perfect! Which platform do you create content on?

You: YouTube
Agent: ✅ You're all set, Alex! We'll reach out to alex@example.com shortly. Welcome to AutoStream!

[Console prints: Lead captured successfully: Alex Johnson, alex@example.com, YouTube]
```
