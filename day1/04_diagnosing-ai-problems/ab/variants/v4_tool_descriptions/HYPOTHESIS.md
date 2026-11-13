H4 (tool surface): the coordinator's decision tools are described in 3-5 words ('Spawns a specialist agent', 'Writes the response.', 'Escalates to a human.'), so nothing tells the model a specialist only acts in its own category, or what each resolution_status means.
Change: coordinator-tools.json descriptions for spawn_specialist / write_response / escalate_to_human only. Prompt left as shipped (which still says ONE specialist).
Predicts: tells us whether tool docs alone can beat a contradictory prompt rule. Likely small movement.
