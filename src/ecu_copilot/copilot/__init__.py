"""The agent: Claude + five tools, wrapped in a FastAPI service with tracing, cost
logging, guardrails and a small dashboard.

Why no agent framework: the loop is ~40 lines (see hello_agent.py) and the SDK's
tool runner does it for us. Every line here can be read, explained and debugged.
"""
