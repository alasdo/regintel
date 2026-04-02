# Impact Prompt Iteration: Removed Section Handling

## Original failure mode
For Part 820 removed sections, the model often stated that requirements were "eliminated" when the text only showed that the CFR section was removed. This was misleading because Part 820 was revised in the QSR-to-QMSR transition, and some requirements may have been relocated or incorporated through ISO 13485 rather than removed entirely.

## Prompt fix
Added an explicit instruction that removed sections should not be assumed to eliminate underlying requirements. The prompt now tells the model to state that the section was removed, note that obligations may have been relocated or replaced, recommend verification, and lower confidence unless the provided context clearly shows what replaced the requirement.

Also added a rule to avoid listing generic affected processes such as change_control and document_control unless the change directly affects those requirements.

## Observed improvement
After the prompt update, removed-section analyses became more cautious and intellectually honest. The model was less likely to state that requirements were eliminated and more likely to frame the change as removal from the CFR text pending confirmation of relocation or replacement. Affected process lists also became more specific and less repetitive.