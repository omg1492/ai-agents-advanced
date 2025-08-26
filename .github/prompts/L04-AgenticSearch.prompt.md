Implement another point in plan - agentic search by creating two function calls for LLM to use - semantic (LLM to provide HyDE text) and kewords (LLM to provide kewords for full-text search). Also add attribute for LLM to decide how many top documents to receive (make it choose between 3-10). This functionality should reside in another file in services folder called agentic_search.py

While doing that it should be easy to implement fencing, another point in plan. From JWT we already now whether user is vip or not. While LLM will not have access to this field during using tool, our tool should have this information about authenticated user and add proper WHERE into SQL query. Described in Design documument, WHERE (products.is_vip = false OR :user_is_vip = true)

We must also tune system prompt. Check official prompt guide for GPT 5 #fetch https://cookbook.openai.com/examples/gpt-5/gpt-5_prompting_guide We must introduce those new function calls into system prompt and advice LLM how to use it, stress that it can use both and even multiple times, if results are not as expected. Because we now what tools are enabled in configuration make sure system prompt uses Jinja template to list and describe only tools currently enabled.

Revise grounding information in system promp so we want either RAG or agentic search to be used as grounding for products and their producers, certifications or allergens.

I think we should make reasoning effort configurable via .env and .env.template. Currently we have used minimal, but with more agentic behavior we might want to test other levels so make it part of configuration, not hardcoded.

Be careful about streaming loop - new added tools must not corrupt processing flow and ability to call multiple tools multiple times as LLM wants.

If needed you can lookup internet for other examples and documentation #websearch 