Gemini models policy for Narrato:

Summary:
- Remove all Gemini models except Gemini-2.5-Flash and utilize Gemini-2.5-Flash as the sole model across the AI story generation pipeline.

Rationale:
- Consolidate AI model usage to Gemini-2.5-Flash for consistency, speed, and cost.
- Aligns with product goals of predictable outputs and streamlined dependencies.

What changes with this policy:
- All non-Gemini-2.5-Flash models should not be used in generation, illustration, or analysis tasks.
- Code paths that previously referenced other Gemini models should be refactored to Gemini-2.5-Flash where possible.
- Documentation and onboarding should reflect this policy.

Migration guidance:
- If your modules previously allowed selecting between Gemini models, default to Gemini-2.5-Flash.
- Remove or deprecate references to Gemini variants other than Gemini-2.5-Flash.
- Tests should assert that Gemini-2.5-Flash is the only model used.

Notes:
- This is a policy document; practical implementation changes should be captured in codebase changes where they exist.
