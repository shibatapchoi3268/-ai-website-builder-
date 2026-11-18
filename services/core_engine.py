import re
import shutil
import subprocess
from html.parser import HTMLParser

from crewai import Agent, Crew, LLM, Process, Task


class _HTMLInspector(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.tags = []
        self.end_tags = []
        self.scripts = []
        self._active_script = None

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        if tag == "script":
            attributes = dict(attrs)
            script_type = attributes.get("type", "").lower()
            if script_type in ("", "text/javascript", "application/javascript", "module"):
                self._active_script = [script_type == "module", []]

    def handle_data(self, data):
        if self._active_script is not None:
            self._active_script[1].append(data)

    def handle_endtag(self, tag):
        self.end_tags.append(tag)
        if tag == "script" and self._active_script is not None:
            is_module, parts = self._active_script
            self.scripts.append((is_module, "".join(parts)))
            self._active_script = None


def _strip_code_fence(code: str) -> str:
    match = re.match(r"\s*```(?:html)?\s*(.*?)\s*```\s*$", code, re.IGNORECASE | re.DOTALL)
    return match.group(1).strip() if match else code.strip()


def _validate_html(code: str) -> list:
    if not code.strip():
        return ["AI không trả về mã nguồn."]

    inspector = _HTMLInspector()
    try:
        inspector.feed(code)
        inspector.close()
    except Exception as error:
        return [f"Không phân tích được HTML: {error}"]

    issues = []
    lowered = code.lstrip().lower()
    if not lowered.startswith("<!doctype html"):
        issues.append("Thiếu khai báo <!DOCTYPE html> ở đầu tài liệu.")
    for tag in ("html", "head", "body"):
        if tag not in inspector.tags:
            issues.append(f"Thiếu thẻ <{tag}>.")
        elif tag not in inspector.end_tags:
            issues.append(f"Thiếu thẻ đóng </{tag}>.")

    document_tags = [tag for tag in inspector.tags if tag in ("html", "head", "body")]
    if document_tags[:3] != ["html", "head", "body"]:
        issues.append("Thứ tự thẻ tài liệu phải là <html>, <head>, <body>.")
    if inspector._active_script is not None:
        issues.append("Có thẻ <script> chưa được đóng.")

    node = shutil.which("node")
    if node:
        for index, (is_module, script) in enumerate(inspector.scripts, start=1):
            command = [node, "--check"]
            if is_module:
                command.extend(["--input-type=module"])
            command.append("-")
            try:
                result = subprocess.run(
                    command,
                    input=script,
                    capture_output=True,
                    text=True,
                    timeout=10,
                    check=False,
                )
            except subprocess.TimeoutExpired:
                issues.append(f"Đoạn JavaScript nội tuyến thứ {index} kiểm tra quá thời gian.")
                continue
            if result.returncode:
                detail = (result.stderr or result.stdout).strip()
                issues.append(f"JavaScript nội tuyến thứ {index} không hợp lệ: {detail}")

    return issues


def generate_website(provider: str, api_key: str, user_prompt: str, max_attempts: int = 3) -> str:
    """Generate a single-file website and return it only after validation."""
    provider = provider.strip().lower()
    user_prompt = user_prompt.strip()
    api_key = api_key.strip()
    if not user_prompt:
        raise ValueError("Vui lòng nhập yêu cầu trang web.")
    if not api_key:
        raise ValueError("Vui lòng nhập API key.")
    if not isinstance(max_attempts, int) or max_attempts < 1:
        raise ValueError("max_attempts phải là số nguyên dương.")

    providers = {
        "gemini": "gemini/gemini-3.8-flash",
        "openai": "gpt-4o-mini",
        "groq": "groq/llama3-8b-8192",
    }
    if provider not in providers:
        raise ValueError(f"Hệ thống chưa hỗ trợ nhà cung cấp: {provider}")

    coder_agent = Agent(
        role="Senior Web Developer",
        goal="Viết và tự kiểm tra mã website HTML/CSS/JavaScript hoàn chỉnh, responsive",
        backstory="Bạn là lập trình viên web giàu kinh nghiệm, ưu tiên mã chạy được và đáp ứng đúng yêu cầu.",
        llm=LLM(model=providers[provider], api_key=api_key),
        verbose=True,
    )

    previous_code = ""
    issues = []
    for attempt in range(1, max_attempts + 1):
        if attempt == 1:
            description = (
                f"Yêu cầu của người dùng: {user_prompt}\n"
                "Tạo website trong một file HTML duy nhất, gồm CSS trong <style> và JavaScript "
                "trong <script>. Trả về toàn bộ mã HTML, không giải thích."
            )
        else:
            description = (
                f"Yêu cầu ban đầu: {user_prompt}\n"
                f"Mã cần sửa:\n{previous_code}\n"
                f"Lỗi kiểm tra cần khắc phục:\n- " + "\n- ".join(issues) + "\n"
                "Hãy sửa mã để đáp ứng yêu cầu ban đầu và trả về toàn bộ file HTML hoàn chỉnh, "
                "không giải thích."
            )

        task = Task(
            description=description,
            expected_output="Toàn bộ mã HTML hoàn chỉnh, không có nội dung ngoài mã.",
            agent=coder_agent,
        )
        crew = Crew(
            agents=[coder_agent],
            tasks=[task],
            process=Process.sequential,
            verbose=True,
        )
        result = crew.kickoff()
        raw_code = getattr(result, "raw", result)
        if not isinstance(raw_code, str):
            raise TypeError("AI trả về kết quả không phải văn bản.")
        previous_code = _strip_code_fence(raw_code)
        issues = _validate_html(previous_code)
        if not issues:
            return previous_code

    raise RuntimeError(
        f"Không tạo được mã hợp lệ sau {max_attempts} lần thử. "
        "Lỗi kiểm tra cuối: " + "; ".join(issues)
    )
