import sys
from pathlib import Path

# Ensure src is on sys.path
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from config.settings import AppSettings
from recognition.postprocessor import TextPostprocessor


def print_header(title: str) -> None:
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)


def run_llm_test(settings: AppSettings) -> None:
    post_cfg = settings.postprocess
    backend = (post_cfg.llm_backend or "").lower()

    print_header("ТЕКУЩИЕ НАСТРОЙКИ LLM")
    print(f"postprocess.enabled        = {post_cfg.enabled}")
    print(f"postprocess.mode           = {post_cfg.mode}")
    print(f"postprocess.llm_backend    = {post_cfg.llm_backend}")
    print(f"Groq model (postprocess)   = {getattr(post_cfg.groq, 'model', '')}")
    print(f"OpenAI model (postprocess) = {getattr(post_cfg.openai, 'model', '')}")
    print(f"OpenAI base_url            = {getattr(post_cfg.openai, 'base_url', '')}")
    print(f"Groq api_key set?          = {bool(getattr(post_cfg.groq, 'api_key', ''))}")
    print(f"OpenAI api_key set?        = {bool(getattr(post_cfg.openai, 'api_key', ''))}")

    if not post_cfg.enabled:
        print("\n[SKIP] postprocess.enabled = false → LLM не используется.")
        return

    if (post_cfg.mode or "").lower() != "llm":
        print(f"\n[SKIP] postprocess.mode = {post_cfg.mode!r} (ожидается 'llm').")
        return

    if backend not in {"groq", "openai"}:
        print(f"\n[SKIP] postprocess.llm_backend = {post_cfg.llm_backend!r} (ожидается 'groq' или 'openai').")
        return

    print_header("ЗАПУСК ТЕСТОВОГО ЗАПРОСА К LLM")
    print(f"Backend: {backend}")

    postprocessor = TextPostprocessor(config=post_cfg)

    test_text = "привет как дела это тест без запятых"
    print(f"\nВходной текст: {test_text!r}")

    try:
        result = postprocessor.process(test_text)
    except Exception as exc:
        print("\n[ERROR] Исключение при вызове postprocessor.process():")
        print(f"{type(exc).__name__}: {exc}")
        return

    print("\nРезультат postprocessor.process():")
    print(repr(result))

    print_header("ИНТЕРПРЕТАЦИЯ РЕЗУЛЬТАТА")
    if result == test_text:
        print(
            "Текст совпадает с исходным.\n"
            "- Если в логах приложения есть сообщение вида\n"
            "  'LLM postprocess failed, fallback to regex-only',\n"
            "  значит LLM‑запрос упал и сработал fallback.\n"
            "- Если логов об ошибке LLM нет, значит LLM либо отключён,\n"
            "  либо режим postprocess.mode != 'llm'."
        )
    else:
        print(
            "Текст ИЗМЕНИЛСЯ по сравнению с исходным.\n"
            "Это означает, что LLM‑постпроцессинг ОТРАБОТАЛ успешно\n"
            "(по крайней мере, без исключений на уровне клиента)."
        )


def main() -> None:
    print_header("ЗАГРУЗКА НАСТРОЕК")
    # Загружаем настройки так же, как это делает приложение:
    settings = AppSettings.load_default()
    print(f"recognition.backend: {settings.recognition.backend}")
    print(f"postprocess.enabled: {settings.postprocess.enabled}")
    print(f"postprocess.mode: {settings.postprocess.mode}")
    print(f"postprocess.llm_backend: {settings.postprocess.llm_backend}")

    run_llm_test(settings)


if __name__ == "__main__":
    main()