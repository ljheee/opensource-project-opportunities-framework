# Stage 3: Semantic Filtering for AI Projects

You are an AI project classifier. Process the pending projects below.

## Classification Categories

**Tech Layer (choose one):**
- foundation_model: Base LLMs, multimodal models
- training_framework: Distributed training, fine-tuning
- inference_engine: Model serving, optimization, quantization
- ai_application: End-user AI applications
- ai_toolchain: Data processing, evaluation, deployment tools

**Application (choose one):**
- code_generation
- image_generation
- multimodal
- agent
- data_annotation
- model_evaluation

## Filtering Rules

SKIP (status='filtered_skip') if ANY apply:
1. Name/description contains: awesome, tutorial, demo, examples, course, curated-list
2. No clear AI/ML focus (not LLM, not generative AI, not ML framework)
3. Empty repository or just documentation
4. Commercial product SDK only (no open-source core)

KEEP (status='scheduled') if ALL apply:
1. Clear AI focus
2. Active code repository
3. Solves a real problem

## Database Operations

For each project, execute SQL:

-- SKIP
UPDATE projects
SET status='filtered_skip', filter_reason='<reason>'
WHERE id='<project_id>';

-- KEEP
UPDATE projects
SET status='scheduled', tech_layer='<layer>', application='<app>'
WHERE id='<project_id>';

Use Python sqlite3. Commit after each project.

## Input

SELECT * FROM projects WHERE status='discovered' LIMIT 50
