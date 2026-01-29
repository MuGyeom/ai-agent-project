import os
from datetime import datetime
import time as time_module

# CRITICAL: Force v0 API - Must set env var BEFORE importing vLLM!
# vLLM decides v0/v1 at import time, so this must be set before import
os.environ["VLLM_USE_V1"] = "0"
print("🔒 Forced VLLM_USE_V1=0 (before vLLM import)")

from vllm import LLM, SamplingParams
from sqlalchemy import text
from common.config import settings
from common.utils import KafkaConsumerWrapper
from common.database import SessionLocal, Request, AnalysisResult, SearchResult
from common.ai_worker_utils import get_gpu_memory_gb, select_model_by_vram


# Initialize vLLM model (Global - only once at program start)
print("🔧 Initializing vLLM Engine...")

# Check if model is specified via environment variable
env_model = os.getenv("VLLM_MODEL")

if env_model:
    # Use explicitly specified model
    MODEL_NAME = env_model
    QUANTIZATION = os.getenv("VLLM_QUANTIZATION", "awq")
    MAX_MODEL_LEN = int(os.getenv("VLLM_MAX_MODEL_LEN", "4096"))
    print(f"📋 Using model from environment: {MODEL_NAME}")
else:
    # Auto-select model based on GPU VRAM
    gpu_memory = get_gpu_memory_gb()
    if gpu_memory:
        print(f"🎮 Detected GPU VRAM: {gpu_memory:.1f} GB")
        MODEL_NAME, QUANTIZATION, MAX_MODEL_LEN = select_model_by_vram(gpu_memory)
        print(f"🤖 Auto-selected model: {MODEL_NAME}")
    else:
        # Fallback to default (safe for most GPUs)
        print("⚠️  Could not detect GPU VRAM, using default model")
        MODEL_NAME = "hugging-quants/Meta-Llama-3.1-8B-Instruct-AWQ-INT4"
        QUANTIZATION = "awq"
        MAX_MODEL_LEN = 4096

GPU_MEMORY_UTIL = float(os.getenv("VLLM_GPU_MEMORY_UTILIZATION", "0.90"))

# Environment check (for debugging)
print(f"🔍 Environment Check:")
print(f"   VLLM_USE_V1={os.getenv('VLLM_USE_V1')}")
print(f"   Model: {MODEL_NAME}")

try:
    llm = LLM(
        model=MODEL_NAME,
        quantization=QUANTIZATION,  # Enable AWQ quantization
        gpu_memory_utilization=GPU_MEMORY_UTIL,
        max_model_len=MAX_MODEL_LEN,
        trust_remote_code=True,  # Required for some models
        dtype="half",  # Use FP16
        enforce_eager=True,  # Disable CUDA graph (fixes RoPE scaling issues)
    )
    print(f"✅ vLLM Model Loaded: {MODEL_NAME}")
    print(f"   Quantization: {QUANTIZATION.upper()}")
    print(f"   GPU Memory Utilization: {GPU_MEMORY_UTIL * 100}%")
    print(f"   Max Model Length: {MAX_MODEL_LEN} tokens")
except Exception as e:
    print(f"❌ Failed to load vLLM model: {e}")
    print(f"💡 Model: {MODEL_NAME}")
    print(f"💡 Quantization: {QUANTIZATION}")
    print(f"💡 VLLM_USE_V1: {os.getenv('VLLM_USE_V1')}")
    print("💡 Tip: For RTX 4070 (12GB), use AWQ 4-bit quantized models")
    import traceback
    traceback.print_exc()
    raise


def generate_search_queries(topic, llm, max_queries=5):
    """
    Phase 1: Generate diverse search queries for a given topic
    
    Args:
        topic: User's search topic
        llm: vLLM instance
        max_queries: Maximum number of queries to generate
        
    Returns:
        List of search query strings
    """
    system_prompt = """You are a search query generator.

Generate 3-5 diverse search queries in Korean to comprehensively research the topic.

Rules:
1. Output in Korean only
2. Each query explores different aspects
3. One query per line
4. No numbering, bullets, or extra formatting"""

    user_prompt = f"""Topic: {topic}

Generate 3-5 diverse search queries:"""

    prompt = f"""<|begin_of_text|><|start_header_id|>system<|end_header_id|>

{system_prompt}<|eot_id|><|start_header_id|>user<|end_header_id|>

{user_prompt}<|eot_id|><|start_header_id|>assistant<|end_header_id|>

"""

    sampling_params = SamplingParams(
        temperature=0.8,  # Higher for diversity
        top_p=0.9,
        max_tokens=200,
        stop=["\n\n"]
    )

    print("🧠 Generating search queries...")
    outputs = llm.generate([prompt], sampling_params)
    queries_text = outputs[0].outputs[0].text.strip()
    
    # Split by newlines and clean
    queries = [q.strip() for q in queries_text.split('\n') if q.strip()]
    queries = queries[:max_queries]
    
    print(f"✅ Generated {len(queries)} queries:")
    for idx, q in enumerate(queries, 1):
        print(f"   {idx}. {q}")
    
    return queries


