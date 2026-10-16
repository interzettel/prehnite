# ComfyUI queue and failure recovery

Prehnite uses only a **user-owned local ComfyUI process**, API-format
workflow JSON and the documented loopback `/prompt`, `/history/{prompt_id}`
and `/view` endpoints. This adapter does not install ComfyUI or include
checkpoints. [ComfyUI server source](https://github.com/Comfy-Org/ComfyUI/blob/master/server.py)
describes both server-generated and client-supplied UUID prompt IDs.

## Recovering a crashed or disconnected runner

1. Before sending the local `POST /prompt`, Prehnite generates an opaque
   UUID and persists it to the batch journal. The request supplies that ID
   to ComfyUI, so a dropped HTTP response cannot force an accidental retry.
2. After a restart, the stage calls only `GET /history/{prompt_id}` using
   the persisted ID. **It never posts the graph a second time** or reuploads
   an existing local image.
3. A temporarily absent history entry remains pending; this is not proof
   that the request never reached the queue. A timeout leaves the ID
   available for future recovery.
4. ComfyUI terminal `error`, `failed`, `interrupted`, `cancelled`,
   `canceled` and `aborted` statuses raise an error. They do not trigger
   blind retries.
5. Only one saved `output` image is accepted. Workflows with multiple
   image-producing nodes may set `options.output_node` to the explicit
   node ID. Wrong/missing nodes, path traversal, unexpected file types,
   invalid images and oversized downloads fail closed.

Download happens through a bounded byte stream to a sibling temporary
file. The image is decoded and checked before atomic promotion to its
stable filename. Existing output files stay intact if retrieval fails.

## Example endpoint settings

```yaml
generation:
  provider: comfyui
  model: owner-supplied-graph
  options:
    workflow: generate_api.json
    prompt_node: "6"
    seed_node: "3"
    size_node: "5"
    output_node: "42"
    timeout_seconds: 1200
    base_url: http://127.0.0.1:8188
```

`PREHNITE_WORKFLOWS` points to the directory containing JSON exports.
A resume with a previously persisted prompt ID does not need the original
workflow file to be present just to fetch its result. However a first
submission requires the file and correct node mappings.

## Boundaries and unresolved questions

- **Lost history:** If ComfyUI loses a prompt after restart/history clear,
  its already-used UUID remains ambiguous. Prehnite will not auto-submit
  another task under a different ID. Start a new explicitly authorized
  attempt only after examining queue/history and batch costs.
- **Compatibility:** The local history API is used because it remains in
  current ComfyUI server code. Newer job-oriented endpoints exist; their
  cross-version behavior still requires live conformance checks.
- **No GPU verification:** Tests use an in-memory `httpx.MockTransport`
  and deterministic Pillow images. They prove the client's protocol and
  filesystem behavior, not runtime checkpoint compatibility, VRAM use,
  visual quality, Windows process behavior or true ComfyUI cancellation.
- **Execution cancellation:** This work classifies statuses; it does *not*
  add a user-facing cancel button or invoke ComfyUI `/interrupt`/`/queue`
  deletion. Safe agent-initiated cancellation remains issue #38.

[Mocked queue tests](../tests/test_comfy_recovery.py) |
[Workflow fixtures](../tests/fixtures/comfy) |
[Local model benchmark issue #24](https://github.com/interzettel/prehnite/issues/24).
