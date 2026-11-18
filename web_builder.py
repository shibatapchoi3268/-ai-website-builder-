import streamlit as st
from services.core_engine import generate_website

# Cấu hình giao diện trang web
st.set_page_config(page_title="AI Web Builder Agent", page_icon="🚀", layout="wide")

st.title("🚀 Hệ Thống Đa Tác Nhân (Multi-Agent Web Builder)")
st.markdown("Nhập ý tưởng của bạn, AI sẽ tự động viết code HTML/CSS/JS cho bạn.")

# ==========================================
# GIAO DIỆN THANH BÊN (SIDEBAR) - CẤU HÌNH API
# ==========================================
with st.sidebar:
    st.header("⚙️ Cấu hình AI Model")

    # 1. Cho người dùng chọn Model
    provider = st.selectbox(
        "Chọn nhà cung cấp AI:",
        ["Google Gemini", "OpenAI (ChatGPT)", "Groq"]
    )

    # 2. Ô nhập API Key
    user_api_key = st.text_input("Nhập API Key của bạn:", type="password")

    st.markdown("---")
    st.info(
        "API key được xử lý trong phiên này để gửi yêu cầu đến nhà cung cấp AI. "
        "Ứng dụng không lưu key vào mã nguồn hoặc tệp cấu hình."
    )

provider_ids = {
    "Google Gemini": "gemini",
    "OpenAI (ChatGPT)": "openai",
    "Groq": "groq",
}

# ==========================================
# GIAO DIỆN CHÍNH - NHẬP YÊU CẦU & KẾT QUẢ
# ==========================================
user_prompt = st.text_area(
    "Bạn muốn làm trang web như thế nào?",
    height=150,
    placeholder="Ví dụ: Tạo một trang web bán đồng hồ thông minh với giao diện màu đen sang trọng..."
)

# Nút Bấm Thực Thi
if st.button("✨ Bắt đầu tạo Website", type="primary"):

    # Kiểm tra xem người dùng đã nhập API Key chưa
    if not user_api_key:
        st.error("⚠️ Vui lòng nhập API Key ở thanh bên trái trước khi bắt đầu!")
    elif not user_prompt:
        st.error("⚠️ Vui lòng nhập yêu cầu trang web của bạn!")
    else:
        with st.spinner(
            "AI đang viết và kiểm tra mã; nếu Gemini quá tải, hệ thống sẽ thử lại "
            "và chuyển model dự phòng... ☕"
        ):
            try:
                html_code = generate_website(
                    provider=provider_ids[provider],
                    api_key=user_api_key,
                    user_prompt=user_prompt,
                )
                st.success("✅ Mã đã vượt qua các bước kiểm tra tự động:")
                st.caption(
                    "Kiểm tra cấu trúc HTML và cú pháp JavaScript nếu Node.js có sẵn; "
                    "mã được tạo không chạy trên máy chủ."
                )
                st.code(html_code, language="html")
                st.download_button(
                    label="📥 Tải file index.html",
                    data=html_code,
                    file_name="index.html",
                    mime="text/html",
                )
            except Exception as error:
                st.error(f"❌ Không thể tạo mã website: {error}")