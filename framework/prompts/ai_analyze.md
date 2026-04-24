# Stage 4: Deep Analysis of AI Project

You are an AI industry analyst. Analyze this project deeply.

## Project Info

Query: SELECT * FROM projects WHERE id='<project_id>'
Query: SELECT * FROM early_burst_signals WHERE project_id='<id>' ORDER BY calculated_at DESC LIMIT 1

## Analysis Framework

### 1. Problem & Solution
- What specific pain point does this address?
- Target users and use cases
- Painkiller vs vitamin assessment

### 2. Innovation Assessment
- Technical: New architecture, algorithm, training method?
- Product: New interaction pattern, UX innovation?
- Business: New monetization, distribution model?

### 3. Differentiation
- vs OpenAI/Anthropic/Google commercial offerings
- vs other open-source alternatives
- Sustainable moat analysis

### 4. Extension Opportunities

Identify 3-5 opportunities. For each provide:
- opportunity_type: product|tech|market|integration|business_model
- title: One-line description
- description: What to build
- impact_potential: high|medium|low
- difficulty: high|medium|low
- time_horizon: short|medium|long
- key_insight: Why this opportunity exists now

### 5. Market Timing
- Why is this the right time?
- Enabling technological shifts
- Key risks and challenges

### 6. Overall Score
Rate 1-10 based on innovation, market size, execution, team

## Output

Insert into analyses table with all fields.
Insert each opportunity into opportunities table.
