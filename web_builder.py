import streamlit as st

from services.research_engine import ResearchAnswer, research


st.set_page_config(page_title="AI Research Chat", page_icon="🔎")
st.title("🔎 AI Research Chat")
st.caption(
    "Hỏi đáp tự nhiên với Gemini. Khi cần thông tin trên web, Gemini có thể "
    "tìm kiếm và hiển thị các nguồn tham khảo."
)

with st.sidebar:
    st.header("Cấu hình Gemini")
    api_key = st.text_input("Gemini API key", type="password")
    st.caption("Key chỉ được dùng trong phiên này và gửi đến Google Gemini.")
    if st.button("Xóa cuộc trò chuyện"):
        st.session_state.messages = []
        st.rerun()

if "messages" not in st.session_state:
    st.session_state.messages = []


def _show_sources(answer: ResearchAnswer) -> None:
    if answer.sources:
        st.caption("Nguồn tham khảo")
        for source in answer.sources:
            st.link_button(source.title, source.url)


for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        if message.get("error"):
            st.error(message["content"])
        else:
            st.markdown(message["content"])
            for source in message.get("sources", []):
                st.link_button(source["title"], source["url"])

prompt = st.chat_input("Bạn muốn tìm hiểu điều gì?")
if prompt:
    previous_messages = [
        {"role": item["role"], "content": item["content"]}
        for item in st.session_state.messages
        if not item.get("error")
    ]
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    if not api_key.strip():
        error_message = "Vui lòng nhập Gemini API key trong thanh bên trước khi gửi câu hỏi."
        st.session_state.messages.append(
            {"role": "assistant", "content": error_message, "error": True}
        )
        with st.chat_message("assistant"):
            st.error(error_message)
    else:
        with st.chat_message("assistant"):
            try:
                with st.spinner("Gemini đang suy nghĩ và tìm kiếm thông tin..."):
                    answer = research(prompt, api_key, previous_messages)
            except RuntimeError as error:
                error_message = str(error)
                st.session_state.messages.append(
                    {"role": "assistant", "content": error_message, "error": True}
                )
                st.error(error_message)
            else:
                sources = [
                    {"title": source.title, "url": source.url}
                    for source in answer.sources
                ]
                st.session_state.messages.append(
                    {
                        "role": "assistant",
                        "content": answer.text,
                        "sources": sources,
                    }
                )
                st.markdown(answer.text)
                _show_sources(answer)