def analyze_search_results(request_id, topic, db, llm):
    """
    Phase 2: Analyze search results and generate summary
    Uses Map-Reduce if context exceeds limit.

    Args:
        request_id: UUID of the request
        topic: Original user topic
        db: Database session
        llm: vLLM instance
        
    Returns:
        tuple: (summary_text, inference_time_ms)
    """
    start_time = time_module.time()
    
    # Get search results from DB
    db_request = db.query(Request).filter(Request.id == request_id).first()
    search_results = db_request.search_results
    
    if not search_results:
        raise ValueError(f"No search results found for request {request_id}")
    
    print(f"📚 Found {len(search_results)} search results")
    
    # 1. Initialize Tokenizer & Constants
    tokenizer = llm.get_tokenizer()
    
    # Reserve tokens:
    # System Prompt (~200) + User Template (~100) + Output Buffer (~1500) = ~1800
    # Safe Context Limit = MAX_MODEL_LEN - 1800
    RESERVED_TOKENS = 1800
    MAX_CONTEXT_TOKENS = MAX_MODEL_LEN - RESERVED_TOKENS
    
    # Chunk size for "Map" phase (smaller to fit multiple chunks if needed, or just safe margin)
    # If we map, we want chunks to be well within limits.
    MAP_CHUNK_SIZE = 3000 
    
    # 2. Prepare content items
    content_items = []
    for idx, result in enumerate(search_results, 1):
        # Format: "[Result N] Title: ... Content: ..."
        content = result.content[:10000] if result.content else "" # Hard cap just in case
        text_item = (
            f"[결과 {idx}]\n"
            f"제목: {result.title}\n"
            f"URL: {result.url}\n"
            f"내용: {content}\n"
        )
        content_items.append(text_item)
        
    # 3. Calculate total tokens
    full_context_str = "\n---\n".join(content_items)
    total_tokens = len(tokenizer.encode(full_context_str))
    
    print(f"📊 Total Context Tokens: {total_tokens} (Limit: {MAX_CONTEXT_TOKENS})")
    
    final_context = ""
    
    # 4. Strategy Selection
    if total_tokens <= MAX_CONTEXT_TOKENS:
        # --- STRATEGY A: Direct Analysis (Fits in context) ---
        print("✅ Context fits in limit. Proceeding with direct analysis.")
        final_context = full_context_str
        
    else:
        # --- STRATEGY B: Map-Reduce ---
        print("⚠️  Context exceeds limit. Triggering Map-Reduce...")
        
        # [Map Phase] Split into chunks and summarize individually
        chunks = []
        current_chunk = []
        current_tokens = 0
        
        for item in content_items:
            item_tokens = len(tokenizer.encode(item))
            
            # If a single item is too huge, truncate it (rare but possible)
            if item_tokens > MAP_CHUNK_SIZE:
                # Naive truncation for simple safety
                ratio = MAP_CHUNK_SIZE / item_tokens
                cut_len = int(len(item) * ratio)
                item = item[:cut_len] + "...(truncated)"
                item_tokens = MAP_CHUNK_SIZE
            
            if current_tokens + item_tokens > MAP_CHUNK_SIZE:
                # Finalize current chunk
                chunks.append("\n---\n".join(current_chunk))
                current_chunk = [item]
                current_tokens = item_tokens
            else:
                current_chunk.append(item)
                current_tokens += item_tokens
        
        if current_chunk:
            chunks.append("\n---\n".join(current_chunk))
            
        print(f"🧩 Split into {len(chunks)} chunks for parallel summarization.")
        
        # Generate summaries for each chunk in parallel
        map_prompts = []
        map_system_prompt = "You are a research assistant. Summarize the provided search results in Korean. Extract key facts relevant to the topic."
        
        for i, chunk in enumerate(chunks, 1):
            user_msg = f"Topic: {topic}\n\nChunk {i}/{len(chunks)}:\n{chunk}\n\nSummarize key points in Korean:"
            # Construct prompt for this chunk
            p = f"<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n\n{map_system_prompt}<|eot_id|><|start_header_id|>user<|end_header_id|>\n\n{user_msg}<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n\n"
            map_prompts.append(p)
            
        print(f"🚀 Running batch inference for {len(chunks)} chunks...")
        
        # Use slightly more aggressive params for speed
        map_params = SamplingParams(temperature=0.7, max_tokens=1024)
        map_outputs = llm.generate(map_prompts, map_params)
        
        intermediate_summaries = []
        for output in map_outputs:
            intermediate_summaries.append(output.outputs[0].text.strip())
            
        # [Reduce Phase] Combine summaries
        print("🔗 Combining intermediate summaries...")
        combined_summaries = "\n\n---\n\n".join([f"Summary Part {i+1}:\n{s}" for i, s in enumerate(intermediate_summaries)])
        
        final_context = combined_summaries
        print(f"📉 Reduced Context Tokens: {len(tokenizer.encode(final_context))}")

    # 5. Final Analysis
    # System prompt for analysis
    system_prompt = """You are a professional information summarization assistant.

CRITICAL RULES:
1. Respond in Korean language ONLY (한국어로만 답변)
2. Summarize based ONLY on the provided search results
3. Be concise - use 3-5 paragraphs maximum
4. Do NOT repeat content
5. Ignore irrelevant results
6. Do NOT mention sources explicitly unless critical

Your response must be entirely in Korean."""

    user_prompt = f"""Topic: {topic}

Search Results (or Summarized Context):
{final_context}

Summarize the above information about '{topic}' in Korean language."""

    # Llama 3.1 Chat Template
    prompt = f"""<|begin_of_text|><|start_header_id|>system<|end_header_id|>

{system_prompt}<|eot_id|><|start_header_id|>user<|end_header_id|>

{user_prompt}<|eot_id|><|start_header_id|>assistant<|end_header_id|>

"""

    # Analysis sampling params
    sampling_params = SamplingParams(
        temperature=0.7,
        top_p=0.9,
        max_tokens=1536,
        repetition_penalty=1.1,
        frequency_penalty=0.2
    )

    # LLM inference
    print("🧠 Analyzing with vLLM (Final Pass)...")
    outputs = llm.generate([prompt], sampling_params)
    summary = outputs[0].outputs[0].text.strip()
    
    inference_time_ms = int((time_module.time() - start_time) * 1000)
    
    print(f"✅ Analysis completed in {inference_time_ms}ms (Total)")
    print(f"📊 Summary length: {len(summary)} characters")
    print("\n" + "=" * 60)
    print("GENERATED SUMMARY:")
    print("-" * 60)
    print(summary)
    print("=" * 60 + "\n")
    
    return summary, inference_time_ms


