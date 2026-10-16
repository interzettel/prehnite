# Offline crash and billing safety matrix

This is a **fake provider** test harness, not proof about fal.ai or Anthropic billing.

| Kill point | Last durable stage state | Provider ID known? | Safe automatic action |
|---|---|---:|---|
| Before calling provider | submitting | No | Stop and reconcile; never blindly replay |
| Provider submission before ID callback | submitting | No | Stop and reconcile; no second submit |
| Immediately after ID journal commit | submitted | Yes | Resume retrieval using the same ID |
| After output bytes, before completion commit | submitted | Yes | Resume retrieval from the same ID |
| Worker dies holding lock | Kernel lock released | N/A | Next runner may acquire batch lock |
| Two workers race for same batch | One owns the lock | N/A | Refuse the second runner |

The tests in tests/test_crash_matrix.py start an independent Python interpreter,
intentionally crash it using os._exit() at each fault point, open the SQLite journal,
and assert persisted state and cost reservation. A live subprocess is also killed
while holding the OS batch lock; the parent proves that the lock becomes available.

**Important limitation:** Submitting is persisted before provider dispatch, so a
lost request ID is ambiguous even when the remote call was never made. The safe
default is refusal and manual/provider reconciliation, not repeating a possible
billable call. The 90-image Windows test and actual provider billing audit are
separate gated issues (#17, #24 and #42). This costs $0 actual inference.
