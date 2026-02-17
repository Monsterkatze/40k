# Nährwert-JPG Generator – APM Memory Root
**Memory Strategy:** Dynamic-MD
**Project Overview:** One-off local Python CLI pipeline for ~40k products: robust CSV ingestion, nutrition text classification/parsing/validation, 1200x1200 nutrition JPG rendering for valid cases, plus operational reporting with dedicated NEEDS_REVIEW and FAILED exports.

## Phase 01 – Audit & Foundations Summary
- Outcome summary: Phase 1 established a working CLI foundation, robust CSV ingestion with encoding fallback and tolerant header mapping, deterministic classification with diagnostics, and an initial audit baseline. The baseline is reproducible but currently skewed to `NUTRITION` due to limited fixture diversity, which is now a known constraint for subsequent parser-optimization confidence.
- Involved Agents: Agent_Ingestion, Agent_Classification
- Memory Logs:
	- `.apm/Memory/Phase_01_Audit_Foundations/Task_1_1_CLI_Scaffold_Runtime_Config.md`
	- `.apm/Memory/Phase_01_Audit_Foundations/Task_1_2_CSV_Ingestion_Encoding_Robustness.md`
	- `.apm/Memory/Phase_01_Audit_Foundations/Task_1_3_Cell_Classification_Engine.md`
	- `.apm/Memory/Phase_01_Audit_Foundations/Task_1_4_Audit_Report_Baseline_Metrics.md`

## Phase 02 – Parsing & Validation Summary
- Outcome summary: Phase 2 delivered deterministic normalization, extraction, validation, and reporting outputs integrated into runtime artifacts. The pipeline now emits parser-ready text, structured nutrition fields, validation/status metadata, and operational CSV exports (`report.csv`, `needs_review.csv`, `failed.csv`) with stable summary logging. These outputs establish an auditable baseline for rendering and later optimization.
- Involved Agents: Agent_Parsing, Agent_Validation
- Memory Logs:
	- `.apm/Memory/Phase_02_Parsing_Validation/Task_2_1_Text_Normalization_Pipeline.md`
	- `.apm/Memory/Phase_02_Parsing_Validation/Task_2_2_Nutrition_Field_Extraction_Parser.md`
	- `.apm/Memory/Phase_02_Parsing_Validation/Task_2_3_Validation_Product_Status_Assignment.md`
	- `.apm/Memory/Phase_02_Parsing_Validation/Task_2_4_Reporting_Core_Split_Review_Exports.md`

## Phase 03 – Rendering & Batch Execution Summary
- Outcome summary: Phase 3 completed deterministic JPG rendering and batch execution hardening. The pipeline now includes a reusable Pillow renderer (`1200x1200`), sharded output paths with resume skip behavior, worker-based parallel rendering, and one-command end-to-end orchestration with explicit stage-boundary logs and consolidated completion metrics.
- Involved Agents: Agent_Rendering, Agent_Runtime
- Memory Logs:
	- `.apm/Memory/Phase_03_Rendering_Batch_Execution/Task_3_1_Nutrition_JPG_Renderer_1200x1200.md`
	- `.apm/Memory/Phase_03_Rendering_Batch_Execution/Task_3_2_Output_Sharding_Resume_Skip_Worker_Pipeline.md`
	- `.apm/Memory/Phase_03_Rendering_Batch_Execution/Task_3_3_End_to_End_Run_Command_Operational_Logging.md`

## Phase 04 – Optimization & Acceptance Summary
- Outcome summary: Phase 4 delivered prioritized rule tuning with verified improvements and updated observability semantics. `NEEDS_REVIEW` load for sparse-but-valid profiles was reduced via minimal-profile split logic, `kcal` warning noise was removed, and ingestion rejects are now surfaced in `FAILED` reporting without destabilizing ingestion. Acceptance review completed deterministically with proportional reporting due to limited eligible pool (2/2 manually correct), while explicitly separating parser/model quality from ingestion-reject `FAILED` visibility.
- Involved Agents: Agent_Optimization
- Memory Logs:
	- `.apm/Memory/Phase_04_Optimization_Acceptance/Task_4_1_Failure_Pattern_Analysis.md`
	- `.apm/Memory/Phase_04_Optimization_Acceptance/Task_4_2_Rule_Tuning_Loop_Controlled_Rerun.md`
	- `.apm/Memory/Phase_04_Optimization_Acceptance/Task_4_3_Acceptance_Check_Final_Handover.md`
