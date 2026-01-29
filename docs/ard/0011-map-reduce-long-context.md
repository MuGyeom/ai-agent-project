# 11. Map-Reduce Pattern for Long Context

* Status: Accepted
* Date: 2026-01-29
* Context: Phase 3 (AI Worker Enhancement)

## Context and Problem Statement

검색 결과가 많거나 각 결과가 긴 경우 토큰 제한 문제가 발생했습니다:

1. **토큰 초과 에러**: `Input prompt (29580 tokens) is too long and exceeds limit of 6144`
2. **정보 손실**: 단순 truncation은 중요 정보 손실 가능
3. **메모리 부족**: 긴 컨텍스트는 GPU 메모리 부담

**필요사항**:
- 토큰 제한 내에서 모든 검색 결과 처리
- 정보 손실 최소화
- 확장 가능한 솔루션

## Decision Drivers

* **정보 보존**: 모든 검색 결과 활용
* **토큰 효율**: 제한 내에서 최대 정보 추출
* **품질**: 요약 품질 유지
* **확장성**: 검색 결과 수 증가에도 대응

## Considered Options

### Option 1: Simple Truncation
**Pros**: 간단함
**Cons**: 정보 손실

### Option 2: Map-Reduce Pattern ✅
**Pros**: 모든 정보 활용, 확장 가능
**Cons**: 추가 LLM 호출 필요

### Option 3: Stuffing with Compression
**Pros**: 단일 호출
**Cons**: 압축 시 정보 손실

## Decision Outcome

**Map-Reduce 패턴**을 적용하여 긴 컨텍스트를 처리합니다.

---

## Implementation Details

### Architecture

```
검색 결과 (N개)
      │
      ▼
┌─────────────────────────────────────────┐
│  토큰 수 계산                            │
│  total_tokens = tokenizer.encode(...)   │
└─────────────────────────────────────────┘
      │
      ├─── 제한 내 ───▶ 직접 분석 (Strategy A)
      │
      └─── 제한 초과 ──▶ Map-Reduce (Strategy B)
                              │
                    ┌─────────┴─────────┐
                    ▼                   ▼
              ┌─────────┐         ┌─────────┐
              │ Chunk 1 │   ...   │ Chunk N │
              └────┬────┘         └────┬────┘
                   │                   │
                   ▼                   ▼
              ┌─────────┐         ┌─────────┐
              │Summary 1│   ...   │Summary N│  ◀── Map Phase
              └────┬────┘         └────┬────┘
                   │                   │
                   └─────────┬─────────┘
                             ▼
                    ┌─────────────────┐
                    │  Final Summary  │  ◀── Reduce Phase
                    └─────────────────┘
```

### Key Code

```python
# src/ai_worker/main.py

# 1. Initialize Tokenizer & Calculate Tokens
tokenizer = llm.get_tokenizer()
RESERVED_TOKENS = 1800  # System prompt + output buffer
MAX_CONTEXT_TOKENS = MAX_MODEL_LEN - RESERVED_TOKENS

full_context_str = "\n---\n".join(content_items)
total_tokens = len(tokenizer.encode(full_context_str))

# 2. Strategy Selection
if total_tokens <= MAX_CONTEXT_TOKENS:
    # STRATEGY A: Direct Analysis
    final_context = full_context_str
else:
    # STRATEGY B: Map-Reduce
    MAP_CHUNK_SIZE = 3000  # tokens per chunk
    
    # [Map Phase] Split into chunks and summarize
    chunks = []
    current_chunk, current_tokens = [], 0
    
    for item in content_items:
        item_tokens = len(tokenizer.encode(item))
        if current_tokens + item_tokens > MAP_CHUNK_SIZE:
            chunks.append("\n---\n".join(current_chunk))
            current_chunk, current_tokens = [item], item_tokens
        else:
            current_chunk.append(item)
            current_tokens += item_tokens
    if current_chunk:
        chunks.append("\n---\n".join(current_chunk))
    
    # Batch inference for all chunks
    map_prompts = [build_map_prompt(chunk, topic) for chunk in chunks]
    map_outputs = llm.generate(map_prompts, SamplingParams(temperature=0.7, max_tokens=1024))
    
    intermediate_summaries = [output.outputs[0].text.strip() for output in map_outputs]
    
    # [Reduce Phase] Combine summaries
    final_context = "\n\n---\n\n".join(
        [f"Summary Part {i+1}:\n{s}" for i, s in enumerate(intermediate_summaries)]
    )
```

---

## Performance

| 시나리오 | 토큰 수 | 전략 | 추가 호출 |
|----------|---------|------|----------|
| 짧은 결과 | <4000 | Direct | 0 |
| 중간 결과 | 4000-8000 | Direct | 0 |
| 긴 결과 | 8000-20000 | Map-Reduce | 2-4 |
| 매우 긴 결과 | 20000+ | Map-Reduce | 5+ |

---

## Consequences

### Positive

1. ✅ **토큰 제한 해결**: 어떤 길이의 입력도 처리 가능
2. ✅ **정보 보존**: 모든 검색 결과 활용
3. ✅ **병렬 처리**: vLLM batch inference로 Map 단계 병렬화
4. ✅ **적응적**: 짧은 입력은 추가 호출 없이 처리

### Negative

1. ❌ **추가 지연**: Map-Reduce 시 2단계 추론 필요
2. ❌ **요약 품질 의존**: 중간 요약 품질이 최종 결과 영향

---

## Example Output

```
📚 Found 8 search results
📊 Total Context Tokens: 15234 (Limit: 6294)
⚠️  Context exceeds limit. Triggering Map-Reduce...
🧩 Split into 4 chunks for parallel summarization.
🚀 Running batch inference for 4 chunks...
🔗 Combining intermediate summaries...
📉 Reduced Context Tokens: 2841
🧠 Analyzing with vLLM (Final Pass)...
✅ Analysis completed in 3456ms (Total)
```

---

## References

- [LangChain Map-Reduce](https://python.langchain.com/docs/tutorials/summarization/#map-reduce)
- [vLLM Batch Inference](https://docs.vllm.ai/en/latest/getting_started/quickstart.html)
