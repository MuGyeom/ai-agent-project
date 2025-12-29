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
    consumer = KafkaConsumerWrapper(
        topic=settings.KAFKA_TOPIC_AI, group_id=settings.KAFKA_GROUP_AI
    )

    print(f"🤖 [AI Worker] Ready for inference...")

    # vLLM 샘플링 파라미터 설정
    sampling_params = SamplingParams(
        temperature=0.7,
        top_p=0.9,
        max_tokens=1024,
    )

    for message in consumer.get_messages():
        try:
            task = message.value
            original_topic = task.get("original_topic")
            context = task.get("context")

            print("\n" + "=" * 60)
            print(f"📥 Topic: {original_topic}")
            print(f"📄 Context Length: {len(context)} characters")
            print("=" * 60)

            # 프롬프트 생성
            prompt = f"""You are a research assistant. Analyze the following web search results and provide a comprehensive summary.

Topic: {original_topic}

Search Results:
{context}

Please provide:
1. A concise summary of the key findings
2. Main themes and insights
3. Relevant conclusions

Summary:"""

            # vLLM 추론 실행
            print("🧠 Generating summary with vLLM...")
            outputs = llm.generate([prompt], sampling_params)
            summary = outputs[0].outputs[0].text.strip()

            # 결과 출력
            print("\n" + "🎯 " + "=" * 58)
            print("GENERATED SUMMARY:")
            print("=" * 60)
            print(summary)
            print("=" * 60)
            print(f"✅ Generated {len(summary)} characters\n")

            # TODO: 추후 DB 저장 또는 Kafka 토픽으로 결과 전송
            # producer.send_data(topic="results-queue", value={
            #     "topic": original_topic,
            #     "summary": summary,
            #     "timestamp": time.time()
            # })

        except Exception as e:
            print(f"❌ Error during inference: {e}")
            import traceback

            traceback.print_exc()


if __name__ == "__main__":
    process_ai()
