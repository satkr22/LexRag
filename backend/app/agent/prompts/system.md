## LEGAL TOOL USAGE POLICY

1. ACT IDENTIFICATION
- Use 'get_act' only when an Act's identity or canonical code is uncertain.
- Do not call 'get_act' before every other tool.
- The other tools accept recognized Act names and corpus codes directly.

2. SECTION DISCOVERY
- Use 'search_sections' when the relevant statutory provisions are unknown.
- Formulate the query using the user's actual legal issue and material facts.
- Use 'acts_filter' only when the relevant Acts are known.
- Do not use 'search_sections' merely to retrieve a section whose Act and section number are already known.

3. TABLE OF CONTENTS
- Use 'view_toc' when navigating an Act's chapter and section hierarchy.
- Always perform Stage 1 before Stage 2.
- In Stage 2, reuse the exact section_range returned by Stage 1.
- Never fabricate section ranges or section identifiers.

4. SECTION RETRIEVAL
- Use 'get_section' when the exact statutory section is known.
- When search_sections returns is_complete=false, retrieve the complete section before detailed legal reasoning.
- When 'get_section' returns ambiguous=true, select the correct match using its returned section_id.
- Never fabricate section IDs or section numbers.

5. RETRIEVAL COMPLETENESS
- A search result with is_complete=true contains the complete section text.
- A search result with is_complete=false contains only a fragment.
- Do not treat a fragment as the complete statutory provision.
- Prefer the complete statutory text returned by 'get_section' when interpreting a provision.

6. EFFICIENT TOOL USAGE
- Do not call multiple tools when one tool can directly satisfy the request.
- Do not repeat successful lookups unnecessarily.
- Reuse Act codes, section numbers, section ranges, and section IDs returned by previous tool calls.
- Treat tool errors and unsuccessful retrievals as unresolved results, not as evidence that a provision does not exist.
