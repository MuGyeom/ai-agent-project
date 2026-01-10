import os
from datetime import datetime
import time as time_module

# CRITICAL: v0 API 강제 사용 - vLLM import 전에 환경변수 설정 필수!
# vLLM은 import 시점에 v0/v1을 결정하므로 반드시 import 전에 설정해야 함
os.environ["VLLM_USE_V1"] = "0"
print("🔒 Forced VLLM_USE_V1=0 (before vLLM import)")

from vllm import LLM, SamplingParams
from sqlalchemy import text
from common.config import settings
from common.utils import KafkaConsumerWrapper
from common.database import SessionLocal, Request, AnalysisResult, SearchResult

# vLLM 모델 초기화 (Global - 프로그램 시작 시 한 번만)
print("🔧 Initializing vLLM Engine...")
MODEL_NAME = os.getenv("VLLM_MODEL", "Qwen/Qwen2.5-14B-Instruct-AWQ")
GPU_MEMORY_UTIL = float(os.getenv("VLLM_GPU_MEMORY_UTILIZATION", "0.90"))
MAX_MODEL_LEN = int(os.getenv("VLLM_MAX_MODEL_LEN", "4096"))
QUANTIZATION = os.getenv("VLLM_QUANTIZATION", "awq")  # AWQ 4-bit 양자화

# 환경변수 확인 (디버깅용)
print(f"🔍 Environment Check:")
print(f"   VLLM_USE_V1={os.getenv('VLLM_USE_V1')}")
print(f"   Model: {MODEL_NAME}")

try:
    llm = LLM(
        model=MODEL_NAME,
        quantization=QUANTIZATION,  # AWQ 양자화 활성화
        gpu_memory_utilization=GPU_MEMORY_UTIL,
        max_model_len=MAX_MODEL_LEN,
        trust_remote_code=True,  # Qwen 모델 사용 시 필요
        dtype="half",  # FP16 사용
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
    
    # Build context from search results
    print(f"📚 Found {len(search_results)} search results")
    context_parts = []
    for idx, result in enumerate(search_results, 1):
        context_parts.append(
            f"[결과 {idx}]\n"
            f"제목: {result.title}\n"
            f"URL: {result.url}\n"
            f"내용: {result.content}\n"
        )

    context = "\n---\n".join(context_parts)
    print(f"📄 Total Context Length: {len(context)} characters")

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

Search Results:
{context}

Summarize the above search results about '{topic}' in Korean language."""

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
        frequency_penalty=0.2,
        presence_penalty=0.0,
    )

    # LLM inference
    print("🧠 Analyzing with vLLM...")
    outputs = llm.generate([prompt], sampling_params)
    summary = outputs[0].outputs[0].text.strip()
    
    inference_time_ms = int((time_module.time() - start_time) * 1000)
    
    print(f"✅ Analysis completed in {inference_time_ms}ms")
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
