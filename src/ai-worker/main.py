import os

# CRITICAL: v0 API 강제 사용 - vLLM import 전에 환경변수 설정 필수!
# vLLM은 import 시점에 v0/v1을 결정하므로 반드시 import 전에 설정해야 함
os.environ["VLLM_USE_V1"] = "0"
print("🔒 Forced VLLM_USE_V1=0 (before vLLM import)")

from vllm import LLM, SamplingParams
from common.config import settings
from common.utils import KafkaConsumerWrapper

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


def process_ai():
    from common.database import SessionLocal, Request, AnalysisResult
    from datetime import datetime
    import time as time_module
    
    consumer = KafkaConsumerWrapper(
        topic=settings.KAFKA_TOPIC_AI, group_id=settings.KAFKA_GROUP_AI
    )

    print(f"🤖 [AI Worker] Ready for inference...")

    # vLLM 샘플링 파라미터 설정
    sampling_params = SamplingParams(
        temperature=0.7,
        top_p=0.9,
        max_tokens=1536,
        repetition_penalty=1.1,      # 반복 방지 (1.0 = 없음, 1.1 = 약간, 1.5 = 강함)
        frequency_penalty=0.2,        # 같은 토큰 반복 패널티
        presence_penalty=0.0,         # 새로운 토픽 유도
    )

    for message in consumer.get_messages():
        db = SessionLocal()
        start_time = time_module.time()
        try:
            task = message.value
            request_id = task.get("request_id")
            topic = task.get("topic")

            print("\n" + "=" * 60)
            print(f"📥 Request ID: {request_id}")
            print(f"� Topic: {topic}")

            # DB에서 검색 결과 조회
            db_request = db.query(Request).filter(Request.id == request_id).first()
            if not db_request:
                print(f"❌ Request {request_id} not found in database")
                continue

            # 🔒 Idempotency: 이미 완료된 요청은 스킵
            if db_request.status == "completed":
                print(f"⏭️ Request {request_id} already completed, skipping duplicate...")
                consumer.consumer.commit()  # Offset만 커밋
                continue

            search_results = db_request.search_results
            if not search_results:
                print(f"❌ No search results found for request {request_id}")
                db_request.status = "failed"
                db_request.error_message = "No search results to analyze"
                db.commit()
                consumer.consumer.commit()  # Offset 커밋
                continue

            # 컨텍스트 구성
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

            # 시스템 프롬프트 (Llama 3.1 최적화)
            system_prompt = """You are a professional information summarization assistant.

CRITICAL RULES:
1. Respond in Korean language ONLY (한국어로만 답변)
2. Summarize based ONLY on the provided search results
3. Be concise - use 3-5 paragraphs maximum
4. Do NOT repeat content
5. Ignore irrelevant results
6. Do NOT mention sources explicitly unless critical

Your response must be entirely in Korean."""

            # 사용자 프롬프트
            user_prompt = f"""Topic: {topic}

Search Results:
{context}

Summarize the above search results about '{topic}' in Korean language."""

            # Llama 3.1 Chat Template
            prompt = f"""<|begin_of_text|><|start_header_id|>system<|end_header_id|>

{system_prompt}<|eot_id|><|start_header_id|>user<|end_header_id|>

{user_prompt}<|eot_id|><|start_header_id|>assistant<|end_header_id|>

"""

            # LLM 추론
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

            # DB에 분석 결과 저장
            analysis_result = AnalysisResult(
                request_id=request_id,
                summary=summary,
                inference_time_ms=inference_time_ms
            )
            db.add(analysis_result)

            # 요청 상태 업데이트: analyzing → completed
            db_request.status = "completed"
            db_request.completed_at = datetime.utcnow()
            db.commit()
            print(f"💾 Analysis result saved to database")

            # ✅ Kafka offset 커밋 (DB 저장 성공 후)
            consumer.consumer.commit()
            print(f"📌 Kafka offset committed")
            print(f"🎉 Request {request_id} completed!")

        except Exception as e:
            print(f"❌ AI Worker Error: {e}")
            import traceback
            traceback.print_exc()
            
            # 에러 상태 저장
            if 'request_id' in locals() and request_id:
                db_request = db.query(Request).filter(Request.id == request_id).first()
                if db_request:
                    db_request.status = "failed"
                    db_request.error_message = str(e)
                    db.commit()
        finally:
            db.close()


if __name__ == "__main__":
    process_ai()
