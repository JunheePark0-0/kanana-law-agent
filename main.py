"""
Agent 전체 실행 파일 - Kanana 버전
"""

import os
from dotenv import load_dotenv
load_dotenv(".env")

# Config 및 Logger import
from config import Config
import utils.logger as app_logger
from utils.logger import log_agent_action

from src.Agent.schemas import UserInput
from src.Agent.kanana_pipeline import get_kanana_pipeline
from src.Agent.graph import legal_agent

def legal_agent_main():
    """Legal Agent 메인 함수 - Kanana 버전"""
    # ============================================================================
    # 환경 설정 - 사용자 입력으로 설정
    # ============================================================================
    print("=" * 60)
    print("⚖️  Legal Agent - Kanana 버전")
    print("=" * 60)
    print("🔧 환경 설정:")
    
    enable_local_logging = input("로컬 로깅을 활성화하시겠습니까? (Y/N): ").strip().lower()
    if enable_local_logging == 'y':
        Config.ENABLE_LOCAL_LOGGING = True
    else:
        Config.ENABLE_LOCAL_LOGGING = False
    
    # 로컬 로깅 설정에 따라 logger 재설정
    app_logger.setup_logger()
    
    print("\n📋 현재 설정:")
    config_summary = Config.get_config_summary()
    for key, value in config_summary.items():
        print(f" • {key}: {value}")
    print()

    if Config.ENABLE_LOCAL_LOGGING:
        now_str = __import__('datetime').datetime.now().strftime('%Y%m%d_%H%M%S')
        log_filename = f"logs/law_agent_{now_str}.log"
        print(f"📝 로컬 로그: {log_filename}")
        app_logger.logger.info(f"로컬 로깅 활성화: {now_str}")
    else:
        print("📝 로컬 로그: 비활성화")
        log_filename = None

    # ============================================================================
    # Kanana 파이프라인 초기화
    # ============================================================================
    print("\n" + "=" * 60)
    print("🔄 Kanana 모델 초기화 중...")
    print("⚠️  처음 실행 시 모델 다운로드 및 로드에 몇 분이 걸릴 수 있습니다.")
    print("   (이후 실행 시에는 이미 로드된 모델을 사용하므로 빠릅니다.)\n")
    
    if Config.ENABLE_LOCAL_LOGGING:
        log_agent_action("Kanana 모델 로드 시작")
    
    get_kanana_pipeline()
    
    print("\n" + "=" * 60)
    if Config.ENABLE_LOCAL_LOGGING:
        log_agent_action("Kanana 모델 로드 완료")
    
    # ============================================================================
    # Agent 초기화 (모델은 이미 로드됨)
    # ============================================================================
    print("🔧 Agent 워크플로우 초기화 중...")
    agent = legal_agent()
    print("✅ Agent 준비 완료!")
    
    # ============================================================================
    # 대화형 모드: 여러 질문을 연속으로 처리
    # ============================================================================
    print("=" * 60)
    print("💬 대화형 모드")
    print("=" * 60)
    print("💡 팁: 모델이 이미 로드되어 있어 빠르게 답변할 수 있습니다!")
    print("   종료하려면 'quit', 'exit', 또는 'q'를 입력하세요.\n")
    
    question_count = 0
    while True:
        try:
            question_count += 1
            print(f"\n{'─' * 60}")
            print(f"질문 #{question_count}")
            print(f"{'─' * 60}")
            
            query = input("\n질문을 입력해주세요 (종료: quit/exit/q): ").strip()
            
            # 종료 조건
            if query.lower() in ['quit', 'exit', 'q', '']:
                print("\n👋 프로그램을 종료합니다.")
                break
            
            document_path = input("\n함께 첨부하실 문서가 있다면 경로를 입력해주세요 (없으면 Enter): \n").strip()
            
            if Config.ENABLE_LOCAL_LOGGING:
                log_agent_action("사용자 입력 수신", {
                    "question_number": question_count,
                    "has_query": bool(query),
                    "has_document": bool(document_path)
                })
            
            # ============================================================================
            # Legal Agent 실행
            # ============================================================================
            original_input = UserInput(
                query = query if query else None, 
                document_path = document_path if document_path else None
            )
            
            if Config.ENABLE_LOCAL_LOGGING:
                log_agent_action("에이전트 워크플로우 시작")
            
            result = agent.invoke({
                "original_input" : original_input,
                "input_query" : query if query else ""
            })
            
            if result.get("input_type") == "Error":
                error_message = result.get("error_message", "알 수 없는 오류가 발생했습니다.")
                print("=" * 60)
                print(f"❌ 오류가 발생했습니다: {error_message}")
                print("=" * 60)
                if Config.ENABLE_LOCAL_LOGGING:
                    app_logger.logger.error(f"워크플로우 오류: {error_message}")
                continue  # 다음 질문으로 계속
            
            if result.get("answer"):
                answer = result.get("answer").answer
                if Config.ENABLE_LOCAL_LOGGING:
                    app_logger.logger.info("\n" + "=" * 30)
                    app_logger.logger.info("[최종 답변]")
                    app_logger.logger.info(f"\n{answer}")
                    app_logger.logger.info("\n" + "=" * 30)
                print("\n" + "=" * 60)
                print("🔎 최종 답변")
                print("=" * 60)
                print(f"\n{answer}\n")
                
                if Config.ENABLE_LOCAL_LOGGING:
                    from utils.logger import log_conversation
                    log_conversation(query, answer)

            print("=" * 60)
            print("✅ 답변 완료!")
            print("=" * 60)
            
            if Config.ENABLE_LOCAL_LOGGING:
                log_agent_action("에이전트 워크플로우 완료")
                
        except KeyboardInterrupt:
            print("\n\n⚠️  사용자가 중단했습니다.")
            break
        except Exception as e:
            print(f"\n❌  Legal Agent 실행 중 오류가 발생했습니다: {e}")
            print("=" * 60)
            if Config.ENABLE_LOCAL_LOGGING:
                from utils.logger import log_error
                log_error(e, "legal_agent_main")
            print("\n다음 질문을 계속 진행할 수 있습니다.\n")
            continue
    
    print("\n" + "=" * 60)
    print(f"🎉 총 {question_count - 1}개의 질문을 처리했습니다!")
    print("=" * 60) 

if __name__ == "__main__":
    legal_agent_main()