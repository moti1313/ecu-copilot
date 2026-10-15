"""Digital twin of an end-of-line (EOL) test line for door control units.

Not a physics simulation: a stateful data generator that behaves like three real
test stations, including the ways real stations misbehave (temperature drift,
hall noise, a bad component lot). The copilot only ever sees its REST API, so a
real MES / test system can replace it without touching the agent.
"""
