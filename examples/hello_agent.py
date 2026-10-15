"""Day 1: the agent loop, written by hand.

One question, one tool, no framework. The point is to see every step:
  question -> model -> tool_use -> we run the tool -> tool_result -> model -> answer
"""

import json

import anthropic

MODEL = "claude-opus-5-5"

# --- 1. The tool schema: this is what the model sees. It is part of the prompt. ---
TOOLS = [
    {
        "name": "get_station_stats",
        "description": (
            "Return the end-of-line test statistics for one test station: "
            "number of tested units, failure rate in percent and the dominant failure code."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "station": {"type": "integer", "description": "Station number, 1 to 3"},
            },
            "required": ["station"],
            "additionalProperties": False,
        },
        "strict": True,
    }
]

# --- 2. The tool implementation: plain Python. The model never runs this; we do. ---
FAKE_STATS = {
    1: {"tested": 412, "failure_rate_pct": 1.9, "dominant_failure": "none"},
    2: {"tested": 398, "failure_rate_pct": 8.3, "dominant_failure": "E-204 quiescent current high"},
    3: {"tested": 405, "failure_rate_pct": 2.1, "dominant_failure": "none"},
}


def get_station_stats(station: int) -> str:
    stats = FAKE_STATS.get(station)
    if stats is None:
        return json.dumps({"error": f"station {station} does not exist"})
    return json.dumps(stats)


# --- 3. The loop. ---
def run(question: str) -> str:
    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from the environment
    messages = [{"role": "user", "content": question}]

    while True:
        response = client.messages.create(
            model=MODEL,
            max_tokens=4096,
            system="You are an assistant for electronics test engineers. Answer in German, briefly.",
            tools=TOOLS,
            messages=messages,
        )
        print(f"\n[stop_reason = {response.stop_reason}]")

        # The API is stateless: we must append the assistant turn ourselves.
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason != "tool_use":
            break  # end_turn (or max_tokens / refusal): nothing more to run

        # One or more tool_use blocks: run every one, return every result in ONE user message.
        results = []
        for block in response.content:
            if block.type == "tool_use":
                print(f"[tool call] {block.name}({json.dumps(block.input)})")
                if block.name == "get_station_stats":
                    output = get_station_stats(**block.input)
                else:
                    output = json.dumps({"error": f"unknown tool {block.name}"})
                print(f"[tool result] {output}")
                results.append({"type": "tool_result", "tool_use_id": block.id, "content": output})
        messages.append({"role": "user", "content": results})

    answer = "".join(b.text for b in response.content if b.type == "text")
    usage = response.usage
    print(f"\n[usage] input={usage.input_tokens} output={usage.output_tokens}")
    return answer


if __name__ == "__main__":
    print(run("Welche Station hat heute die höchste Ausfallrate, und was ist der Hauptfehler?"))
