# Lesson 5 Plan – Memory & Voice (Simplified)

High-level steps only – aligned with unified design. Each step considered complete when minimal working implementation + basic test exists.

- [x] Create `conversations_raw` table (SQL script) and indexes (user_id, expires_at)
- [ ] Implement storing conversations (user & assistant turns) in agent backend
- [ ] Expose & build UI to list and view prior conversations (basic pagination)
- [ ] Create `conversation_summaries` table (summary + embedding)
- [ ] Batch script to convert raw conversations → summaries (title, summary, embedding, status updates)
- [ ] Add memory search tool (user‑fenced semantic similarity over summaries) and register with LLM
- [ ] Create `user_profiles` table (jsonb profile)
- [ ] Batch script to enrich/update user profile from raw + summaries
- [ ] Inject current user profile block into system prompt
- [ ] Tool to append/add new profile info directly (`memory_write_profile` style)
- [ ] Implement voice mode (button in UI → speech‑to‑speech via gpt-realtime)
- [ ] Persist a text transcript of voice conversation (store like normal turns, mode=voice)
- [ ] Decide which tools are enabled in voice mode (baseline: memory_search allowed, heavy graph tools off unless flagged)

Deferred / Optional Later:
- WebRTC direct integration
- Continuous streaming audio tokens
- Profile PII redaction

End.
