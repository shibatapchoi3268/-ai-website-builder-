import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from urllib.parse import urlparse

from google import genai
from google.genai import types
from google.genai.errors import APIError


_MODELS = ("gemini-3.8-flash", "gemini-3.6-flash")
_MAX_HISTORY_MESSAGES = 20
_SYSTEM_INSTRUCTION = (
    "Bạn là trợ lý nghiên cứu hữu ích. Trả lời bằng ngôn ngữ người dùng. "
    "Tự quyết định khi nào cần Google Search; hãy tìm kiếm với thông tin mới, "
    "sự kiện, dữ kiện cụ thể hoặc khi người dùng yêu cầu tra cứu. Dựa trên "
    "nguồn tìm được, nêu rõ điều gì chưa chắc chắn và không bịa nguồn."
)


@dataclass(frozen=True)
class Source:
    title: str
    url: str


@dataclass(frozen=True)
class ResearchAnswer:
    text: str
    sources: tuple[Source, ...]


def _build_contents(
    prompt: str, history: Sequence[Mapping[str, str]]
) -> list[types.Content]:
    contents = []
    for message in history[-_MAX_HISTORY_MESSAGES:]:
        role = message.get("role")
        text = message.get("content")
        if role not in ("user", "assistant") or not isinstance(text, str) or not text.strip():
            continue
        contents.append(
            types.Content(
                role="model" if role == "assistant" else "user",
                parts=[types.Part(text=text)],
            )
        )
    contents.append(types.Content(role="user", parts=[types.Part(text=prompt)]))
    return contents


def _extract_text(response: types.GenerateContentResponse) -> str:
    text_parts = []
    for candidate in response.candidates or []:
        content = candidate.content
        if content is None:
            continue
        for part in content.parts or []:
            if part.text and not part.thought:
                text_parts.append(part.text)
    return "\n".join(text_parts).strip()


def _extract_sources(response: types.GenerateContentResponse) -> tuple[Source, ...]:
    sources = []
    seen_urls = set()
    for candidate in response.candidates or []:
        metadata = candidate.grounding_metadata
        if metadata is None:
            continue
        for chunk in metadata.grounding_chunks or []:
            web_source = chunk.web
            if web_source is None or not web_source.uri:
                continue
            parsed_url = urlparse(web_source.uri)
            if parsed_url.scheme not in ("http", "https") or not parsed_url.netloc:
                continue
            if web_source.uri in seen_urls:
                continue
            seen_urls.add(web_source.uri)
            sources.append(
                Source(
                    title=web_source.title or parsed_url.netloc,
                    url=web_source.uri,
                )
            )
    return tuple(sources)


def research(
    prompt: str,
    api_key: str,
    history: Sequence[Mapping[str, str]] = (),
) -> ResearchAnswer:
    """Answer a chat prompt with Gemini and its native Google Search grounding."""
    prompt = prompt.strip()
    api_key = api_key.strip()
    if not prompt:
        raise ValueError("Vui lòng nhập câu hỏi.")
    if not api_key:
        raise ValueError("Vui lòng nhập Gemini API key.")

    client = genai.Client(api_key=api_key)
    config = types.GenerateContentConfig(
        system_instruction=_SYSTEM_INSTRUCTION,
        tools=[types.Tool(google_search=types.GoogleSearch())],
    )
    try:
        for model_index, model in enumerate(_MODELS):
            for attempt in range(2):
                try:
                    response = client.models.generate_content(
                        model=model,
                        contents=_build_contents(prompt, history),
                        config=config,
                    )
                except APIError as error:
                    if error.code != 503:
                        raise RuntimeError(
                            f"Gemini API trả về lỗi {error.code}: {error}"
                        ) from error
                    if attempt == 0:
                        time.sleep(2)
                        continue
                    if model_index == len(_MODELS) - 1:
                        raise RuntimeError(
                            "Gemini đang quá tải. Hệ thống đã thử lại và chuyển "
                            "sang Gemini 3.6 Flash nhưng dịch vụ vẫn chưa khả dụng. "
                            "Vui lòng đợi một lúc rồi thử lại."
                        ) from error
                    break

                answer_text = _extract_text(response)
                if not answer_text:
                    raise RuntimeError("Gemini không trả về nội dung văn bản.")
                return ResearchAnswer(
                    text=answer_text,
                    sources=_extract_sources(response),
                )
    finally:
        client.close()

    raise RuntimeError("Không thể hoàn tất yêu cầu nghiên cứu.")
