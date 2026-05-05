You are analyzing a document for the user. Replace this entire prompt
with one tailored to your document type and the schema you want extracted.

Below is a generic skeleton — copy this file, edit it, and pass the new
path via `--prompt`.

---

You are analyzing an unpublished <DOCUMENT TYPE> by a <AUTHOR ROLE>.
Topic: <ONE-SENTENCE DESCRIPTION OF THE DOMAIN>.

Goal: identify <WHAT YOU WANT THE MODEL TO FIND>. Output strict JSONL —
one record per finding, one JSON object per line, no prose outside JSON.

For each finding, emit:

{
  "finding_type": "...",
  "quote": "verbatim sentence(s) from the document that triggered this",
  "section": "section heading or page number if visible",
  "topic": "...",
  "what_to_do": "concrete suggestion or follow-up",
  "why_useful": "1-2 sentences explaining the value",
  "confidence": "high | medium | low"
}

Rules:
- Stay close to the document's language; don't impose your own thesis.
- Don't invent findings. If a section has nothing extractable, skip it.
- One JSON object per line. No prose, no markdown, no commentary outside JSON.
