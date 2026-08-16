import json
import os

import anthropic

_client = None


def _build_schema(speakers):
    # Structured outputs requires additionalProperties: false on every
    # object, so the set of allowed speaker keys must be listed explicitly
    # rather than expressed as a dynamic-value additionalProperties schema.
    return {
        "type": "object",
        "properties": {
            "needs_clarification": {
                "type": "boolean",
                "description": (
                    "True if the instruction does not give enough information to "
                    "confidently identify which speaker(s) to adjust (no label, "
                    "ordinal, or distinguishing description at all)."
                ),
            },
            "speaker_rates": {
                "type": "object",
                "description": (
                    "Playback speed multiplier per speaker that should change "
                    "(>1.0 = faster/shorter, <1.0 = slower/longer). Omit any "
                    "speaker whose pace should stay unchanged. Leave empty if "
                    "needs_clarification is true."
                ),
                "properties": {sp: {"type": "number"} for sp in speakers},
                "additionalProperties": False,
            },
            "explanation": {
                "type": "string",
                "description": (
                    "If needs_clarification is true, a short clarifying question "
                    "asking the user to identify the speaker (by label, position, "
                    "or a distinguishing trait). Otherwise, one sentence explaining "
                    "what was changed and why."
                ),
            },
        },
        "required": ["needs_clarification", "speaker_rates", "explanation"],
        "additionalProperties": False,
    }


def get_client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    return _client


def _speaker_summary(segments):
    order = []
    totals = {}
    for seg in segments:
        sp = seg["speaker"]
        if sp not in totals:
            totals[sp] = 0.0
            order.append(sp)
        totals[sp] += seg["end_seconds"] - seg["start_seconds"]

    ordinal = ["first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth"]
    lines = [
        f"{sp}: the {ordinal[i] if i < len(ordinal) else f'{i + 1}th'} speaker to talk, "
        f"speaks for {totals[sp]:.0f}s total across the conversation"
        for i, sp in enumerate(order)
    ]
    return order, "\n".join(lines)


def interpret_instruction(instruction, segments):
    speakers, summary = _speaker_summary(segments)
    client = get_client()
    response = client.messages.create(
        model="claude-opus-4-8",
        max_tokens=1024,
        system=(
            "You adjust the speaking pace of specific speakers in a diarized "
            "conversation based on a user's natural-language request.\n\n"
            f"Speakers in this conversation: {', '.join(speakers)}.\n{summary}\n\n"
            "Map the user's description (by speaker label, order of appearance, "
            "or amount of talk time) to the correct speaker label(s), then choose "
            "a speed multiplier per speaker that should change (>1.0 = faster, "
            "<1.0 = slower). Typical adjustments are in the 0.7-1.4 range unless "
            "the user asks for something more extreme. Only include speakers the "
            "user actually wants changed.\n\n"
            "You only have text metadata about each speaker (order of appearance, "
            "total talk time) — you cannot hear the audio. If the instruction gives "
            "no way to tell which speaker is meant (no label, no ordinal, no "
            "relative description like 'the one who talks less'), do not guess: "
            "set needs_clarification to true, leave speaker_rates empty, and ask a "
            "short clarifying question in explanation."
        ),
        output_config={"format": {"type": "json_schema", "schema": _build_schema(speakers)}},
        messages=[{"role": "user", "content": instruction}],
    )
    text = next(b.text for b in response.content if b.type == "text")
    data = json.loads(text)

    data["speaker_rates"] = {
        sp: max(0.5, min(2.0, float(rate)))
        for sp, rate in (data.get("speaker_rates") or {}).items()
        if sp in speakers
    }
    return data
