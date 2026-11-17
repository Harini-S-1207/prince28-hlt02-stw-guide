
# STW Guide – Evaluation Questions

These questions are used to evaluate the STW Guide chatbot's ability to retrieve information from ICMR Standard Treatment Workflows.

## Answerable Questions

1. What are the red flags mentioned in the ICMR Standard Treatment Workflow for Hypertension in Adults?

2. How should blood pressure be measured and confirmed according to the workflow?

3. What lifestyle modifications are recommended for adults with hypertension?

4. What investigations are recommended for patients with hypertension?

5. What symptoms may indicate target-organ damage in a patient with severe hypertension?

## Unanswerable Question

6. What is the exact medication dosage for a pregnant patient with hypertension?

Expected behaviour: The system must state that this information is not available in the currently indexed STW source. It must not invent a dosage.

## Additional Retrieval Questions

7. When is one clinic visit sufficient to confirm hypertension according to the workflow?

8. What blood pressure level, together with symptoms of target-organ damage, requires emergency referral?

9. What does the workflow recommend regarding salt intake and daily physical activity?

10. What is the appropriate level of care for a patient with hypertension who requires emergency referral?

## Evaluation Criteria

- Answers must be grounded in the available ICMR workflow.
- The system must identify the relevant source.
- The system must not invent clinical information.
- Unsupported questions must receive an explicit limitation response.