def process_ai():
    consumer = KafkaConsumerWrapper(
        topic=settings.KAFKA_TOPIC_AI, group_id=settings.KAFKA_GROUP_AI
    )

    print(f"🤖 [AI Worker] Ready for inference...")

    for message in consumer.get_messages():
        db = SessionLocal()
        try:
            task = message.value
            request_id = task.get("request_id")
            topic = task.get("topic")
            phase = task.get("phase", "analyze")  # Default to analysis phase

            print("\n" + "=" * 60)
            print(f"Request ID: {request_id}")
            print(f"Topic: {topic}")
            print(f"Phase: {phase}")

            if phase == "generate_queries":
                # Phase 1: Generate search queries (future implementation)
                print("⚠️  Query generation phase not yet implemented")
                print("⚠️  Falling back to analysis phase")
                phase = "analyze"
            
            if phase == "analyze":
                # Phase 2: Analyze search results
                
                # 🔒 Pessimistic Lock: Row-level locking
                lock_query = text("""
                    SELECT id, status 
                    FROM requests 
                    WHERE id = :request_id 
                    AND status = 'analyzing'
                    FOR UPDATE SKIP LOCKED
                """)
                
                result = db.execute(lock_query, {"request_id": request_id}).fetchone()
                
                if not result:
                    existing = db.query(Request).filter(Request.id == request_id).first()
                    if existing:
                        if existing.status == 'analyzing':
                            print(f"🔒 Request {request_id} locked by another worker, skipping")
                        else:
                            print(f"⏭️  Request {request_id} already processed (status: {existing.status})")
                    else:
                        print(f"❌ Request {request_id} not found")
                    consumer.consumer.commit()
                    continue

                # Claim the request
                db_request = db.query(Request).filter(Request.id == request_id).first()
                db_request.status = 'processing_analysis'
                db.commit()
                print(f"✅ Locked and claimed request {request_id}")

                # Analyze search results
                summary, inference_time_ms = analyze_search_results(
                    request_id, topic, db, llm
                )

                # Save analysis result
                analysis_result = AnalysisResult(
                    request_id=request_id,
                    summary=summary,
                    inference_time_ms=inference_time_ms
                )
                db.add(analysis_result)

                # Update request status
                db_request.status = "completed"
                db_request.completed_at = datetime.utcnow()
                db.commit()

                # Commit Kafka offset
                consumer.consumer.commit()
                print(f"Kafka offset committed")
                print(f"Request {request_id} completed!")

        except Exception as e:
            print(f"AI Worker Error: {e}")
            import traceback
            traceback.print_exc()
            
            # Update to failed status
            if 'request_id' in locals() and request_id:
                try:
                    db_request = db.query(Request).filter(Request.id == request_id).first()
                    if db_request:
                        db_request.status = "failed"
                        db_request.error_message = str(e)
                        db.commit()
                except:
                    pass
        finally:
            db.close()


if __name__ == "__main__":
    process_ai()
