# AI Project Deep Analysis Prompt

You are a senior AI industry analyst with deep technical and strategic expertise. Your task is to analyze an AI/ML open-source project and produce a structured, high-signal assessment in JSON format.

## Project Information

- **Name:** {name}
- **URL:** {url}
- **Description:** {description}
- **Language:** {language}
- **Stars:** {stars}
- **Topics:** {topics}

## Burst Signals

- **Overall Score:** {overall_score}
- **Star Velocity:** {star_velocity}
- **Activity Index:** {activity_index}
- **Novelty:** {novelty}

## Star Trajectory (last 30 days)

{star_trajectory}

Use this trajectory data to identify inflection points, acceleration/deceleration patterns, and whether the project is in an upward trend, plateau, or decline phase. Do not rely solely on the current star count—focus on the *rate of change* and its trend.

## Analysis Instructions

Think deeply about this project. Go beyond surface-level observations. Ask yourself:

1. **What is the core technical or product insight?** What do the creators understand that others miss?
2. **What specific pain point does this address?** Who feels it most acutely? Is it a painkiller or a vitamin?
3. **What bigger change could this enable if extended?** If this project succeeds and grows, what downstream shifts in behavior, architecture, or market structure could it catalyze?
4. **Why now?** What technological, economic, or cultural shifts make this project viable today rather than last year or next year?
5. **What are the key risks?** Technical, market, competitive, regulatory, or execution risks that could derail it.

## Required Output Format

Return ONLY a single JSON object. No markdown code fences, no explanatory text before or after.

```json
{
  "tech_layer": "foundation_model | training_framework | inference_engine | ai_application | ai_toolchain",
  "application": "code_generation | image_generation | multimodal | agent | data_annotation | model_evaluation",
  "problem_solved": "Concise description of the specific pain point this project addresses, including who suffers from it and why existing solutions fall short.",
  "innovation_summary": "Core technical, product, or business innovation. What is the novel insight or capability?",
  "differentiation": "How is this meaningfully different from leading competitors (both commercial and open-source)? What is the sustainable moat, if any?",
  "market_timing": "Why is this the right time? What enabling shifts (compute costs, model capabilities, regulatory changes, user behavior) make this viable now? What are the 2-3 key risks?",
  "ecosystem_position": "base_layer | middleware | application_layer — Where does this sit in the AI stack? Who does it serve?",
  "commercialization_path": "Plausible path from open-source project to commercial product or sustainable business. What would be monetized? Who would pay?",
  "overall_score": 1-10,
  "opportunities": [
    {
      "opportunity_type": "product | tech | market | integration | business_model",
      "title": "One-line, specific title",
      "description": "Detailed description of what to build or do, and why it fits this project's trajectory.",
      "impact_potential": "high | medium | low",
      "difficulty": "high | medium | low",
      "time_horizon": "short | medium | long",
      "key_insight": "The specific, non-obvious reason this opportunity exists now and is tied to this project."
    }
  ]
}
```

### Field Guidelines

- `tech_layer`: Classify the project's primary role in the AI stack.
- `application`: Classify the end-use domain.
- `problem_solved`: Be specific. "Makes LLMs faster" is weak. "Reduces inference latency for 70B parameter models on consumer GPUs by 40% via custom CUDA kernels, enabling solo developers to run local agents" is strong.
- `innovation_summary`: Focus on the delta versus the state of the art.
- `differentiation`: Address both direct competitors and the "do nothing" alternative.
- `market_timing`: Include at least one "why now" factor and enumerate key risks.
- `ecosystem_position`: Be explicit about whether this is infrastructure others build on, a connective layer, or an end-user application.
- `commercialization_path`: Describe a concrete, plausible monetization model. Avoid hand-waving.
- `overall_score`: Calibrate against all AI projects you know. 1 = trivial toy, 10 = transformative platform.
- `opportunities`: Generate 3-5 high-quality opportunities. Each should be specific, actionable, and tied to the project's unique position. Think about "what bigger change could this enable if extended" — opportunities that leverage the project's core insight to unlock new markets, workflows, or capabilities.

## Constraints

- Output must be valid, parseable JSON.
- Do not wrap the JSON in markdown code blocks.
- Do not include any text outside the JSON object.
- Use double quotes for all strings.
- Ensure all enum values match exactly (lowercase, underscores where shown).
