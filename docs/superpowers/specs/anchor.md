# Anchor Discovery — 锚点反向发现机制

## 本质

锚点不是"搜索目标"，而是**搜索参照物**。

标准 topics 搜索是"按标签找项目"；锚点发现是"按已知的重要项目/协议/概念，反向搜它的新实现或变体"。

锚点的核心假设：一个领域内的创新，往往以**已有知名项目/概念为参照**进行自我定位。新项目会在 name/description 中提及这些参照物，以快速建立认知关联。锚点发现就是捕获这些**"站在巨人肩膀上"的初期项目**。

## 与 Topics 搜索的差异

| | Topics 搜索 | 锚点发现 |
|---|---|---|
| 搜索维度 | `topic:llm language:Rust` | `uniswap in:name,description language:Rust` |
| 发现逻辑 | 等项目自己打标签 | 等项目主动提及参照物 |
| 覆盖范围 | 已归类项目（90%+） | 未归类或新范式项目（补充 5~10%） |
| 时效性 | 标签更新滞后 | name/description 第一时间体现 |
| 噪声 | 低（标签是主动归类） | 中（需过滤同名、fork、教程） |

## 锚点的三层设计

### 第一层：协议/标准层锚点
领域内的**底层协议、技术标准、核心概念**。这些是最高稳定性的锚点，变化极慢。

- AI: `transformer`, `attention`, `diffusion`, `rag`
- 区块链: `evm`, `zk-rollup`, `ibc`, `erc-4337`
- 中间件: `raft`, `paxos`, `consensus`, `distributed-transaction`

### 第二层：知名项目层锚点
领域内的**标志性开源项目**。这些是中等稳定性的锚点，每隔 1~2 年更新一次即可。

- AI: `langchain`, `llamaindex`, `stable-diffusion`, `ollama`
- 区块链: `uniswap`, `aave`, `chainlink`, `arbitrum`
- 中间件: `redis`, `kafka`, `etcd`, `consul`

### 第三层：应用场景层锚点
领域内的**热门应用场景**。这些变化最快，需要按季度审视。

- AI: `code-generation`, `image-generation`, `voice-clone`, `ai-agent`
- 区块链: `defi`, `nft-marketplace`, `dao-governance`, `cross-chain-bridge`
- 中间件: `service-mesh`, `rate-limiting`, `circuit-breaker`

**设计原则**：每层锚点的**keywords 应该互相独立**，避免同一搜索命中多个锚点造成重复。例如 `uniswap` 和 `amm` 可以分属第二层和第三层，但不应同时出现在同一层的不同锚点中。

## 搜索执行逻辑

```python
for anchor in anchors:
    for kw in anchor['keywords']:
        for lang in config['sources']['github']['languages']:
            query = f"{kw} in:name,description language:{lang} stars:{min}..{max}"
            repos = gh_search(query, per_page=10)
```

参数说明：
- `in:name,description`：限定只在项目名称和描述中匹配，避免在 README 正文中的大量误匹配
- `per_page=10`：每个组合最多取 10 个，控制总量；锚点发现的目的是"补充覆盖"，不是"全面扫描"
- `stars:min..max`：过滤掉过于成熟的项目（通常已在前几步被 topics 搜索覆盖）

## 按类别配置的示例

### AI 类别

```yaml
anchors:
  # 协议/标准层
  - name: "RAG"
    keywords: ["rag", "retrieval-augmented", "knowledge-base", "vector-search"]
  - name: "Agent"
    keywords: ["agent", "autonomous", "multi-agent", "swarm", "tool-use"]
  - name: "Diffusion"
    keywords: ["diffusion", "stable-diffusion", "latent-diffusion", "flow-matching"]

  # 知名项目层
  - name: "LangChain"
    keywords: ["langchain", "langgraph", "langserve"]
  - name: "Ollama"
    keywords: ["ollama", "local-llm", "gguf"]
  - name: "Transformers"
    keywords: ["huggingface", "transformers", "peft", "trl"]

  # 应用场景层
  - name: "Code Generation"
    keywords: ["code-generation", "copilot", "code-llm", "code-completion"]
  - name: "Voice AI"
    keywords: ["tts", "text-to-speech", "voice-clone", "speech-synthesis"]
```

### 区块链类别

```yaml
anchors:
  # 协议/标准层
  - name: "Zero-Knowledge"
    keywords: ["zero-knowledge", "zk-snark", "zk-stark", "circom"]
  - name: "Account Abstraction"
    keywords: ["account-abstraction", "erc-4337", "smart-wallet", "paymaster"]

  # 知名项目层
  - name: "Uniswap"
    keywords: ["uniswap", "amm", "v4-hook", "concentrated-liquidity"]
  - name: "Chainlink"
    keywords: ["chainlink", "oracle", "price-feed", "ccip"]

  # 应用场景层
  - name: "Restaking"
    keywords: ["restaking", "eigenlayer", "avs", "liquid-restaking"]
  - name: "Intent"
    keywords: ["intent", "intent-centric", "solver", "account-abstraction"]
```

## 维护策略

1. **协议/标准层**：年更新。只有领域底层范式变化时才调整（如 AI 领域从 Transformer 到 Mamba）
2. **知名项目层**：半年审视。移除已衰落的项目，补充新兴标杆
3. **应用场景层**：季度审视。紧跟行业热点轮动（如 2023 的 NFT → 2024 的 Restaking → 2025 的 AI Agent）

## 常见陷阱

1. **关键词过宽**：`blockchain` 作为关键词会命中几乎所有项目，失去锚点意义。锚点关键词应该是**具体项目名或技术术语**，而非领域泛词
2. **锚点与 topics 重叠**：如果某关键词已经被设为 `topic:`（如 `topic:defi`），则不应再作为锚点关键词，避免重复搜索
3. **语言限制过严**：某些协议实现可能是多语言的（如 ZK 电路用 Circom，prover 用 Rust），应在 keywords 层面而非 language 层面区分
